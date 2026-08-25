#!/usr/bin/env python3
"""Build the strict Freshmile-direct CPO inventory used by Tesla Charge Companion.

Scope is based on the AFIREV CPO identities assigned directly to Freshmile:
FR*FR0, FR*FR1, FR*FR2, FR*FR3 and FR*FRS. Regional/third-party CPO
identities are excluded even when Freshmile provides backend or eMSP services.

The national IRVE consolidation supplies station/EVSE inventory and declared
``tarification`` text. That text is preserved as a candidate only: Freshmile
states that tariffs are network/site specific, so TCC must not rank a price
until it has been cross-checked against the Freshmile station portal/API.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DATASET_APIS = (
    (
        "pan_beta",
        "https://www.data.gouv.fr/api/1/datasets/"
        "beta-bases-nationales-des-points-de-recharge-pour-vehicules-electriques-en-france-irve/",
    ),
    (
        "datagouv_legacy",
        "https://www.data.gouv.fr/api/1/datasets/"
        "base-nationale-des-irve-data-gouv-infrastructures-de-recharge-pour-vehicules-electriques/",
    ),
)
STATIC_SCHEMA = "etalab/schema-irve-statique"
DIRECT_CPO_IDS = {
    "FRFR0": "Freshmile CPO",
    "FRFR1": "Freshmile",
    "FRFR2": "Freshmile-Advenir",
    "FRFR3": "Freshmile Infrastructure",
    "FRFRS": "Freshmile Semi-public",
}
AFIREV_SOURCE = "https://afirev.fr/en/list-of-assigned-identifiers/"
AFIREV_VERIFIED_AT = "2026-08-25"
FRESHMILE_HELP = "https://www.freshmile.com/aide-contact/"
FRESHMILE_TERMS = "https://www.freshmile.com/cgu-cgv/cgv/"
FRESHMILE_MAP = "https://charge.freshmile.com/map"
DEFAULT_OUTPUT = Path("data/national/freshmile_direct_stations_france.json.gz")
UA = "Tesla-Charge-Companion-Freshmile-Direct/1.0 (+public-data-only)"

CONNECTOR_FIELDS = (
    ("prise_type_ef", "EF"),
    ("prise_type_2", "TYPE_2"),
    ("prise_type_combo_ccs", "CCS"),
    ("prise_type_chademo", "CHADEMO"),
    ("prise_type_autre", "OTHER"),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def canonical_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_text(value)).strip("_")


def parse_bool(value: Any) -> bool | None:
    text = normalize_text(value)
    if text in {"true", "1", "oui", "yes", "vrai"}:
        return True
    if text in {"false", "0", "non", "no", "faux"}:
        return False
    return None


def parse_number(value: Any) -> float | None:
    match = re.search(r"-?\d+(?:[.,]\d+)?", clean(value))
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", "."))
    except ValueError:
        return None
    return number if number == number else None


def parse_coordinates(value: Any) -> tuple[float, float] | None:
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


def cpo_code(identifier: Any) -> str | None:
    compact = re.sub(r"[^A-Z0-9]", "", clean(identifier).upper())
    if len(compact) < 5:
        return None
    prefix = compact[:5]
    return prefix if prefix.startswith("FR") else None


def is_freshmile_operator(value: Any) -> bool:
    text = normalize_text(value)
    return bool(text) and "freshmile" in text


def schema_name(resource: dict[str, Any]) -> str:
    schema = resource.get("schema")
    if isinstance(schema, dict):
        return clean(schema.get("name"))
    return clean(schema)


def fetch_bytes(url: str, accept: str = "*/*") -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": accept, "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), response.geturl()


def load_national_metadata() -> tuple[str, dict[str, Any], str]:
    errors: list[str] = []
    for source_name, url in DATASET_APIS:
        try:
            raw, resolved = fetch_bytes(url, "application/json")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict) or not payload.get("resources"):
                raise RuntimeError("metadata has no resources")
            return source_name, payload, resolved
        except Exception as exc:  # network fallthrough is intentional
            errors.append(f"{source_name}: {exc}")
    raise RuntimeError("unable to load a national IRVE dataset: " + " | ".join(errors))


def select_static_resource(metadata: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for resource in metadata.get("resources") or []:
        if normalize_text(resource.get("format")) != "csv":
            continue
        if schema_name(resource) != STATIC_SCHEMA:
            continue
        title = normalize_text(resource.get("title") or resource.get("name"))
        if "dynam" in title or "documentation" in title:
            continue
        candidates.append(resource)
    if not candidates:
        raise RuntimeError("no etalab/schema-irve-statique CSV found in national dataset")

    def score(resource: dict[str, Any]) -> tuple[int, int, str]:
        title = normalize_text(resource.get("title") or resource.get("name"))
        dedup = 0 if ("non dedoubl" in title or "non-dedoubl" in title) else 1
        preferred = 1 if ("donnees statiques" in title or "derniere version" in title) else 0
        modified = clean(resource.get("last_modified") or resource.get("modified") or "")
        return dedup, preferred, modified

    candidates.sort(key=score, reverse=True)
    selected = candidates[0]
    if score(selected)[0] == 0:
        raise RuntimeError("only non-deduplicated static IRVE resource is available")
    if not clean(selected.get("url")):
        raise RuntimeError("selected national IRVE resource has no URL")
    return selected


def decode_csv(raw: bytes) -> list[dict[str, str]]:
    decoded = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise RuntimeError("unable to decode national IRVE CSV")
    try:
        dialect = csv.Sniffer().sniff(decoded[:10000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(decoded), dialect=dialect)
    if not reader.fieldnames:
        raise RuntimeError("national IRVE CSV has no header")
    rows: list[dict[str, str]] = []
    for source in reader:
        row = {canonical_key(k): clean(v) for k, v in source.items() if k is not None}
        if any(row.values()):
            rows.append(row)
    return rows


def normalized_identifier(primary: Any, local: Any, *, prefix: str, seed: str) -> str:
    for value in (primary, local):
        candidate = clean(value)
        if candidate and normalize_text(candidate) not in {"non concerne", "n/a", "na"}:
            return candidate
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18].upper()
    return f"{prefix}-{digest}"


def tariff_candidate(text: Any, free: bool | None) -> dict[str, Any]:
    raw = clean(text)
    if free is True:
        return {
            "status": "declared_free_requires_portal_crosscheck",
            "raw": raw or None,
            "candidateComponents": {"energyEurPerKwh": 0.0},
            "tccRankable": False,
            "freshmilePortalValidationRequired": True,
        }
    if not raw:
        return {
            "status": "missing",
            "raw": None,
            "candidateComponents": {},
            "tccRankable": False,
            "freshmilePortalValidationRequired": True,
        }
    normalized = normalize_text(raw).replace(",", ".")
    patterns = {
        "energyEurPerKwh": r"(\d+(?:\.\d+)?)\s*(?:€|eur)\s*(?:/|par\s*)?\s*kwh\b",
        "timeEurPerMinute": r"(\d+(?:\.\d+)?)\s*(?:€|eur)\s*(?:/|par\s*)?\s*(?:min|minute)\b",
        "flatEur": r"(\d+(?:\.\d+)?)\s*(?:€|eur)\s*(?:/|par\s*)?\s*(?:session|charge)\b",
    }
    components: dict[str, float] = {}
    ambiguous = False
    for key, pattern in patterns.items():
        values = [float(match) for match in re.findall(pattern, normalized)]
        if len(set(values)) > 1:
            ambiguous = True
        elif values:
            components[key] = round(values[0], 6)
    complex_terms = bool(
        re.search(
            r"\b(apres|au dela|a partir|plafond|minimum|forfait|heure|heures|nuit|jour|"
            r"gratuit pendant|stationnement|occupation|abonne|resident)\b",
            normalized,
        )
    )
    if not components:
        status = "descriptive_only"
    elif ambiguous or complex_terms:
        status = "parsed_candidate_complex"
    else:
        status = "parsed_candidate_simple"
    return {
        "status": status,
        "raw": raw,
        "candidateComponents": components,
        "tccRankable": False,
        "freshmilePortalValidationRequired": True,
    }


def connector_kind(connectors: list[str], power: float | None) -> str:
    ac = any(item in {"EF", "TYPE_2"} for item in connectors)
    dc = any(item in {"CCS", "CHADEMO"} for item in connectors)
    if ac and dc:
        return "MIXED"
    if dc:
        return "DC"
    if ac:
        return "AC"
    return "DC" if (power or 0) > 43 else "AC"


def build(rows: Iterable[dict[str, str]], *, source: dict[str, Any]) -> dict[str, Any]:
    source_rows = list(rows)
    direct_rows: list[tuple[str, dict[str, str]]] = []
    code_counts: Counter[str] = Counter()
    conflicting_operator_rows = 0
    direct_id_with_blank_operator = 0

    for row in source_rows:
        code = cpo_code(row.get("id_pdc_itinerance"))
        if code not in DIRECT_CPO_IDS:
            continue
        operator = clean(row.get("nom_operateur"))
        if operator and not is_freshmile_operator(operator):
            conflicting_operator_rows += 1
            continue
        if not operator:
            direct_id_with_blank_operator += 1
        direct_rows.append((code, row))
        code_counts[code] += 1

    if not direct_rows:
        raise RuntimeError("no row matched the strict Freshmile direct CPO identifiers")

    grouped: dict[str, dict[str, Any]] = {}
    invalid_coordinates = 0
    duplicate_evse_rows = 0

    for code, row in direct_rows:
        coordinates = parse_coordinates(row.get("coordonneesxy"))
        if coordinates is None:
            invalid_coordinates += 1
            continue
        lat, lon = coordinates
        name = clean(row.get("nom_station"))
        address = clean(row.get("adresse_station"))
        station_seed = "|".join((code, name, address, str(lat), str(lon)))
        station_id = normalized_identifier(
            row.get("id_station_itinerance"), row.get("id_station_local"),
            prefix=f"{code}-P", seed=station_seed,
        )
        evse_seed = station_seed + "|" + clean(row.get("id_pdc_local")) + "|" + clean(row.get("puissance_nominale"))
        evse_id = normalized_identifier(
            row.get("id_pdc_itinerance"), row.get("id_pdc_local"),
            prefix=f"{code}-E", seed=evse_seed,
        )
        power = parse_number(row.get("puissance_nominale"))
        if power is not None:
            power = round(power / 1000, 3) if power > 1000 else round(power, 3)
        connectors = [label for field, label in CONNECTOR_FIELDS if parse_bool(row.get(field)) is True]
        free = parse_bool(row.get("gratuit"))
        point = {
            "evseId": evse_id,
            "localEvseId": clean(row.get("id_pdc_local")) or None,
            "cpoCode": code,
            "powerKw": power,
            "kind": connector_kind(connectors, power),
            "connectors": connectors,
            "payment": {
                "free": free,
                "adHoc": parse_bool(row.get("paiement_acte")),
                "bankCardTerminal": parse_bool(row.get("paiement_cb")),
                "other": parse_bool(row.get("paiement_autre")),
            },
            "declaredTariff": tariff_candidate(row.get("tarification"), free),
            "reservation": parse_bool(row.get("reservation")),
            "commissionedAt": clean(row.get("date_mise_en_service")) or None,
            "updatedAt": clean(row.get("date_maj")) or None,
            "observations": clean(row.get("observations")) or None,
        }
        if station_id not in grouped:
            grouped[station_id] = {
                "stationId": station_id,
                "localStationId": clean(row.get("id_station_local")) or None,
                "name": name or f"Station Freshmile {station_id}",
                "address": address,
                "inseeCode": clean(row.get("code_insee_commune")) or None,
                "coordinates": {"latitude": lat, "longitude": lon},
                "operator": "Freshmile",
                "operatorSourceValue": clean(row.get("nom_operateur")) or None,
                "brand": clean(row.get("nom_enseigne")) or None,
                "owner": clean(row.get("nom_amenageur")) or None,
                "siteType": clean(row.get("implantation_station")) or None,
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
            if clean(point.get("updatedAt")) < clean(previous.get("updatedAt")):
                continue
        bucket[evse_id] = point

    stations: list[dict[str, Any]] = []
    for station_id in sorted(grouped):
        raw_station = grouped[station_id]
        points = [raw_station["chargePointsById"][key] for key in sorted(raw_station["chargePointsById"])]
        if not points:
            continue
        station = {key: value for key, value in raw_station.items() if key != "chargePointsById"}
        station["cpoCodes"] = sorted({point["cpoCode"] for point in points})
        station["chargePointCount"] = len(points)
        station["maxPowerKw"] = max((p["powerKw"] or 0 for p in points), default=0) or None
        station["connectorTypes"] = sorted({connector for point in points for connector in point["connectors"]})
        station["chargePoints"] = points
        stations.append(station)

    if not stations:
        raise RuntimeError("Freshmile direct filter produced no station with valid coordinates")

    charge_points = [point for station in stations for point in station["chargePoints"]]
    tariff_text_points = [p for p in charge_points if p["declaredTariff"]["raw"]]
    parsed_candidate_points = [
        p for p in charge_points if p["declaredTariff"]["status"].startswith("parsed_candidate")
    ]
    generated_at = clean(source.get("lastModified")) or now_iso()
    return {
        "schemaVersion": "1.0.0",
        "dataset": "freshmile-direct-cpo-stations-france",
        "generatedAt": generated_at,
        "country": "FR",
        "operator": "Freshmile",
        "scope": {
            "cpoIdentityAuthority": "AFIREV assigned CPO identifiers",
            "directCpoIdentifiers": DIRECT_CPO_IDS,
            "regionalOrThirdPartyCpoIdentifiersIncluded": False,
            "regionalNetworkSubscriptionsIncluded": False,
            "emspRoamingStationsIncluded": False,
            "freshmilePassDiscountAssumed": False,
            "operatorNameConflictPolicy": "exclude row when CPO id is Freshmile but nonblank nom_operateur identifies another operator",
        },
        "sources": {
            "afirev": {"url": AFIREV_SOURCE, "verifiedAt": AFIREV_VERIFIED_AT},
            "freshmileHelp": FRESHMILE_HELP,
            "freshmileCpoTerms": FRESHMILE_TERMS,
            "freshmileStationPortal": FRESHMILE_MAP,
            "nationalIrve": source,
        },
        "tariffPolicy": {
            "singleNationalFreshmileTariff": False,
            "priceGranularity": "network_or_station_specific",
            "nationalIrveTarification": "candidate_only",
            "freshmilePortalCrosscheckRequiredBeforeTccRanking": True,
            "unvalidatedPriceIsRankable": False,
            "regionalSubscriptionsHandledSeparately": True,
        },
        "stats": {
            "sourceRowCount": len(source_rows),
            "matchedDirectCpoRows": len(direct_rows),
            "directRowsByCpoCode": dict(sorted(code_counts.items())),
            "excludedConflictingOperatorRows": conflicting_operator_rows,
            "directIdRowsWithBlankOperatorName": direct_id_with_blank_operator,
            "excludedInvalidCoordinateRows": invalid_coordinates,
            "deduplicatedEvseRows": duplicate_evse_rows,
            "stationCount": len(stations),
            "chargePointCount": len(charge_points),
            "chargePointCountWithDeclaredTariffText": len(tariff_text_points),
            "chargePointCountWithParsedTariffCandidate": len(parsed_candidate_points),
            "chargePointCountRankableBeforeFreshmileValidation": 0,
        },
        "tccIntegration": {
            "staticInventoryReady": True,
            "stationAndEvseIdentifiersPreservedForPortalJoin": True,
            "directTariffLayerReady": False,
            "nextGate": "cross-check EVSE tariffs against Freshmile portal/public API before publishing rankable prices",
        },
        "stations": stations,
    }


def write_gzip_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="Optional local IRVE CSV (tests/offline validation)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.input:
        raw = args.input.read_bytes()
        source = {
            "kind": "local_test_input",
            "url": str(args.input),
            "lastModified": None,
            "schema": STATIC_SCHEMA,
        }
    else:
        source_name, metadata, metadata_url = load_national_metadata()
        resource = select_static_resource(metadata)
        raw, resolved_url = fetch_bytes(clean(resource.get("url")), "text/csv,*/*;q=0.8")
        source = {
            "kind": source_name,
            "datasetId": clean(metadata.get("id")) or None,
            "datasetTitle": clean(metadata.get("title")) or None,
            "metadataUrl": metadata_url,
            "resourceId": clean(resource.get("id")) or None,
            "resourceTitle": clean(resource.get("title") or resource.get("name")) or None,
            "url": resolved_url,
            "lastModified": clean(resource.get("last_modified") or resource.get("modified")) or None,
            "schema": schema_name(resource),
        }

    payload = build(decode_csv(raw), source=source)
    write_gzip_json(args.output, payload)
    print(json.dumps({
        "output": str(args.output),
        "dataset": payload["dataset"],
        "generatedAt": payload["generatedAt"],
        "stats": payload["stats"],
        "directCpoIdentifiers": sorted(payload["scope"]["directCpoIdentifiers"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
