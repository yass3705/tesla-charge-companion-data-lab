#!/usr/bin/env python3
"""Stage EnergyVision BE AFIR DATEX data without assigning a tariff to an EVSE.

A station-level DATEX energyRate is NOT automatically an EVSE-level offer.
This staged dataset and its audit are for reconciliation only; Production does
not load them, and all prices remain non-published.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import os
from pathlib import Path
import urllib.request

from defusedxml import ElementTree as DET
from scripts.energyvision_datex_inventory_probe import BASE, MAX_BYTES, local, safely_read


def kids(node, name):
    return [c for c in node] if name == "*" else [c for c in node if local(c.tag) == name] if node is not None else []


def kid(node, name):
    return next(iter(kids(node, name)), None) if node is not None else None


def scalar(node):
    if node is None:
        return None
    if node.text and node.text.strip():
        return node.text.strip()
    for part in node.iter():
        if part is node:
            continue
        if part.text and part.text.strip():
            return part.text.strip()
    return None


def get(node, *path):
    for name in path:
        node = kid(node, name)
        if node is None:
            return None
    return scalar(node)


def attr(node, key="id"):
    return node.attrib.get(key) if node is not None else None


def finite_decimal(value):
    if not value:
        return None
    try:
        d = Decimal(str(value))
        return str(d) if d.is_finite() else None
    except InvalidOperation:
        return None


def component_leaves(node, max_leaves=100):
    """Preserve source-specific applicability without pretending to interpret it."""
    result = []
    def walk(element, trail):
        if len(result) >= max_leaves:
            return
        children = list(element)
        if not children:
            value = (element.text or "").strip()
            if value:
                result.append({"path": "/".join(trail), "value": value[:200]})
        else:
            for c in children:
                walk(c, trail + [local(c.tag)])
    walk(node, [local(node.tag)])
    return result


def interpret_static(body: bytes) -> dict:
    root = DET.fromstring(body)
    sites = []
    for site_node in root.iter():
        if local(site_node.tag) != "energyInfrastructureSite":
            continue
        latitude = finite_decimal(get(site_node, "entrance", "pointByCoordinates", "pointCoordinates", "latitude"))
        longitude = finite_decimal(get(site_node, "entrance", "pointByCoordinates", "pointCoordinates", "longitude"))
        site = {
            "sourceSiteId": attr(site_node),
            "name": get(site_node, "brand", "values", "value"),
            "sourceSiteType": get(site_node, "typeOfSite"),
            "sourceSiteEnergyRateCount": sum(len(kids(pr, "energyRate")) for pr in kids(site_node, "energyProduct")),
            "city": get(site_node, "entrance", "_locationExtension", "afirFacilityLocation", "address", "city"),
            "postalCode": get(site_node, "entrance", "_locationExtension", "afirFacilityLocation", "address", "postcode"),
            "latitude": latitude,
            "longitude": longitude,
            "stations": [],
        }
        for station_node in kids(site_node, "energyInfrastructureStation"):
            station = {
                "sourceStationId": attr(station_node),
                "maximumPowerSource": get(station_node, "totalMaximumPower"),
                "declaredRefillPoints": get(station_node, "numberOfRefillPoints"),
                "sourceStationEnergyRateCount": sum(len(kids(pr, "energyRate")) for pr in kids(station_node, "energyProduct")),
                "authenticationMethods": [scalar(m) for m in kids(station_node, "authenticationAndIdentificationMethods")],
                "refillPoints": [],
                "stationRatesUnassignedToEvse": [],
            }
            for point_node in kids(station_node, "refillPoint"):
                connectors = []
                for c in kids(point_node, "connector"):
                    connectors.append({
                        "sourceConnectorType": get(c, "connectorType"),
                        "sourcePowerW": get(c, "maxPowerAtSocket"),
                        "sourceExternalIdentifier": get(c, "externalIdentifier", "identifier"),
                        "sourceIdentifierType": get(c, "externalIdentifier", "typeOfIdentifier"),
                    })
                station["refillPoints"].append({
                    "sourceRefillPointId": attr(point_node),
                    "sourcePointEnergyRateCount": sum(len(kids(pr, "energyRate")) for pr in kids(point_node, "energyProduct")),
                    "currentType": get(point_node, "currentType"),
                    "sourcePowerW": get(point_node, "availableChargingPower"),
                    "connectors": connectors,
                })
            for prod in kids(station_node, "energyProduct"):
                for rate_node in kids(prod, "energyRate"):
                    prices = []
                    for c in kids(rate_node, "energyPrice"):
                        prices.append({
                            "groupIndex": get(c, "priceGroupIndex"),
                            "priceType": get(c, "priceType"),
                            "amountSource": finite_decimal(get(c, "value")),
                            "taxIncluded": get(c, "taxIncluded"),
                            "taxRateSource": finite_decimal(get(c, "taxRate")),
                            "rawApplicabilityLeaves": component_leaves(c),
                        })
                    station["stationRatesUnassignedToEvse"].append({
                        "sourceRateId": attr(rate_node),
                        "ratePolicy": get(rate_node, "ratePolicy"),
                        "sourceLastUpdated": get(rate_node, "lastUpdated"),
                        "currency": get(rate_node, "applicableCurrency"),
                        "priceComponents": prices,
                    })
            site["stations"].append(station)
        sites.append(site)
    return {"sites": sites}


def interpret_dynamic(body: bytes) -> dict:
    root = DET.fromstring(body)
    points = []
    stations = []
    for site_node in root.iter():
        if local(site_node.tag) != "energyInfrastructureSiteStatus":
            continue
        for station_node in kids(site_node, "energyInfrastructureStationStatus"):
            stations.append({
                "sourceReferenceId": attr(kid(station_node, "reference")),
                "isAvailable": get(station_node, "isAvailable"),
            })
            for point_node in kids(station_node, "refillPointStatus"):
                points.append({
                    "sourceReferenceId": attr(kid(point_node, "reference")),
                    "status": get(point_node, "status"),
                })
    return {"stationStatuses": stations, "refillPointStatuses": points}


def audit(staged: dict) -> dict:
    sites = staged["static"]["sites"]
    all_stations = [station for site in sites for station in site["stations"]]
    all_points = [p for station in all_stations for p in station["refillPoints"]]
    all_connectors = [c for p in all_points for c in p["connectors"]]
    all_rates = [rate for st in all_stations for rate in st["stationRatesUnassignedToEvse"]]
    all_components = [p for rate in all_rates for p in rate["priceComponents"]]
    sta_ids = {p["sourceRefillPointId"] for p in all_points if p["sourceRefillPointId"]}
    dyn_points = staged["dynamic"]["refillPointStatuses"]
    dyn_ids = {p["sourceReferenceId"] for p in dyn_points if p["sourceReferenceId"]}
    connector_types = Counter(c["sourceConnectorType"] or "UNKNOWN" for c in all_connectors)
    rate_policy = Counter(r["ratePolicy"] or "UNKNOWN" for r in all_rates)
    statuses = Counter(p["status"] or "UNKNOWN" for p in dyn_points)
    price_types = Counter(c["priceType"] or "UNKNOWN" for c in all_components)
    currencies = Counter(r["currency"] or "UNKNOWN" for r in all_rates)
    rates_by_station = Counter(len(st["stationRatesUnassignedToEvse"]) for st in all_stations)
    windows = sum(any("Time" in item["path"] or "Period" in item["path"] or "Minute" in item["path"] for item in p["rawApplicabilityLeaves"])
                  for p in all_components)
    return {
        "counts": {
            "sites": len(sites), "stations": len(all_stations),
            "refillPoints": len(all_points), "connectors": len(all_connectors),
            "stationLevelRates": len(all_rates), "priceComponents": len(all_components),
            "dynamicStationStatuses": len(staged["dynamic"]["stationStatuses"]),
            "dynamicRefillPointStatuses": len(dyn_points),
            "distinctStaticRefillIds": len(sta_ids),
            "distinctDynamicRefillRefs": len(dyn_ids),
            "exactStaticDynamicRefillLinks": len(sta_ids & dyn_ids),
            "staticRefillWithoutDynamic": len(sta_ids - dyn_ids),
            "dynamicRefillWithoutStatic": len(dyn_ids - sta_ids),
            "pricesWithTimeOrPeriodLeaves": windows,
        },
        "connectorTypes": dict(connector_types),
        "ratePolicies": dict(rate_policy),
        "priceTypes": dict(price_types),
        "currencies": dict(currencies),
        "statusValues": dict(statuses),
        "stationRateCountDistribution": {str(k): v for k, v in sorted(rates_by_station.items())},
        "warnings": [
            "Station-level rates have NOT been assigned to EVSE/connectors.",
            "Raw DATEX price components are not equivalent to verified V9 session prices.",
            "Source power values are not normalized to kW until units and connector kinds are validated.",
            "Status reference IDs require unique cross-check before claiming availability.",
        ],
        "v9ReadyForPriceRanking": False,
    }


def fetch_xml(endpoint: str, key: str) -> tuple[bytes, dict]:
    request = urllib.request.Request(BASE + "/" + endpoint,
        headers={"Authorization": "Bearer " + key, "Accept": "application/xml",
                 "Accept-Encoding": "identity", "User-Agent": "TeslaChargeCompanion/9 EnergyVision-AFIR-stage"})
    with urllib.request.urlopen(request, timeout=55) as response:
        if response.status != 200:
            raise ValueError("unexpected DATEX HTTP status")
        body = safely_read(response, MAX_BYTES[endpoint])
    if not body.lstrip().startswith(b"<"):
        raise ValueError("unexpected DATEX non-XML content")
    return body, {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report", default="reports/belgium/energyvision-datex-semantic-audit.json")
    p.add_argument("--staging", default="artifacts/energyvision-datex-stage.json.gz")
    args = p.parse_args()
    key = os.environ.get("ENERGYVISION_API_KEY", "").strip()
    if not key:
        raise SystemExit("ENERGYVISION_API_KEY not available")
    a, stat = fetch_xml("energy-infrastructure-table", key)
    b, dyn = fetch_xml("energy-infrastructure-status", key)
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    staged = {
        "schemaVersion": 1, "provider": "EnergyVision", "country": "BE",
        "collectedAt": timestamp,
        "sourceStatic": stat, "sourceDynamic": dyn,
        "v9PublicationReady": False,
        "static": interpret_static(a),
        "dynamic": interpret_dynamic(b),
    }
    report = {"provider": "EnergyVision", "country": "BE",
              "collectedAt": timestamp, "sourceStatic": stat, "sourceDynamic": dyn,
              **audit(staged)}
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    staging_path = Path(args.staging)
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(staging_path, "wt", encoding="utf-8", compresslevel=8) as file:
        json.dump(staged, file, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({"summary": report["counts"], "connectorTypes": report["connectorTypes"],
                      "ratePolicies": report["ratePolicies"], "priceTypes": report["priceTypes"],
                      "currencies": report["currencies"], "statusValues": report["statusValues"],
                      "v9ReadyForPriceRanking": False}, ensure_ascii=False))
    if report["counts"]["sites"] == 0 or report["counts"]["refillPoints"] == 0:
        raise SystemExit("No EnergyVision sites/refill points: block candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
