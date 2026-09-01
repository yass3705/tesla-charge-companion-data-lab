#!/usr/bin/env python3
"""Build a fail-closed Ewiva contactless-direct candidate for Italy V9.

Ewiva's public map publishes both its current site inventory and the explicit
``nopos_ids`` exclusion list used by the "pay by card" filter.  This builder
validates that first-party rule, keeps active POS sites only, and maps them to
PUN Ewiva stations with a deliberately strict geographic + address join.

No tariff is expanded to every Ewiva EVSE.  Ambiguous, distant, inactive,
``nopos`` and weak-metadata matches remain unpublished.
"""
from __future__ import annotations

import argparse
import gzip
import html as html_lib
import json
import math
import re
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRICE_URL = "https://ewiva.com/nuova-tariffa-agosto-2026/"
MAP_URL = "https://ewiva.com/colonnine-ricarica/"
LOCATIONS_URL = "https://ewiva.com/wp-content/themes/ewiva/it.bluedog.www/map/data/locations.json"
MAP_MANAGER_URL = "https://ewiva.com/wp-content/themes/ewiva/assets/js/mapmanager.js?ver=1.1"
DIRECT_EUR_PER_KWH = 0.80
VALID_FROM = "2026-08-01"
MAX_MATCH_METERS = 25.0
USER_AGENT = "tesla-charge-companion-data-lab/ewiva-pos-direct-v9"

STREET_STOPWORDS = {
    "via",
    "viale",
    "strada",
    "piazza",
    "piazzale",
    "localita",
    "contrada",
    "della",
    "delle",
    "degli",
    "dello",
    "dei",
    "del",
    "di",
    "corso",
    "zona",
    "provincia",
    "regione",
    "statale",
    "italia",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP {response.status} for {url}")
        return response.read().decode("utf-8")


def read_text(path: str | None, url: str) -> str:
    return Path(path).read_text(encoding="utf-8") if path else fetch_text(url)


def read_json(path: str | None, url: str) -> dict[str, Any]:
    value = json.loads(read_text(path, url))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object payload from {path or url}")
    return value


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("expected object PUN payload")
    return value


def save_gz(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def normalize(value: Any) -> str:
    decoded = urllib.parse.unquote_plus(str(value or ""))
    ascii_text = unicodedata.normalize("NFKD", decoded).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text.casefold()))


def text_from_html(raw: str) -> str:
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return " ".join(html_lib.unescape(without_tags).split())


def validate_price_page(raw: str) -> None:
    text = text_from_html(raw).casefold().replace("\xa0", " ")
    decimal_text = text.replace(",", ".")
    if not re.search(r"\b0\.80\s*€?\s*/?\s*kwh\b", decimal_text):
        raise RuntimeError("official Ewiva tariff page no longer confirms 0.80 EUR/kWh")
    if not re.search(r"\b1\s*°?\s*agosto\s+2026\b", text):
        raise RuntimeError("official Ewiva tariff page no longer confirms 2026-08-01")
    if "stazioni abilitate" not in text or "contactless" not in text:
        raise RuntimeError("official Ewiva tariff page no longer limits retail price to contactless-enabled sites")


def validate_map_algorithm(raw: str) -> None:
    compact = re.sub(r"\s+", " ", raw)
    required = (
        "getPOSLocations",
        "window.nopos_ids",
        "idsWithoutPOS.includes",
        "/map/data/locations.json",
    )
    missing = [token for token in required if token not in compact]
    if missing:
        raise RuntimeError(f"Ewiva public map algorithm changed; missing {missing}")
    if not re.search(r"!\s*idsWithoutPOS\.includes\s*\(\s*loc\?\.store_code\s*\)", compact):
        raise RuntimeError("Ewiva POS filter is no longer inventory minus nopos_ids")
    if not re.search(r"location\.status\s*==+\s*(?:1|['\"]1['\"])", compact):
        raise RuntimeError("Ewiva map no longer explicitly filters active status 1")


def extract_nopos_ids(raw: str) -> tuple[list[str], set[str]]:
    match = re.search(r"window\.nopos_ids\s*=\s*(\[[^;]+\])", raw, flags=re.S)
    if not match:
        raise RuntimeError("official Ewiva map page no longer publishes window.nopos_ids")
    values = json.loads(match.group(1))
    if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
        raise RuntimeError("invalid Ewiva nopos_ids payload")
    return values, set(values)


def haversine_meters(a: list[float] | tuple[float, float], b: list[float] | tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, (float(a[0]), float(a[1])))
    lat2, lon2 = map(math.radians, (float(b[0]), float(b[1])))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 12_742_000 * math.asin(math.sqrt(value))


def address_evidence(station: dict[str, Any], location: dict[str, Any]) -> dict[str, bool]:
    address = location.get("address") or {}
    official_city = normalize(address.get("city"))
    pun_city = normalize(station.get("city"))
    city_match = bool(
        official_city
        and pun_city
        and (
            official_city == pun_city
            or (len(official_city) >= 4 and f" {official_city} " in f" {pun_city} ")
            or (len(pun_city) >= 4 and f" {pun_city} " in f" {official_city} ")
        )
    )

    official_street = {
        token
        for token in normalize(address.get("street")).split()
        if len(token) >= 4 and token not in STREET_STOPWORDS
    }
    pun_street = {
        token
        for token in normalize(station.get("address")).split()
        if len(token) >= 4 and token not in STREET_STOPWORDS
    }
    shared = official_street & pun_street
    street_match = bool(
        official_street
        and pun_street
        and (
            len(shared) >= 2
            or (len(official_street) == 1 and official_street <= pun_street)
            or (len(pun_street) == 1 and pun_street <= official_street)
        )
    )
    region_match = bool(
        normalize(address.get("region"))
        and normalize(address.get("region")) == normalize(station.get("region"))
    )
    return {"region": region_match, "city": city_match, "street": street_match}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pun", default="data/national/pun_italy_national.json.gz")
    parser.add_argument("--out", default="data/national/ewiva_pos_direct_italy_candidate.json.gz")
    parser.add_argument("--report", default="data/reports/ewiva_pos_direct_italy_report.json")
    parser.add_argument("--price-html")
    parser.add_argument("--map-html")
    parser.add_argument("--locations-json")
    parser.add_argument("--map-manager-js")
    args = parser.parse_args()

    price_html = read_text(args.price_html, PRICE_URL)
    map_html = read_text(args.map_html, MAP_URL)
    locations_payload = read_json(args.locations_json, LOCATIONS_URL)
    map_manager = read_text(args.map_manager_js, MAP_MANAGER_URL)
    validate_price_page(price_html)
    validate_map_algorithm(map_manager)
    nopos_raw, nopos_ids = extract_nopos_ids(map_html)

    locations = [row for row in locations_payload.get("locations") or [] if isinstance(row, dict)]
    store_codes = [str(row.get("store_code") or "") for row in locations]
    if len(store_codes) != len(set(store_codes)) or any(not code for code in store_codes):
        raise RuntimeError("Ewiva location inventory has missing or duplicate store codes")
    if nopos_ids - set(store_codes):
        raise RuntimeError("Ewiva nopos_ids contains codes absent from the official inventory")
    active_locations = [row for row in locations if str(row.get("status")) == "1"]
    active_pos_locations_including_test = [
        row
        for row in active_locations
        if row["store_code"] not in nopos_ids
    ]
    active_pos_locations = [
        row
        for row in active_pos_locations_including_test
        if not str(row["store_code"]).startswith("TEST_")
    ]

    pun = load_gz(Path(args.pun))
    ewiva_stations = [
        row
        for row in pun.get("stations") or []
        if isinstance(row, dict) and str(row.get("partyId") or "").upper() == "EWI"
    ]
    pun_evse_count = sum(len(row.get("evses") or []) for row in ewiva_stations)

    entries: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    blocked: Counter[str] = Counter()
    matched_site_codes: set[str] = set()

    for station in ewiva_stations:
        coordinates = station.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) != 2:
            blocked["pun_coordinates_missing"] += 1
            continue
        nearby = sorted(
            (
                haversine_meters(coordinates, [location.get("lat"), location.get("lng")]),
                location,
            )
            for location in active_locations
        )
        within = [candidate for candidate in nearby if candidate[0] <= MAX_MATCH_METERS]
        if not within:
            blocked["no_active_official_site_within_25m"] += 1
            continue
        if len(within) != 1:
            blocked["ambiguous_active_official_sites_within_25m"] += 1
            continue

        distance, location = within[0]
        site_code = str(location["store_code"])
        if site_code in nopos_ids:
            blocked["official_site_in_nopos_ids"] += 1
            continue
        if site_code.startswith("TEST_"):
            blocked["official_test_site"] += 1
            continue
        evidence = address_evidence(station, location)
        if evidence["region"] is not True or not (evidence["city"] or evidence["street"]):
            blocked["metadata_evidence_failed"] += 1
            continue

        station_id = str(station.get("stationId") or "")
        if not station_id:
            raise RuntimeError("matched PUN Ewiva station has no stationId")
        matched_site_codes.add(site_code)
        station_entries = []
        for evse in station.get("evses") or []:
            evse_id = str((evse or {}).get("evseId") or "")
            if not evse_id.startswith("IT*EWI*E"):
                raise RuntimeError(f"invalid matched Ewiva EVSE identity {evse_id!r}")
            entry = {
                "evseId": evse_id,
                "stationId": station_id,
                "partyId": "EWI",
                "operator": "Ewiva",
                "sourceStatus": evse.get("sourceStatus"),
                "operationalState": evse.get("operationalState"),
                "officialSiteCode": site_code,
                "matchDistanceMeters": round(distance, 3),
                "matchEvidence": evidence,
                "directTariff": {
                    "pricingType": "flat",
                    "energyEurPerKwh": DIRECT_EUR_PER_KWH,
                    "currency": "EUR",
                    "validFrom": VALID_FROM,
                    "validThrough": None,
                    "paymentMethod": "contactless_pos",
                    "rankable": True,
                    "tariffSource": PRICE_URL,
                    "eligibilitySources": [MAP_URL, LOCATIONS_URL, MAP_MANAGER_URL],
                },
            }
            entries.append(entry)
            station_entries.append(evse_id)
        matches.append(
            {
                "stationId": station_id,
                "officialSiteCode": site_code,
                "distanceMeters": round(distance, 3),
                "matchEvidence": evidence,
                "evseCount": len(station_entries),
            }
        )

    entries.sort(key=lambda row: row["evseId"])
    matches.sort(key=lambda row: (row["officialSiteCode"], row["stationId"]))
    evse_ids = [row["evseId"] for row in entries]
    if len(evse_ids) != len(set(evse_ids)):
        raise RuntimeError("duplicate Ewiva EVSE identity in direct candidate")

    counts = {
        "officialInventoryLocations": len(locations),
        "officialActiveLocations": len(active_locations),
        "officialNoPosIdsRaw": len(nopos_raw),
        "officialNoPosIdsUnique": len(nopos_ids),
        "officialActivePosLocationsIncludingTest": len(active_pos_locations_including_test),
        "officialActivePosLocations": len(active_pos_locations),
        "punEwivaStations": len(ewiva_stations),
        "punEwivaEvse": pun_evse_count,
        "matchedPunStations": len(matches),
        "matchedOfficialPosSites": len(matched_site_codes),
        "rankableDirectEvse": len(entries),
        "blockedPunStations": dict(sorted(blocked.items())),
    }
    safety_gates = {
        "officialInventoryLargeEnough": len(locations) >= 500,
        "officialActiveInventoryLargeEnough": len(active_locations) >= 400,
        "officialNoPosListPlausible": 50 <= len(nopos_ids) <= 150,
        "officialActivePosInventoryLargeEnough": len(active_pos_locations) >= 350,
        "punEwivaInventoryLargeEnough": len(ewiva_stations) >= 800 and pun_evse_count >= 1600,
        "strictMatchesLargeEnough": len(matches) >= 600 and len(entries) >= 1100,
        "multipleOfficialSitesRemainFailClosed": blocked["ambiguous_active_official_sites_within_25m"] > 0,
        "allEntriesWithin25m": all(row["matchDistanceMeters"] <= MAX_MATCH_METERS for row in entries),
        "allEntriesHaveMetadataEvidence": all(
            row["matchEvidence"]["region"] and (row["matchEvidence"]["city"] or row["matchEvidence"]["street"])
            for row in entries
        ),
        "noNoPosOrTestSitePublished": all(
            row["officialSiteCode"] not in nopos_ids and not row["officialSiteCode"].startswith("TEST_")
            for row in entries
        ),
        "tariffExactly080": all(row["directTariff"]["energyEurPerKwh"] == DIRECT_EUR_PER_KWH for row in entries),
    }
    if not all(safety_gates.values()):
        raise RuntimeError(f"Ewiva candidate safety gates failed: {safety_gates}")

    generated_at = now_iso()
    payload = {
        "schemaVersion": 1,
        "dataset": "ewiva-pos-direct-italy-candidate",
        "generatedAt": generated_at,
        "country": "IT",
        "operator": "Ewiva",
        "partyId": "EWI",
        "tariff": {
            "pricingType": "flat",
            "energyEurPerKwh": DIRECT_EUR_PER_KWH,
            "currency": "EUR",
            "validFrom": VALID_FROM,
            "validThrough": None,
            "paymentMethod": "contactless_pos",
        },
        "sources": {
            "tariff": PRICE_URL,
            "eligibleSites": MAP_URL,
            "locations": LOCATIONS_URL,
            "mapAlgorithm": MAP_MANAGER_URL,
        },
        "sourceSnapshot": {
            "locationsExpiration": locations_payload.get("expiration"),
            "locationsLatestModified": max(
                (str(row.get("date_last_modified") or "") for row in locations), default=""
            ),
        },
        "policy": {
            "officialMapAlgorithmValidated": True,
            "activeStatusOneOnly": True,
            "officialNoPosIdsExcluded": True,
            "exactPunEvseIdentityOnly": True,
            "maxGeographicMatchMeters": MAX_MATCH_METERS,
            "regionAndCityOrStreetEvidenceRequired": True,
            "ambiguousMatchesFailClosed": True,
            "unmatchedSitesFailClosed": True,
            "neverExpandPriceToAllEwivaStations": True,
            "authorizationHoldIsNotSessionCost": True,
            "postChargeFeeRemainsUnknown": True,
        },
        "counts": counts,
        "safetyGates": safety_gates,
        "entries": entries,
    }
    save_gz(Path(args.out), payload)
    report = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "counts": counts,
        "sourceSnapshot": payload["sourceSnapshot"],
        "policy": payload["policy"],
        "safetyGates": safety_gates,
        "matchSample": matches[:100],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
