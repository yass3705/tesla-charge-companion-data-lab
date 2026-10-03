#!/usr/bin/env python3
"""Integrate the official TotalEnergies NL PAYG price surface.

The web portal publishes a public runtime configuration containing the API
base URL and the public web API key.  The key is read in memory from that
configuration and is never written to reports or overlays.

Only exact national EVSE/connector identities are accepted.  The accepted
product is the public ``Tarif visitor PAYG`` product: CHARGE, empty subEmsp,
and a fixed TTC EUR/kWh price in the Dutch price description.  Visitor
Hosting, PRIX FLEX and VARPRICE are intentionally fail-closed here.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


WEB_ROOT = "https://chargingservices.totalenergies.com/fr/find-a-charger?countryCode=NL"
WEB_JS_FALLBACK = "https://chargingservices.totalenergies.com/main.833f41fbec0463af.js"
API_PATH = "/v3/infrastructure/locations"
PORTAL = "https://chargingservices.totalenergies.com/fr/find-a-charger?countryCode=NL"
PARTY = "GFX"
PRICE_RE = re.compile(r"€\s*([0-9]+[,.][0-9]+)\s*/\s*kWh", re.I)
CONFIG_RE = re.compile(r"y=JSON\.parse\('([^\n]+?)'\)")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_config() -> tuple[str, str, str, str]:
    root_req = urllib.request.Request(
        WEB_ROOT,
        headers={"Accept": "text/html,*/*;q=0.8", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(root_req, timeout=60) as response:
        root = response.read().decode("utf-8", "replace")
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+main\.[^"\']+\.js)["\']', root, re.I)
    web_js = urllib.parse.urljoin(WEB_ROOT, scripts[-1]) if scripts else WEB_JS_FALLBACK
    req = urllib.request.Request(
        web_js,
        headers={"Accept": "application/javascript,*/*;q=0.8", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        text = response.read().decode("utf-8", "replace")
    match = CONFIG_RE.search(text)
    if not match:
        raise RuntimeError("Total web runtime configuration not found")
    config = json.loads(match.group(1))
    for name in ("bffApiUrl", "globalApiKey"):
        if not config.get(name):
            raise RuntimeError(f"Total web runtime configuration missing {name}")
    # marketplace-evp is in the separate Angular app config, not the env JSON.
    return config["bffApiUrl"], config["globalApiKey"], web_js


def fetch_inventory(base: str, key: str) -> list[dict]:
    params = urllib.parse.urlencode({"countryCode": "NL", "pageNumber": "0", "pageSize": "5", "language": "nl-NL"})
    req = urllib.request.Request(
        f"{base}{API_PATH}?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "x-apif-apikey": key,
            "marketplace-evp": "tcseu",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected Total locations payload")
    return payload


def read_normalized(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_normalized(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def fixed_price(product: dict) -> float | None:
    descriptions = ((product.get("price") or {}).get("priceDescriptions") or {})
    values = descriptions.get("nl-NL") or []
    if not values:
        return None
    match = PRICE_RE.search(str(values[0]))
    if not match:
        return None
    return round(float(match.group(1).replace(",", ".")), 6)


def tariff_for(gross: float) -> tuple[str, dict]:
    token = f"{gross:.6f}"
    key = "NL:GFX:TOTAL-PAYG:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    net = round(gross / 1.21, 6)
    return key, {
        "tariffKey": key,
        "countryCode": "NL",
        "partyId": PARTY,
        "tariffId": key.rsplit(":", 1)[-1],
        "type": "AD_HOC_PAYMENT",
        "currency": "EUR",
        "elements": [{
            "priceComponents": [{
                "type": "ENERGY",
                "priceExVat": net,
                "vatPct": 21.0,
                "priceInclVat": gross,
                "stepSize": 1,
            }],
            "restrictions": {},
        }],
        "source": PORTAL,
        "sourceKind": "official_cpo_payg_portal",
        "sourceMetadata": {
            "provider": "TotalEnergies Charging Services",
            "product": "Tarif visitor PAYG",
            "cpoOnly": True,
            "emspExcluded": True,
            "roamingExcluded": True,
            "priceTtc": True,
            "fixedPriceOnly": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized", type=Path, default=Path("data/national/netherlands_dotnl/normalized.json.gz"))
    parser.add_argument("--overlay", type=Path, default=Path("data/operator_direct/totalenergies_nl_payg_exact_overlay.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/netherlands/totalenergies-direct-payg-live-integration-2026-10-04.json"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    generated = now()
    base, api_key, web_js = fetch_config()
    inventory = fetch_inventory(base, api_key)
    data = read_normalized(args.normalized)

    national = {}
    duplicate_national = Counter()
    for station in data.get("stations") or []:
        if station.get("partyId") != PARTY:
            continue
        for evse in station.get("evses") or []:
            evse_id = evse.get("evseId")
            for connector in evse.get("connectors") or []:
                key = (evse_id, str(connector.get("id")))
                if key in national:
                    duplicate_national[key] += 1
                else:
                    national[key] = (station, evse, connector)

    source_rows = []
    reasons = Counter()
    for location in inventory:
        address = location.get("address") or {}
        if address.get("country") != "NL" or location.get("serviceOperatorId") != "TotalEnergies":
            continue
        for spot in location.get("chargingSpots") or []:
            for evse in spot.get("evses") or []:
                for connector in evse.get("connectors") or []:
                    key = (evse.get("emi3"), str(connector.get("id")))
                    products = [
                        product for product in evse.get("products") or []
                        if product.get("type") == "CHARGE"
                        and product.get("subEmsp", "") == ""
                        and "PAYG" in str(product.get("name", "")).upper()
                    ]
                    if len(products) != 1:
                        reasons["non_payg_or_ambiguous_product"] += 1
                        continue
                    product = products[0]
                    gross = fixed_price(product)
                    if gross is None:
                        reasons[str(((product.get("price") or {}).get("priceDescriptions") or {}).get("nl-NL", ["unparseable"])[0])] += 1
                        continue
                    if key not in national:
                        reasons["exact_evse_connector_not_in_dotnl"] += 1
                        continue
                    if key in duplicate_national:
                        reasons["duplicate_dotnl_identity"] += 1
                        continue
                    tariff_key, _ = tariff_for(gross)
                    source_rows.append({
                        "evseId": key[0],
                        "connectorId": key[1],
                        "tariffKey": tariff_key,
                        "grossEurPerKwh": gross,
                        "productName": product.get("name"),
                        "sourceLocationId": location.get("id"),
                        "sourceStationName": location.get("name"),
                        "sourceProductKey": product.get("productKey"),
                        "match": "exact_evse_and_connector",
                    })

    tariffs = {}
    for row in source_rows:
        tariffs[row["tariffKey"]] = tariff_for(row["grossEurPerKwh"])[1]

    changed = 0
    conflicts = []
    for row in source_rows:
        station, evse, connector = national[(row["evseId"], row["connectorId"])]
        old_ids = list(connector.get("tariffKeys") or connector.get("tariffIds") or [])
        old_gross = []
        for old_id in old_ids:
            old_tariff = data.get("tariffs", {}).get(old_id) or {}
            for element in old_tariff.get("elements") or []:
                for component in element.get("priceComponents") or []:
                    if component.get("type") == "ENERGY" and component.get("priceInclVat") is not None:
                        old_gross.append(round(float(component["priceInclVat"]), 6))
        if old_gross and row["grossEurPerKwh"] not in old_gross:
            conflicts.append({"evseId": row["evseId"], "connectorId": row["connectorId"], "oldGross": old_gross, "newGross": row["grossEurPerKwh"]})
        if not args.no_write:
            connector["tariffKeys"] = [row["tariffKey"]]
            connector["tariffIds"] = []
            connector["unresolvedTariffIds"] = []
        changed += 1

    if not args.no_write:
        data.setdefault("tariffs", {}).update(tariffs)
        data.setdefault("source", {}).setdefault("directTariffOverlays", [])
        data["source"]["directTariffOverlays"] = [
            x for x in data["source"]["directTariffOverlays"]
            if x.get("provider") != "TotalEnergies" or x.get("countryCode") != "NL"
        ] + [{
            "provider": "TotalEnergies",
            "countryCode": "NL",
            "source": PORTAL,
            "sourceKind": "official_cpo_payg_portal",
            "generatedAt": generated,
            "exactConnectorCount": changed,
            "emspExcluded": True,
        }]
        data["generatedAt"] = generated
        write_normalized(args.normalized, data)

    overlay = {
        "schemaVersion": 1,
        "dataset": "nl-totalenergies-official-payg-exact-overlay",
        "generatedAt": generated,
        "country": "NL",
        "partyId": PARTY,
        "source": PORTAL,
        "tariffs": tariffs,
        "matches": source_rows,
        "policy": {
            "officialWebApi": True,
            "directCpoOnly": True,
            "paygOnly": True,
            "emptySubEmspOnly": True,
            "exactEvseAndConnectorMatchOnly": True,
            "visitorHostingExcluded": True,
            "prixFlexAndVarpriceExcluded": True,
            "noStationInheritance": True,
        },
    }
    args.overlay.parent.mkdir(parents=True, exist_ok=True)
    args.overlay.write_text(json.dumps(overlay, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    report = {
        "schemaVersion": 1,
        "generatedAt": generated,
        "apiSource": {"webRuntime": WEB_JS, "endpoint": f"{base}{API_PATH}", "apiKeyPersisted": False},
        "officialInventory": {
            "locations": sum(1 for x in inventory if (x.get("address") or {}).get("country") == "NL" and x.get("serviceOperatorId") == "TotalEnergies"),
            "evseConnectors": sum(1 for x in inventory if (x.get("address") or {}).get("country") == "NL" and x.get("serviceOperatorId") == "TotalEnergies" for s in x.get("chargingSpots") or [] for e in s.get("evses") or [] for _ in e.get("connectors") or []),
        },
        "dotnlInventory": {"stations": sum(1 for x in data.get("stations") or [] if x.get("partyId") == PARTY), "connectorRecords": len(national)},
        "exactPricedConnectorCount": changed,
        "overlayTariffCount": len(tariffs),
        "rejectedReasons": dict(reasons),
        "conflictingExistingTariffs": conflicts,
        "status": "integrated" if not args.no_write else "candidate_only",
        "overlaySha256": hashlib.sha256(args.overlay.read_bytes()).hexdigest(),
        "guardrails": ["No eMSP or roaming product", "No Visitor Hosting", "No PRIX FLEX/VARPRICE", "No station inheritance", "Exact EVSE and connector identity only"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("officialInventory", "dotnlInventory", "exactPricedConnectorCount", "overlayTariffCount", "rejectedReasons", "status")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
