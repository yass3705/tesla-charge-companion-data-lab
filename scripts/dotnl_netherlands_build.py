#!/usr/bin/env python3
import argparse
import collections
import datetime as dt
import gzip
import json
import math
from pathlib import Path

SERVICE_STATUSES = {"AVAILABLE", "BLOCKED", "CHARGING", "RESERVED"}
BROKEN_STATUSES = {"INOPERATIVE", "OUTOFORDER"}
EXCLUDED_EVSE_STATUSES = {"PLANNED", "REMOVED"}


def read_gzip_json(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig") as handle:
        return json.load(handle)


def as_float(value):
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def gross_component(component):
    price = as_float(component.get("price"))
    vat = as_float(component.get("vat"))
    if price is None:
        return None
    return price * (1.0 + (vat or 0.0) / 100.0)


def gross_price_object(value):
    if not isinstance(value, dict):
        return None
    incl = as_float(value.get("incl_vat"))
    if incl is not None:
        return incl
    return as_float(value.get("excl_vat"))


def normalize_tariff(tariff):
    elements = []
    for element in tariff.get("elements") or []:
        if not isinstance(element, dict):
            continue
        components = []
        for component in element.get("price_components") or []:
            if not isinstance(component, dict):
                continue
            typ = str(component.get("type") or "").upper()
            net = as_float(component.get("price"))
            gross = gross_component(component)
            components.append(
                {
                    "type": typ,
                    "priceExVat": net,
                    "vatPct": as_float(component.get("vat")),
                    "priceInclVat": None if gross is None else round(gross, 6),
                    "stepSize": component.get("step_size"),
                }
            )
        elements.append(
            {
                "priceComponents": components,
                "restrictions": element.get("restrictions"),
            }
        )
    return {
        "id": str(tariff.get("id") or ""),
        "type": tariff.get("type"),
        "currency": tariff.get("currency") or "EUR",
        "startDateTime": tariff.get("start_date_time"),
        "endDateTime": tariff.get("end_date_time"),
        "minPriceInclVat": gross_price_object(tariff.get("min_price")),
        "maxPriceInclVat": gross_price_object(tariff.get("max_price")),
        "altText": tariff.get("tariff_alt_text"),
        "altUrl": tariff.get("tariff_alt_url"),
        "elements": elements,
        "lastUpdated": tariff.get("last_updated"),
    }


def derive_power_kw(connector):
    explicit = as_float(connector.get("max_electric_power"))
    if explicit is not None and explicit > 0:
        return round(explicit / 1000.0, 3), "max_electric_power"

    voltage = as_float(connector.get("max_voltage"))
    amperage = as_float(connector.get("max_amperage"))
    if voltage is None or amperage is None or voltage <= 0 or amperage <= 0:
        return None, "missing"

    power_type = str(connector.get("power_type") or "").upper()
    phases = {
        "AC_1_PHASE": 1,
        "AC_2_PHASE": 2,
        "AC_2_PHASE_SPLIT": 2,
        "AC_3_PHASE": 3,
        "DC": 1,
    }.get(power_type, 1)
    return round(voltage * amperage * phases / 1000.0, 3), "voltage_amperage"


def station_service_status(statuses):
    s = {str(x).upper() for x in statuses}
    if s & SERVICE_STATUSES:
        return "IN_SERVICE"
    if s and s <= BROKEN_STATUSES:
        return "OUT_OF_SERVICE"
    if s & BROKEN_STATUSES and not (s & SERVICE_STATUSES):
        return "OUT_OF_SERVICE"
    return "UNKNOWN"


def normalize_location(location, tariff_index, metrics):
    party = str(location.get("party_id") or "").upper()
    location_id = str(location.get("id") or "")
    coords = location.get("coordinates") or {}
    lat = as_float(coords.get("latitude"))
    lon = as_float(coords.get("longitude"))
    if lat is None or lon is None:
        metrics["skippedMissingCoordinates"] += 1
        return None

    evses_out = []
    active_statuses = []
    for evse in location.get("evses") or []:
        if not isinstance(evse, dict):
            continue
        status = str(evse.get("status") or "UNKNOWN").upper()
        metrics["evseStatusRaw"][status] += 1
        if status in EXCLUDED_EVSE_STATUSES:
            metrics["evsesExcludedPlannedRemoved"] += 1
            continue

        connectors_out = []
        for connector in evse.get("connectors") or []:
            if not isinstance(connector, dict):
                continue
            power_kw, power_source = derive_power_kw(connector)
            metrics["connectors"] += 1
            metrics["powerSource"][power_source] += 1
            if power_kw is None:
                metrics["connectorsMissingUsablePower"] += 1

            tariff_ids = [str(x) for x in (connector.get("tariff_ids") or [])]
            resolved_tariffs = []
            unresolved = []
            for tariff_id in tariff_ids:
                tariff = tariff_index.get((party, tariff_id))
                if tariff is None:
                    unresolved.append(tariff_id)
                    metrics["unresolvedTariffLinksByParty"][party] += 1
                else:
                    resolved_tariffs.append(tariff)

            if tariff_ids:
                metrics["connectorsWithTariffIds"] += 1
            if resolved_tariffs:
                metrics["connectorsWithResolvedTariff"] += 1
                if any(str(t.get("type") or "").upper() == "AD_HOC_PAYMENT" for t in resolved_tariffs):
                    metrics["connectorsWithAdHocTariff"] += 1
                elif any(str(t.get("type") or "").upper() in ("REGULAR", "") for t in resolved_tariffs):
                    metrics["connectorsWithRegularOrUntypedTariff"] += 1

            connectors_out.append(
                {
                    "id": str(connector.get("id") or ""),
                    "standard": connector.get("standard"),
                    "format": connector.get("format"),
                    "powerType": connector.get("power_type"),
                    "maxVoltage": connector.get("max_voltage"),
                    "maxAmperage": connector.get("max_amperage"),
                    "powerKw": power_kw,
                    "powerSource": power_source,
                    "tariffIds": tariff_ids,
                    "tariffs": resolved_tariffs,
                    "unresolvedTariffIds": unresolved,
                    "termsAndConditions": connector.get("terms_and_conditions"),
                    "lastUpdated": connector.get("last_updated"),
                }
            )

        if not connectors_out:
            continue
        active_statuses.append(status)
        metrics["evses"] += 1
        evses_out.append(
            {
                "uid": str(evse.get("uid") or ""),
                "evseId": evse.get("evse_id"),
                "status": status,
                "capabilities": evse.get("capabilities") or [],
                "parkingRestrictions": evse.get("parking_restrictions") or [],
                "floorLevel": evse.get("floor_level"),
                "physicalReference": evse.get("physical_reference"),
                "connectors": connectors_out,
                "lastUpdated": evse.get("last_updated"),
            }
        )

    if not evses_out:
        metrics["locationsExcludedNoActiveEvse"] += 1
        return None

    operator = location.get("operator") if isinstance(location.get("operator"), dict) else {}
    metrics["locationsByPartyId"][party] += 1
    return {
        "stationId": f"NL:{party}:{location_id}",
        "countryCode": "NL",
        "partyId": party,
        "locationId": location_id,
        "name": location.get("name"),
        "operatorName": operator.get("name"),
        "address": location.get("address"),
        "city": location.get("city"),
        "postalCode": location.get("postal_code"),
        "country": location.get("country"),
        "coordinates": {"latitude": lat, "longitude": lon},
        "parkingType": location.get("parking_type"),
        "openingTimes": location.get("opening_times"),
        "timeZone": location.get("time_zone"),
        "facilities": location.get("facilities") or [],
        "energyMix": location.get("energy_mix"),
        "serviceStatus": station_service_status(active_statuses),
        "evses": evses_out,
        "lastUpdated": location.get("last_updated"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("locations_gz", type=Path)
    parser.add_argument("tariffs_gz", type=Path)
    parser.add_argument("output_gz", type=Path)
    parser.add_argument("report_json", type=Path)
    args = parser.parse_args()

    locations = read_gzip_json(args.locations_gz)
    tariffs = read_gzip_json(args.tariffs_gz)
    if not isinstance(locations, list) or not isinstance(tariffs, list):
        raise SystemExit("DOT-NL snapshots must have JSON-array roots")

    nl_tariffs = [
        t
        for t in tariffs
        if isinstance(t, dict)
        and str(t.get("country_code") or "").upper() == "NL"
        and str(t.get("party_id") or "").upper() != "TSL"
    ]
    tariff_index = {}
    duplicate_tariffs = 0
    for tariff in nl_tariffs:
        key = (str(tariff.get("party_id") or "").upper(), str(tariff.get("id") or ""))
        normalized = normalize_tariff(tariff)
        old = tariff_index.get(key)
        if old is not None:
            duplicate_tariffs += 1
            if str(normalized.get("lastUpdated") or "") <= str(old.get("lastUpdated") or ""):
                continue
        tariff_index[key] = normalized

    metrics = {
        "rawLocations": len(locations),
        "rawTariffs": len(tariffs),
        "nlNonTeslaInputLocations": 0,
        "skippedCountry": 0,
        "skippedTesla": 0,
        "skippedPublishFalse": 0,
        "skippedMissingCoordinates": 0,
        "locationsExcludedNoActiveEvse": 0,
        "evsesExcludedPlannedRemoved": 0,
        "evses": 0,
        "connectors": 0,
        "connectorsMissingUsablePower": 0,
        "connectorsWithTariffIds": 0,
        "connectorsWithResolvedTariff": 0,
        "connectorsWithAdHocTariff": 0,
        "connectorsWithRegularOrUntypedTariff": 0,
        "evseStatusRaw": collections.Counter(),
        "powerSource": collections.Counter(),
        "locationsByPartyId": collections.Counter(),
        "unresolvedTariffLinksByParty": collections.Counter(),
    }

    best_location = {}
    duplicate_locations = 0
    for location in locations:
        if not isinstance(location, dict):
            continue
        cc = str(location.get("country_code") or "").upper()
        party = str(location.get("party_id") or "").upper()
        if cc != "NL":
            metrics["skippedCountry"] += 1
            continue
        if party == "TSL":
            metrics["skippedTesla"] += 1
            continue
        if location.get("publish") is False:
            metrics["skippedPublishFalse"] += 1
            continue
        metrics["nlNonTeslaInputLocations"] += 1
        key = (party, str(location.get("id") or ""))
        old = best_location.get(key)
        if old is not None:
            duplicate_locations += 1
            if str(location.get("last_updated") or "") <= str(old.get("last_updated") or ""):
                continue
        best_location[key] = location

    stations = []
    for key in sorted(best_location):
        station = normalize_location(best_location[key], tariff_index, metrics)
        if station is not None:
            stations.append(station)

    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    dataset = {
        "schemaVersion": "1.0.0",
        "dataset": "dotnl-netherlands-non-tesla-normalized",
        "generatedAt": generated,
        "scope": {"countryCode": "NL", "teslaExcluded": True, "publicOnly": True},
        "source": {
            "locations": "https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz",
            "tariffs": "https://opendata.ndw.nu/charging_point_tariffs_ocpi.json.gz",
            "format": "OCPI 2.2.1",
        },
        "stations": stations,
    }

    args.output_gz.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dataset, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(args.output_gz, "wb", compresslevel=9, mtime=0) as handle:
        handle.write(payload)

    c = metrics["connectors"]
    report = {
        "dataset": "dotnl-netherlands-build-report",
        "generatedAt": generated,
        "output": str(args.output_gz),
        "outputCompressedBytes": args.output_gz.stat().st_size,
        "outputUncompressedBytes": len(payload),
        "stationCount": len(stations),
        "duplicateLocationKeys": duplicate_locations,
        "duplicateTariffKeys": duplicate_tariffs,
        "tariffObjectCountNlNonTesla": len(tariff_index),
        "metrics": {
            **{k: v for k, v in metrics.items() if not isinstance(v, collections.Counter)},
            "evseStatusRaw": dict(metrics["evseStatusRaw"]),
            "powerSource": dict(metrics["powerSource"]),
            "locationsByPartyId": dict(metrics["locationsByPartyId"]),
            "unresolvedTariffLinksByParty": dict(metrics["unresolvedTariffLinksByParty"].most_common()),
        },
        "coveragePct": {
            "usablePower": round(100.0 * (c - metrics["connectorsMissingUsablePower"]) / c, 3) if c else 0,
            "tariffIds": round(100.0 * metrics["connectorsWithTariffIds"] / c, 3) if c else 0,
            "resolvedTariff": round(100.0 * metrics["connectorsWithResolvedTariff"] / c, 3) if c else 0,
            "adHocTariff": round(100.0 * metrics["connectorsWithAdHocTariff"] / c, 3) if c else 0,
        },
    }
    args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
