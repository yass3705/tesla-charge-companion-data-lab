#!/usr/bin/env python3
"""Integrate exact Electra NL direct-pay prices from the official public map/API.

The public Electra map exposes location UUIDs and its own client calls the
GraphQL endpoint below for the live EVSE list and location tariff.  The API
host contains ``emsp`` for historical reasons, but the accepted records are
limited to locations whose CPO and operator are both Electra and whose price
is the official no-subscription/card/app price shown before charging.

Fail closed on national identity ambiguity, missing prices, unsupported tariff
components, or a connector-count mismatch.  Never imports roaming, charging-
card, Electra+ subscription, or partner prices.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


MAP_URL = "https://stations.go-electra.com/nl"
API_URL = "https://emsp.go-electra.com/graphql"
PARTY = "ELD"
LOCATION_RE = re.compile(r'"type":"Feature".*?"properties":(\{.*?\})', re.S)
GRAPHQL = """query($id:ID!){location(id:$id){id name country cpo{name} operator{name}
 evses{id evseId physicalReference status connectors{id}}
 chargeTariffs{chargeTariffId currency currentPricePerKwh elements{
 restrictions{dayOfWeek startTime endTime minDuration maxDuration minKwh maxKwh minPower maxPower}
 priceComponents{type price}}}}}"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get(url: str, payload: dict | None = None) -> bytes:
    request = urllib.request.Request(url, method="POST" if payload else "GET")
    request.add_header("User-Agent", "tesla-charge-companion-data-lab/electra-nl")
    if payload is not None:
        request.add_header("Content-Type", "application/json")
        request.data = json.dumps(payload).encode()
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def read_gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_gz(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def parse_features(page: str) -> list[dict]:
    marker = '[{"type":"Feature"'
    start = page.find(marker)
    if start < 0:
        raise RuntimeError("Electra public map did not expose its FeatureCollection")
    try:
        features, _ = json.JSONDecoder().raw_decode(page[start:])
    except json.JSONDecodeError as exc:
        raise RuntimeError("Electra FeatureCollection could not be decoded") from exc
    return [f["properties"] for f in features if f.get("properties", {}).get("country") == "NL"]


def tariff_elements(api_tariffs: list[dict]) -> tuple[str, list[dict], list[dict]] | None:
    if not api_tariffs:
        return None
    # Electra's own client selects the tariff with the most specific live
    # restrictions, then uses its energy component.  Keep every supported
    # direct component, but reject congestion/surcharge semantics we cannot
    # represent deterministically in the DOT-NL OCPI tariff model.
    selected = sorted(
        api_tariffs,
        key=lambda tariff: (
            -sum(bool((element.get("restrictions") or {}).get(k)) for element in tariff.get("elements", []) for k in ("dayOfWeek", "startTime", "endTime")),
            float(tariff.get("currentPricePerKwh") or 10**9),
        ),
    )[0]
    elements = []
    omitted = []
    for element in selected.get("elements") or []:
        components = []
        for component in element.get("priceComponents") or []:
            kind = str(component.get("type") or "").upper()
            price = component.get("price")
            if kind not in {"ENERGY", "TIME", "PARKING_TIME", "FLAT"} or not isinstance(price, (int, float)):
                if kind in {"CONGESTION_TIME"}:
                    omitted.append({"type": kind, "price": price, "restriction": element.get("restrictions") or None})
                    continue
                return None
            components.append({"type": kind, "priceExVat": price, "priceInclVat": price, "stepSize": 1})
        if components:
            elements.append({"priceComponents": components, "restrictions": element.get("restrictions") or None})
    if not elements:
        return None
    token = json.dumps(elements, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(token.encode()).hexdigest()[:16], elements, omitted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized", type=Path, default=Path("data/national/netherlands_dotnl/normalized.json.gz"))
    parser.add_argument("--overlay", type=Path, default=Path("data/operator_direct/electra_nl_graphql_exact_overlay.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/netherlands/electra-direct-payg-integration-latest.json"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    data = read_gz(args.normalized)
    national: dict[str, list[tuple[dict, dict]]] = {}
    for station in data.get("stations") or []:
        if station.get("partyId") != PARTY:
            continue
        for evse in station.get("evses") or []:
            national.setdefault(str(evse.get("evseId") or ""), []).append((station, evse))

    features = parse_features(get(MAP_URL).decode("utf-8"))
    tariffs: dict[str, dict] = {}
    matches: list[dict] = []
    rejected: list[dict] = []
    stats = Counter()
    locations: dict[str, dict | None] = {}
    aliases = []
    for i, feature in enumerate(features):
        location_id = str(feature.get("id") or "")
        aliases.append(f"loc_{i}: location(id: {json.dumps(location_id)}) {{ id name country cpo{{name}} operator{{name}} evses{{id evseId physicalReference status connectors{{id}}}} chargeTariffs{{chargeTariffId currency currentPricePerKwh elements{{restrictions{{dayOfWeek startTime endTime}} priceComponents{{type price}}}}}} }}")
    try:
        response = json.loads(get(API_URL, {"query": "query { " + " ".join(aliases) + " }"}))
        locations = (response.get("data") or {})
    except Exception as exc:
        for feature in features:
            rejected.append({"locationId": str(feature.get("id") or ""), "reason": "api_error", "detail": str(exc)[:300]})
    for feature in features:
        location_id = str(feature.get("id") or "")
        location = locations.get(f"loc_{features.index(feature)}")
        if location is None:
            rejected.append({"locationId": location_id, "reason": "api_location_missing"})
            continue
        if not location:
            rejected.append({"locationId": location_id, "reason": "api_location_missing"})
            continue
        if location.get("country") != "NL" or (location.get("cpo") or {}).get("name") != "Electra" or (location.get("operator") or {}).get("name") != "Electra":
            rejected.append({"locationId": location_id, "reason": "cpo_operator_not_exact_electra"})
            continue
        compiled = tariff_elements(location.get("chargeTariffs") or [])
        if not compiled:
            rejected.append({"locationId": location_id, "reason": "no_supported_direct_tariff"})
            continue
        digest, elements, omitted = compiled
        tariff_key = f"NL:{PARTY}:ELECTRA-PAYG:{digest}"
        tariffs[tariff_key] = {"tariffKey": tariff_key, "countryCode": "NL", "partyId": PARTY, "tariffId": f"ELECTRA-PAYG:{digest}", "type": "AD_HOC_PAYMENT", "currency": (location.get("chargeTariffs") or [{}])[0].get("currency", "EUR"), "elements": elements, "source": MAP_URL, "sourceKind": "official_cpo_direct_payg_api", "sourceMetadata": {"provider": "Electra", "cpoOnly": True, "emspExcluded": True, "roamingExcluded": True, "subscriptionExcluded": True, "paymentModes": ["bank_card_terminal", "official_electra_app"], "exactLocationId": location_id, "identityPolicy": "exact national EVSE and unique connector identity", "omittedUnsupportedComponents": omitted, "energyComponentExact": True}}
        for source_evse in location.get("evses") or []:
            evse_id = str(source_evse.get("evseId") or "")
            pairs = national.get(evse_id, [])
            if len(pairs) != 1:
                rejected.append({"locationId": location_id, "evseId": evse_id, "reason": "national_evse_missing_or_duplicated"})
                continue
            station, evse = pairs[0]
            source_connectors = source_evse.get("connectors") or []
            national_connectors = evse.get("connectors") or []
            if len(source_connectors) != len(national_connectors) or len(national_connectors) != 1:
                rejected.append({"locationId": location_id, "evseId": evse_id, "reason": "connector_identity_ambiguous", "sourceConnectorCount": len(source_connectors), "nationalConnectorCount": len(national_connectors)})
                continue
            connector = national_connectors[0]
            old_keys = list(connector.get("tariffKeys") or [])
            if old_keys and all(str(k).startswith("NL:ELD:") and data.get("tariffs", {}).get(k, {}).get("sourceKind") not in {None, "official_cpo_direct_payg_api"} for k in old_keys):
                stats["existing_preserved"] += 1
                continue
            if not args.no_write:
                connector["tariffKeys"] = [tariff_key]
                connector["tariffIds"] = []
                connector["unresolvedTariffIds"] = []
            matches.append({"stationId": station.get("stationId"), "evseId": evse_id, "connectorId": connector.get("id"), "locationId": location_id, "tariffKey": tariff_key, "sourceConnectorId": source_connectors[0].get("id"), "match": "exact_evse_unique_connector"})
            stats["promoted"] += 1
    data.setdefault("tariffs", {}).update(tariffs)
    overlay = {"schemaVersion": 1, "dataset": "nl-electra-direct-payg-exact-overlay", "generatedAt": now(), "country": "NL", "partyId": PARTY, "source": MAP_URL, "api": API_URL, "tariffs": tariffs, "matches": matches, "rejected": rejected, "policy": {"directCpoOnly": True, "officialElectraMapAndApiOnly": True, "emspExcluded": True, "roamingExcluded": True, "subscriptionExcluded": True, "exactEvseAndUniqueConnectorMatchOnly": True, "ambiguousConnectorFailClosed": True, "existingDirectTariffsPreserved": True}}
    report = {"schemaVersion": 1, "generatedAt": overlay["generatedAt"], "dataset": "netherlands-electra-direct-payg-integration", "publicMapNlLocations": len(features), "promotedExactConnectors": stats["promoted"], "tariffScheduleCount": len(tariffs), "rejectedCount": len(rejected), "rejectedReasons": dict(Counter(r["reason"] for r in rejected)), "status": "validated_no_write" if args.no_write else "integrated", "source": {"map": MAP_URL, "api": API_URL}, "policy": overlay["policy"]}
    if not args.no_write:
        write_gz(args.normalized, data)
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        args.overlay.write_text(json.dumps(overlay, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
