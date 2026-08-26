#!/usr/bin/env python3
import json
import re
from collections import Counter
from pathlib import Path

SRC = Path("izivia/izivia_express_station_tariffs_v1.json")
OUT = Path("data/national/izivia_express_direct_tcc_v8.json")


def clean(value):
    return " ".join(re.sub(r"<br\s*/?>", " ", str(value or ""), flags=re.I).replace("\u00a0", " ").split())


def low(value):
    return clean(value).lower().replace(",", ".")


def num(value):
    return float(str(value).replace(",", "."))


def started_kwh_text(text):
    return bool(re.search(r"(?:kwh|énergie|energie)[^.!;]{0,45}entam|entam[^.!;]{0,45}(?:kwh|énergie|energie)", text))


def started_minute_text(text):
    return bool(re.search(r"(?:minute|durée|duree)[^.!;]{0,45}entam|entam[^.!;]{0,45}(?:minute|durée|duree)", text))


def parse_post_charge(text):
    for pattern in (
        r"(\d+(?:\.\d+)?)\s*€\s*/\s*(\d+)\s*mins?\s+(?:en\s+)?post[- ]charge",
        r"(\d+(?:\.\d+)?)\s*€\s*/\s*(\d+)\s*min\s+(?:en\s+)?post[- ]charge",
    ):
        match = re.search(pattern, text)
        if match:
            return {"billing": "started_block", "blockMinutes": int(match.group(2)), "blockFeeEur": num(match.group(1))}
    match = re.search(r"(\d+(?:\.\d+)?)\s*€\s*/\s*min(?:ute)?\s+(?:en\s+)?post[- ]charge", text)
    if match:
        return {
            "billing": "started_minute" if started_minute_text(text) else "linear_minute",
            "ratePerMinuteEur": num(match.group(1)),
        }
    match = re.search(r"(\d+(?:\.\d+)?)\s*€\s*/\s*h\s+(?:en\s+)?post[- ]charge", text)
    if match:
        return {
            "billing": "started_minute" if started_minute_text(text) else "linear_minute",
            "ratePerMinuteEur": num(match.group(1)) / 60.0,
        }
    return None


def energy_component(rate, started):
    return {"ratePerKwhEur": rate, "billing": "started_kwh" if started else "linear_kwh"}


def parse_formula(raw):
    source = clean(raw)
    text = low(raw)
    kwh = [num(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*€\s*/\s*kwh", text)]
    if not kwh:
        raise ValueError(f"no kWh price: {source}")
    started_kwh = started_kwh_text(text)
    cap = re.search(r"(?:facturation\s+max\s*:\s*|plafond(?:\s+de)?\s*)(\d+(?:\.\d+)?)\s*€", text)
    if cap:
        post = parse_post_charge(text)
        if not post:
            raise ValueError(f"cap family without post charge: {source}")
        return {
            "family": "session_cap",
            "currency": "EUR",
            "energy": energy_component(kwh[0], started_kwh),
            "postCharge": post,
            "sessionCapEur": num(cap.group(1)),
            "raw": source,
        }

    normalized_no_spaces = text.replace(" ", "")
    day_night = "20kwh" in normalized_no_spaces and (
        re.search(r"8h\s*(?:et|-|à|a)\s*20h", text) or re.search(r"08h\s*-\s*20h", text)
    )
    if day_night:
        day_rate, night_rate = kwh[0], kwh[-1]
        fee = None
        for pattern in (
            r"forfait\s+de\s+connexion\s+(?:à|a|de)\s*(\d+(?:\.\d+)?)\s*€",
            r"forfait\s+de\s+connexion\s*(\d+(?:\.\d+)?)\s*€",
            r"forfait\s+de\s*(\d+(?:\.\d+)?)\s*€",
        ):
            match = re.search(pattern, text)
            if match:
                fee = num(match.group(1))
                break
        if fee is None:
            raise ValueError(f"night fee not parsed: {source}")
        day_text = re.split(r"entre\s+20h|20h\s*-\s*08h|20h\s*-\s*8h", text, maxsplit=1)[0]
        return {
            "family": "day_night_included_energy",
            "currency": "EUR",
            "tariffSelection": "connection_start_local_time",
            "day": {
                "start": "08:00",
                "end": "20:00",
                "energy": energy_component(day_rate, started_kwh),
                "postCharge": parse_post_charge(day_text),
            },
            "night": {
                "start": "20:00",
                "end": "08:00",
                "connectionFeeEur": fee,
                "includedEnergyKwh": 20.0,
                "extraEnergy": energy_component(night_rate, started_kwh),
            },
            "raw": source,
        }

    post = parse_post_charge(text)
    if not post:
        raise ValueError(f"simple family without post charge: {source}")
    return {
        "family": "simple_postcharge",
        "currency": "EUR",
        "energy": energy_component(kwh[0], started_kwh),
        "postCharge": post,
        "raw": source,
    }


def connector_configs(station):
    grouped = {}
    for connector in station.get("mapConnectorStats") or []:
        power = num(connector.get("maxPowerInW", 0)) / 1000.0
        if power <= 0:
            continue
        standard = str(connector.get("standard", "")).lower()
        kind = "AC" if standard in ("t2", "type2", "type_2") and power <= 43 else "DC"
        key = (kind, round(power, 3))
        grouped[key] = max(grouped.get(key, 0), int(connector.get("totalConnectorCount") or connector.get("availableConnectorCount") or 0))
    if not grouped:
        for value in station.get("powersKw") or []:
            power = num(value)
            kind = "AC" if power <= 22.5 else "DC"
            grouped[(kind, round(power, 3))] = max(grouped.get((kind, round(power, 3)), 0), 1)
    return [
        {"kind": kind, "powerKw": power, "stalls": max(1, stalls)}
        for (kind, power), stalls in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
    ]


def formula_targets(raw):
    text = low(raw)
    targets = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*kw\s*(ac|dc)", text):
        targets.append((match.group(2).upper(), num(match.group(1))))
    if not targets:
        match = re.search(r"borne\s+(\d+(?:\.\d+)?)\s*kw\b", text)
        if match:
            power = num(match.group(1))
            targets.append(("DC" if power > 22.5 else "AC", power))
    return targets


def applies(config, targets):
    if not targets:
        return True
    return any(config["kind"] == kind and abs(config["powerKw"] - power) <= 2.1 for kind, power in targets)


def representative_rules(exact):
    if exact["family"] == "day_night_included_energy":
        return [
            {
                "scope": "timeWindow", "start": "08:00", "end": "20:00", "billing": "kwh", "currency": "EUR",
                "pricePerKwh": exact["day"]["energy"]["ratePerKwhEur"], "chargePerMinute": 0, "connectionFee": 0,
                "idlePerMinute": 0, "afterMinutesRate": 0, "afterMinutesThreshold": 0, "afterMinutesCap": 0,
            },
            {
                "scope": "timeWindow", "start": "20:00", "end": "08:00", "billing": "kwh", "currency": "EUR",
                "pricePerKwh": 0, "chargePerMinute": 0, "connectionFee": exact["night"]["connectionFeeEur"],
                "idlePerMinute": 0, "afterMinutesRate": 0, "afterMinutesThreshold": 0, "afterMinutesCap": 0,
            },
        ]
    return [{
        "scope": "allDay", "start": "00:00", "end": "24:00", "billing": "kwh", "currency": "EUR",
        "pricePerKwh": exact["energy"]["ratePerKwhEur"], "chargePerMinute": 0, "connectionFee": 0,
        "idlePerMinute": 0, "afterMinutesRate": 0, "afterMinutesThreshold": 0, "afterMinutesCap": 0,
    }]


def main():
    src = json.loads(SRC.read_text())
    meta = src.get("metadata", {})
    assert meta.get("officialStations") == 155
    assert meta.get("resolvedStations") == 155
    assert meta.get("stationsDirectPricePublished") == 146
    assert meta.get("stationsDirectPriceNotPublished") == 9
    assert meta.get("distinctDirectRawTariffs") == 18

    row_out = []
    excluded = []
    family_rows = Counter()
    formula_count = 0

    for station in src.get("stations", []):
        coords = station.get("coordinatesOfficial")
        if isinstance(coords, str):
            coords = json.loads(coords or "[null,null]")
        lat, lon = ((coords or []) + [None, None])[:2] if isinstance(coords, list) else (None, None)
        configs = connector_configs(station)
        formulas = []
        for raw in station.get("directRawPricing") or []:
            exact = parse_formula(raw)
            formulas.append((exact, formula_targets(raw)))
            family_rows[exact["family"]] += 1
            formula_count += 1

        output_configs = []
        for config in configs:
            matches = [exact for exact, targets in formulas if applies(config, targets)]
            unique = {json.dumps(value, sort_keys=True, ensure_ascii=False): value for value in matches}
            if len(unique) > 1:
                excluded.append({
                    "stationId": station.get("officialStationId"), "kind": config["kind"], "powerKw": config["powerKw"],
                    "reason": "ambiguous_formula", "formulas": [value["raw"] for value in unique.values()],
                })
                continue
            if not unique:
                continue
            exact = next(iter(unique.values()))
            output_configs.append({
                "id": f"izivia-direct:{config['kind']}:{str(config['powerKw']).replace('.', '_')}",
                "label": f"IZIVIA direct · {config['kind']} {config['powerKw']:g} kW",
                "kind": config["kind"], "powerKw": config["powerKw"], "stalls": config["stalls"],
                "offerProvider": "IZIVIA direct", "offerType": "operator_direct",
                "iziviaDirect": True, "iziviaStrictExact": True,
                "pricing": {"type": "rules", "rules": representative_rules(exact), "iziviaExact": exact},
            })

        row_out.append({
            "stationId": station.get("officialStationId"), "mapLocationId": station.get("mapLocationId"),
            "name": station.get("name"), "address": station.get("address"), "latitude": lat, "longitude": lon,
            "directPricePublished": bool(station.get("directPricePublished")),
            "officialStationIds": [station.get("officialStationId")], "configurations": output_configs,
            "rawPricing": station.get("directRawPricing") or [],
        })

    merged = {}
    for station in row_out:
        key = station.get("mapLocationId") or station.get("stationId")
        if key not in merged:
            merged[key] = station
            continue
        current = merged[key]
        current["officialStationIds"] = sorted(set(current["officialStationIds"] + station["officialStationIds"]))
        current["directPricePublished"] = current["directPricePublished"] or station["directPricePublished"]
        by_key = {
            (cfg["kind"], round(cfg["powerKw"], 3), json.dumps(cfg["pricing"]["iziviaExact"], sort_keys=True, ensure_ascii=False)): cfg
            for cfg in current["configurations"]
        }
        for cfg in station["configurations"]:
            config_key = (cfg["kind"], round(cfg["powerKw"], 3), json.dumps(cfg["pricing"]["iziviaExact"], sort_keys=True, ensure_ascii=False))
            if config_key not in by_key:
                by_key[config_key] = cfg
            else:
                by_key[config_key]["stalls"] = max(by_key[config_key]["stalls"], cfg["stalls"])
        current["configurations"] = list(by_key.values())
        current["rawPricing"] = sorted(set(current["rawPricing"] + station["rawPricing"]))

    stations = sorted(merged.values(), key=lambda value: (str(value.get("name") or ""), str(value.get("stationId") or "")))
    direct_rows = sum(1 for station in row_out if station["directPricePublished"])
    no_price_rows = sum(1 for station in row_out if not station["directPricePublished"])
    exact_configs = sum(len(station["configurations"]) for station in stations)
    priced_locations = sum(1 for station in stations if station["configurations"])

    counts = {
        "officialStationRows": len(row_out), "tccLocations": len(stations),
        "directPricePublishedRows": direct_rows, "directPriceNotPublishedRows": no_price_rows,
        "pricedTccLocations": priced_locations, "exactConfigurations": exact_configs,
        "excludedAmbiguousConfigurations": len(excluded), "distinctRawTariffs": meta.get("distinctDirectRawTariffs"),
        "formulaRows": formula_count, "familyFormulaRows": dict(family_rows),
    }
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    if excluded:
        print("EXCLUDED", json.dumps(excluded[:20], ensure_ascii=False, indent=2))

    assert len(row_out) == 155 and direct_rows == 146 and no_price_rows == 9
    assert family_rows == Counter({"session_cap": 75, "day_night_included_energy": 68, "simple_postcharge": 3})
    assert not excluded, excluded[:5]
    assert exact_configs > 0 and priced_locations > 0

    output = {
        "dataset": "izivia-express-direct-tcc-v8-france", "schemaVersion": "1.0.0",
        "sourceGeneratedAt": meta.get("generatedAt"),
        "scope": {
            "countryCode": "FR", "onlyDirectCpo": True, "roamingIncluded": False,
            "subscriptionDiscountsIncluded": False, "failClosed": True, "pricingSemantics": "exact_custom_runtime",
        },
        "counts": counts, "aliasMappings": meta.get("aliasMappings") or {}, "excluded": excluded, "stations": stations,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
