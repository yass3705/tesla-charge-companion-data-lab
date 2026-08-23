#!/usr/bin/env python3
"""Build a strict E55C-operated France station base for Tesla Charge Companion.

The official E55C static IRVE resource is the only station-inventory source.
Rows are retained only when ``nom_operateur`` identifies Electric 55 Charging;
the dataset publisher, amenageur or commercial brand is never used as a proxy.
Dynamic status is deliberately excluded because TCC resolves it through Electra
or Electroverse.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DATASET_API = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "caracteristiques-des-points-de-charge-pour-vehicules-electriques-"
    "electric-55-charging-e55c-ouverts-au-public/"
)
STATIC_SCHEMA = "etalab/schema-irve-statique"
CANONICAL_OPERATOR = "Electric 55 Charging (E55C)"
UA = "Tesla-Charge-Companion-E55C-Builder/1.0 (+public-data-only)"

OPERATOR_PATTERNS = (
    re.compile(r"^electric\s*55\s*charging(?:\s*\(\s*e55c\s*\))?(?:\s+(?:sas|sasu))?$"),
    re.compile(r"^electric\s*55(?:\s*\(\s*e55c\s*\))?(?:\s+(?:sas|sasu))?$"),
    re.compile(r"^e55c(?:\s+(?:sas|sasu))?$"),
)

CONNECTOR_FIELDS = (
    ("prise_type_ef", "EF"),
    ("prise_type_2", "TYPE_2"),
    ("prise_type_combo_ccs", "CCS"),
    ("prise_type_chademo", "CHADEMO"),
    ("prise_type_autre", "OTHER"),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "'").lower()
    return re.sub(r"\s+", " ", text).strip()


def canonical_key(value: Any) -> str:
    text = normalize_text(value)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def is_e55c_operator(value: Any) -> bool:
    candidate = normalize_text(value)
    return any(pattern.fullmatch(candidate) for pattern in OPERATOR_PATTERNS)


def parse_bool(value: Any) -> bool | None:
    text = normalize_text(value)
    if text in {"true", "1", "oui", "yes", "vrai"}:
        return True
    if text in {"false", "0", "non", "no", "faux"}:
        return False
    return None


def parse_number(value: Any) -> float | None:
    text = clean(value).replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return number if number == number else None


def parse_coordinates(value: Any) -> tuple[float, float] | None:
    """Return latitude, longitude from the IRVE [longitude, latitude] field."""
    text = clean(value)
    if not text:
        return None
    try:
        parsed = json.loads(text)
        values = parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        values = re.findall(r"-?\d+(?:[.,]\d+)?", text)
    if len(values) < 2:
        return None
    try:
        lon = float(str(values[0]).replace(",", "."))
        lat = float(str(values[1]).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 7), round(lon, 7)


def normalized_identifier(primary: Any, local: Any, *, prefix: str, seed: str) -> str:
    for value in (primary, local):
        candidate = clean(value)
        if candidate and normalize_text(candidate) not in {"non concerne", "n/a", "na"}:
            return candidate
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18].upper()
    return f"{prefix}-{digest}"


def station_postal_city(address: str) -> tuple[str | None, str | None]:
    matches = list(re.finditer(r"\b(\d{5})\b", address))
    if not matches:
        return None, None
    match = matches[-1]
    city = clean(address[match.end() :].strip(" ,-")) or None
    return match.group(1), city


def _time(value: str, minutes: str | None) -> str:
    hour = min(23, max(0, int(value)))
    minute = min(59, max(0, int(minutes or 0)))
    return f"{hour:02d}:{minute:02d}"


def parse_tariff(text: Any, free: bool | None) -> dict[str, Any]:
    """Parse only unambiguous official tariff text; preserve everything else."""
    raw = clean(text)
    if free is True:
        return {
            "status": "parsed_free",
            "raw": raw or None,
            "rules": [{
                "scope": "allDay",
                "start": "00:00",
                "end": "24:00",
                "billing": "kwh",
                "currency": "EUR",
                "energyEurPerKwh": 0.0,
                "timeEurPerMinute": 0.0,
                "flatEur": 0.0,
            }],
        }
    if not raw:
        return {"status": "missing", "raw": None, "rules": []}

    normalized = normalize_text(raw).replace(",", ".")
    price_re = re.compile(
        r"(?P<amount>\d+(?:\.\d+)?)\s*(?:€|eur)\s*"
        r"(?:/|par\s+|la\s+|le\s+)?\s*"
        r"(?P<unit>kwh|kw/h|minute|min|session|charge)\b"
    )
    range_re = re.compile(
        r"(?P<sh>\d{1,2})(?:\s*(?:h|:)\s*(?P<sm>\d{2})?)?\s*"
        r"(?:-|a|au|et)\s*"
        r"(?P<eh>\d{1,2})(?:\s*(?:h|:)\s*(?P<em>\d{2})?)?"
    )
    prices = [
        {
            "amount": float(m.group("amount")),
            "unit": m.group("unit"),
            "position": m.start(),
        }
        for m in price_re.finditer(normalized)
    ]
    ranges = [
        {
            "start": _time(m.group("sh"), m.group("sm")),
            "end": _time(m.group("eh"), m.group("em")),
            "position": m.start(),
        }
        for m in range_re.finditer(normalized)
    ]
    if not prices:
        return {"status": "descriptive_only", "raw": raw, "rules": []}
    if re.search(r"\b(apres|au dela|a partir de|plafond|minimum|forfait)\b", normalized):
        return {"status": "descriptive_only", "raw": raw, "rules": []}

    def component(rule: dict[str, Any], price: dict[str, Any]) -> bool:
        unit = price["unit"]
        amount = round(float(price["amount"]), 6)
        if unit in {"kwh", "kw/h"}:
            rule["energyEurPerKwh"] = amount
        elif unit in {"minute", "min"}:
            rule["timeEurPerMinute"] = amount
        elif unit in {"session", "charge"}:
            rule["flatEur"] = amount
        else:
            return False
        return True

    base = {
        "scope": "allDay",
        "start": "00:00",
        "end": "24:00",
        "billing": "mixed",
        "currency": "EUR",
        "energyEurPerKwh": 0.0,
        "timeEurPerMinute": 0.0,
        "flatEur": 0.0,
    }
    rules: list[dict[str, Any]] = []
    if not ranges:
        units = [p["unit"] for p in prices]
        canonical_units = ["energy" if u in {"kwh", "kw/h"} else "time" if u in {"minute", "min"} else "flat" for u in units]
        if len(canonical_units) != len(set(canonical_units)):
            return {"status": "descriptive_only", "raw": raw, "rules": []}
        rule = dict(base)
        if not all(component(rule, price) for price in prices):
            return {"status": "descriptive_only", "raw": raw, "rules": []}
        rules = [rule]
    elif len(ranges) == len(prices):
        for price, timerange in zip(prices, ranges):
            rule = dict(base)
            rule.update(scope="timeWindow", start=timerange["start"], end=timerange["end"])
            if not component(rule, price):
                return {"status": "descriptive_only", "raw": raw, "rules": []}
            rules.append(rule)
    else:
        return {"status": "descriptive_only", "raw": raw, "rules": []}

    for rule in rules:
        active = [
            key
            for key in ("energyEurPerKwh", "timeEurPerMinute", "flatEur")
            if rule[key] != 0
        ]
        rule["billing"] = (
            "kwh" if active == ["energyEurPerKwh"]
            else "minute" if active == ["timeEurPerMinute"]
            else "session" if active == ["flatEur"]
            else "mixed"
        )
    return {"status": "parsed_official_station_text", "raw": raw, "rules": rules}


def fetch_bytes(url: str, accept: str = "*/*") -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": accept, "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.geturl()


def load_metadata(url: str) -> dict[str, Any]:
    raw, _ = fetch_bytes(url, "application/json")
    payload = json.loads(raw.decode("utf-8"))
    organization = normalize_text((payload.get("organization") or {}).get("name"))
    if organization != "electric 55 charging":
        raise RuntimeError("data.gouv dataset is not owned by Electric 55 Charging")
    return payload


def select_static_resource(metadata: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        resource
        for resource in metadata.get("resources") or []
        if (resource.get("schema") or {}).get("name") == STATIC_SCHEMA
        and normalize_text(resource.get("format")) == "csv"
    ]
    if not candidates:
        raise RuntimeError("no official E55C static IRVE CSV resource found")
    candidates.sort(
        key=lambda resource: clean(resource.get("last_modified") or resource.get("modified") or ""),
        reverse=True,
    )
    return candidates[0]


def decode_csv(raw: bytes) -> tuple[list[dict[str, str]], list[str]]:
    decoded = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise RuntimeError("unable to decode official E55C CSV")
    sample = decoded[:10000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(decoded), dialect=dialect)
    if not reader.fieldnames:
        raise RuntimeError("official E55C CSV has no header")
    fields = [canonical_key(field) for field in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for source in reader:
        row = {canonical_key(key): clean(value) for key, value in source.items() if key is not None}
        if any(row.values()):
            rows.append(row)
    return rows, fields


def read_input_csv(path: Path) -> bytes:
    return path.read_bytes()


def _connector_kind(connectors: list[str], power: float | None) -> str:
    ac = any(item in {"EF", "TYPE_2"} for item in connectors)
    dc = any(item in {"CCS", "CHADEMO"} for item in connectors)
    if ac and dc:
        return "MIXED"
    if dc:
        return "DC"
    if ac:
        return "AC"
    return "DC" if (power or 0) > 43 else "AC"


def _offer_signature(point: dict[str, Any]) -> str:
    relevant = {
        "kind": point["kind"],
        "powerKw": point["powerKw"],
        "payment": point["payment"],
        "pricing": point["pricing"],
    }
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def offers_for_station(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        groups[_offer_signature(point)].append(point)
    offers: list[dict[str, Any]] = []
    for signature, members in sorted(groups.items(), key=lambda item: item[0]):
        first = members[0]
        digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:14]
        direct_available = first["payment"]["adHoc"] is True
        price_status = first["pricing"]["status"]
        offers.append({
            "offerId": f"e55c-direct-{digest}",
            "source": "e55c_official_irve_static",
            "provider": "E55C direct",
            "operator": CANONICAL_OPERATOR,
            "accessProfile": "ad_hoc" if direct_available else "direct_access_not_confirmed_in_irve_row",
            "kind": first["kind"],
            "powerKw": first["powerKw"],
            "stalls": len(members),
            "evseIds": sorted(member["evseId"] for member in members),
            "priceStatus": price_status,
            "pricingRules": first["pricing"]["rules"],
            "tariffText": first["pricing"]["raw"],
        })
    return offers


def build(rows: Iterable[dict[str, str]], *, source: dict[str, Any]) -> dict[str, Any]:
    source_rows = list(rows)
    operator_counts = Counter(clean(row.get("nom_operateur")) or "<blank>" for row in source_rows)
    matched = [row for row in source_rows if is_e55c_operator(row.get("nom_operateur"))]
    if not matched:
        raise RuntimeError(
            "strict CPO filter matched no row; observed nom_operateur values: "
            + ", ".join(f"{name} ({count})" for name, count in operator_counts.most_common(8))
        )

    grouped: dict[str, dict[str, Any]] = {}
    invalid_coordinates = 0
    duplicate_evse_rows = 0
    accepted_labels: set[str] = set()
    for row in matched:
        coordinates = parse_coordinates(row.get("coordonneesxy"))
        if coordinates is None:
            invalid_coordinates += 1
            continue
        lat, lon = coordinates
        accepted_labels.add(clean(row.get("nom_operateur")))
        address = clean(row.get("adresse_station"))
        name = clean(row.get("nom_station"))
        station_seed = "|".join((name, address, str(lat), str(lon)))
        station_id = normalized_identifier(
            row.get("id_station_itinerance"),
            row.get("id_station_local"),
            prefix="E55C-P",
            seed=station_seed,
        )
        evse_seed = station_seed + "|" + clean(row.get("id_pdc_local")) + "|" + clean(row.get("puissance_nominale"))
        evse_id = normalized_identifier(
            row.get("id_pdc_itinerance"),
            row.get("id_pdc_local"),
            prefix="E55C-E",
            seed=evse_seed,
        )
        power = parse_number(row.get("puissance_nominale"))
        if power is not None:
            power = round(power / 1000, 3) if power > 1000 else round(power, 3)
        connectors = [label for field, label in CONNECTOR_FIELDS if parse_bool(row.get(field)) is True]
        free = parse_bool(row.get("gratuit"))
        point = {
            "evseId": evse_id,
            "localEvseId": clean(row.get("id_pdc_local")) or None,
            "powerKw": power,
            "kind": _connector_kind(connectors, power),
            "connectors": connectors,
            "cableT2Attached": parse_bool(row.get("cable_t2_attache")),
            "payment": {
                "free": free,
                "adHoc": parse_bool(row.get("paiement_acte")),
                "bankCardTerminal": parse_bool(row.get("paiement_cb")),
                "other": parse_bool(row.get("paiement_autre")),
            },
            "pricing": parse_tariff(row.get("tarification"), free),
            "reservation": parse_bool(row.get("reservation")),
            "commissionedAt": clean(row.get("date_mise_en_service")) or None,
            "updatedAt": clean(row.get("date_maj")) or None,
            "observations": clean(row.get("observations")) or None,
        }
        if station_id not in grouped:
            postal, city = station_postal_city(address)
            grouped[station_id] = {
                "stationId": station_id,
                "localStationId": clean(row.get("id_station_local")) or None,
                "name": name or f"Station E55C {station_id}",
                "address": address,
                "postalCode": postal,
                "city": city,
                "inseeCode": clean(row.get("code_insee_commune")) or None,
                "coordinates": {"latitude": lat, "longitude": lon},
                "operator": CANONICAL_OPERATOR,
                "operatorSourceValue": clean(row.get("nom_operateur")),
                "brand": clean(row.get("nom_enseigne")) or None,
                "owner": clean(row.get("nom_amenageur")) or None,
                "siteType": clean(row.get("implantation_station")) or None,
                "declaredChargePointCount": int(parse_number(row.get("nbre_pdc")) or 0),
                "access": {
                    "condition": clean(row.get("condition_acces")) or None,
                    "hours": clean(row.get("horaires")) or None,
                    "pmr": clean(row.get("accessibilite_pmr")) or None,
                    "vehicleSizeRestriction": clean(row.get("restriction_gabarit")) or None,
                    "twoWheelOnly": parse_bool(row.get("station_deux_roues")),
                },
                "chargePointsById": {},
            }
        bucket = grouped[station_id]["chargePointsById"]
        previous = bucket.get(evse_id)
        if previous is not None:
            duplicate_evse_rows += 1
            previous_date = clean(previous.get("updatedAt"))
            current_date = clean(point.get("updatedAt"))
            if current_date < previous_date:
                continue
        bucket[evse_id] = point

    stations: list[dict[str, Any]] = []
    for station_id in sorted(grouped):
        raw_station = grouped[station_id]
        points = [raw_station["chargePointsById"][key] for key in sorted(raw_station["chargePointsById"])]
        if not points:
            continue
        station = {key: value for key, value in raw_station.items() if key != "chargePointsById"}
        station["chargePointCount"] = len(points)
        station["maxPowerKw"] = max((p["powerKw"] or 0 for p in points), default=0) or None
        station["connectorTypes"] = sorted({connector for point in points for connector in point["connectors"]})
        station["chargePoints"] = points
        station["offers"] = offers_for_station(points)
        stations.append(station)

    if not stations:
        raise RuntimeError("strict E55C filter produced no station with valid coordinates")
    charge_points = [point for station in stations for point in station["chargePoints"]]
    parsed_points = [point for point in charge_points if point["pricing"]["rules"]]
    parsed_station_count = sum(
        1 for station in stations if any(point["pricing"]["rules"] for point in station["chargePoints"])
    )
    generated_at = clean(source.get("lastModified")) or now_iso()
    return {
        "schemaVersion": "1.0.0",
        "dataset": "electric55-operated-stations-france",
        "generatedAt": generated_at,
        "country": "FR",
        "operator": CANONICAL_OPERATOR,
        "scope": {
            "stationInventory": "only rows whose nom_operateur strictly identifies E55C",
            "operatorFieldAuthority": "etalab/schema-irve-statique nom_operateur",
            "thirdPartySupervisedStationsWithoutE55CAsOperatorExcluded": True,
            "dynamicStatusIncluded": False,
            "dynamicStatusAuthorityForTcc": ["Electroverse", "Electra"],
            "roamingTariffsIncluded": False,
        },
        "source": source,
        "filterEvidence": {
            "field": "nom_operateur",
            "acceptedSourceValues": sorted(accepted_labels),
            "publisherAloneNeverQualifiesARow": True,
            "amenageurAloneNeverQualifiesARow": True,
            "brandAloneNeverQualifiesARow": True,
        },
        "stats": {
            "sourceRowCount": len(source_rows),
            "matchedE55cOperatorRows": len(matched),
            "excludedNonE55cOperatorRows": len(source_rows) - len(matched),
            "excludedInvalidCoordinateRows": invalid_coordinates,
            "deduplicatedEvseRows": duplicate_evse_rows,
            "stationCount": len(stations),
            "chargePointCount": len(charge_points),
            "stationCountWithMachineReadablePricing": parsed_station_count,
            "chargePointCountWithMachineReadablePricing": len(parsed_points),
            "chargePointCountWithAdHocPayment": sum(1 for p in charge_points if p["payment"]["adHoc"] is True),
            "chargePointCountWithTariffText": sum(1 for p in charge_points if p["pricing"]["raw"]),
        },
        "tccIntegration": {
            "staticInventoryReady": True,
            "stationAndEvseIdentifiersPreservedForStatusJoin": True,
            "offersAreOperatorDirectOnly": True,
            "unparsedTariffsMustRemainUnranked": True,
            "statusMustBeJoinedExternally": True,
        },
        "stations": stations,
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def summary(payload: dict[str, Any]) -> str:
    stats = payload["stats"]
    return (
        "# Base nationale E55C pour TCC\n\n"
        f"- Stations E55C publiées : **{stats['stationCount']}**\n"
        f"- Points de charge uniques : **{stats['chargePointCount']}**\n"
        f"- Lignes source hors CPO E55C exclues : **{stats['excludedNonE55cOperatorRows']}**\n"
        f"- Points avec tarif officiel interprétable : **{stats['chargePointCountWithMachineReadablePricing']}**\n"
        f"- Points avec texte tarifaire officiel : **{stats['chargePointCountWithTariffText']}**\n"
        "- Statuts dynamiques : **non inclus** (jointure TCC via Electroverse/Electra).\n"
        "- Itinérance/eMSP : **non incluse**.\n"
        f"- Empreinte source : `{payload['source']['sha256']}`\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-url", default=DATASET_API)
    parser.add_argument("--input-csv", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/national/electric55_stations_france.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/electric55/station_base_summary.md"))
    parser.add_argument("--min-stations", type=int, default=1)
    args = parser.parse_args()

    if args.input_csv:
        csv_bytes = read_input_csv(args.input_csv)
        resource = {
            "id": "local-test",
            "url": str(args.input_csv),
            "last_modified": now_iso(),
            "schema": {"name": STATIC_SCHEMA},
        }
        final_url = str(args.input_csv)
        dataset_last_update = None
    else:
        metadata = load_metadata(args.metadata_url)
        resource = select_static_resource(metadata)
        resource_url = clean(resource.get("url"))
        if not resource_url:
            raise RuntimeError("official E55C static resource has no URL")
        csv_bytes, final_url = fetch_bytes(resource_url, "text/csv,application/csv,*/*;q=0.8")
        dataset_last_update = metadata.get("last_update")

    rows, fields = decode_csv(csv_bytes)
    required = {"nom_operateur", "id_station_itinerance", "id_pdc_itinerance", "coordonneesxy"}
    missing = sorted(required - set(fields))
    if missing:
        raise RuntimeError("official E55C CSV missing required fields: " + ", ".join(missing))
    source = {
        "datasetApi": args.metadata_url if not args.input_csv else None,
        "resourceId": resource.get("id"),
        "resourceUrl": clean(resource.get("url")) or final_url,
        "resolvedResourceUrl": final_url,
        "schema": STATIC_SCHEMA,
        "schemaVersion": (resource.get("schema") or {}).get("version"),
        "lastModified": resource.get("last_modified") or resource.get("modified") or dataset_last_update,
        "sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "officialPublisher": "Electric 55 Charging",
    }
    payload = build(rows, source=source)
    if payload["stats"]["stationCount"] < args.min_stations:
        raise RuntimeError(
            f"unexpected E55C station count {payload['stats']['stationCount']} < {args.min_stations}"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(payload), encoding="utf-8")
    args.report.write_text(summary(payload), encoding="utf-8")
    print(summary(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
