#!/usr/bin/env python3
"""Read-only EnergyVision DATEX <> pinned Belgium NAP identity and pricing audit.

Never join station-level tariffs to EVSE offers or write into V9 production.
The report contains aggregates only; stage files remain short-lived Actions artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import re


def normalized(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def connector_kind(value):
    value = str(value or "").lower()
    if "combo" in value or "ccs" in value:
        return "CCS"
    if "iec62196t2" in value or value in ("type 2", "type2"):
        return "TYPE2"
    return "UNSUPPORTED"


def finite(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def distance_metres(lat1, lon1, lat2, lon2):
    coords = [finite(x) for x in (lat1, lon1, lat2, lon2)]
    if any(x is None for x in coords):
        return None
    a, b, c, d = map(math.radians, coords)
    square = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 12742000 * math.asin(min(1, math.sqrt(square)))


def compatible_power(a, b, kind):
    a, b = finite(a), finite(b)
    if not a or not b or a <= 0 or b <= 0:
        return False
    if kind == "TYPE2":
        return abs(a - b) <= max(a, b) * 0.10
    if kind == "CCS":
        return abs(a - b) <= 15000
    return False


def nap_connectors(manifest_path):
    manifest_path = Path(manifest_path)
    root = manifest_path.parents[2]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("country") != "BE" or not manifest.get("pages"):
        raise ValueError("Invalid pinned NAP manifest")
    for page_meta in manifest["pages"]:
        path = root / page_meta["canonicalPath"]
        with gzip.open(path, "rt", encoding="utf-8") as fp:
            page = json.load(fp)
        for loc in page.get("locations") or []:
            for station in loc.get("stations") or []:
                for evse in station.get("evses") or []:
                    for conn in evse.get("connectors") or []:
                        ids = set(evse.get("externalIdentifiers") or [])
                        ids.update(conn.get("externalIdentifiers") or [])
                        yield {
                            "location": loc.get("id"), "evse": evse.get("id"),
                            "lat": loc.get("latitude"), "lon": loc.get("longitude"),
                            "kind": connector_kind(conn.get("type")),
                            "power": conn.get("maxPowerW"),
                            "ids": tuple(sorted(x for x in ids if x)),
                        }


def energyvision_connectors(stage):
    for site in stage["static"]["sites"]:
        for station in site["stations"]:
            for point in station["refillPoints"]:
                for conn in point["connectors"]:
                    yield {
                        "site": site["sourceSiteId"],
                        "point": point["sourceRefillPointId"],
                        "id": conn.get("sourceExternalIdentifier"),
                        "lat": site.get("latitude"), "lon": site.get("longitude"),
                        "kind": connector_kind(conn.get("sourceConnectorType")),
                        "power": conn.get("sourcePowerW") or point.get("sourcePowerW"),
                    }


def audit_identity(stage, nap):
    exact, canonical = defaultdict(list), defaultdict(list)
    nap_locations, nap_points = set(), set()
    counts = Counter()
    for item in nap:
        counts["napConnectors"] += 1
        nap_locations.add(item["location"])
        nap_points.add((item["location"], item["evse"]))
        for name in item["ids"]:
            exact[name.upper()].append(item)
            canonical[normalized(name)].append(item)
    source_ids = Counter()
    for src in energyvision_connectors(stage):
        counts["sourceConnectors"] += 1
        src_id = str(src.get("id") or "")
        source_ids[src_id] += 1
        candidates = exact.get(src_id.upper(), []) if src_id else []
        match_type = "exact"
        if not candidates and src_id:
            candidates = canonical.get(normalized(src_id), [])
            match_type = "normalized"
        unique = {(c["location"], c["evse"], c["kind"]): c for c in candidates}
        if not unique:
            counts["unmatchedIds"] += 1
            continue
        if len(unique) != 1:
            counts["ambiguousIds"] += 1
            continue
        target = next(iter(unique.values()))
        if src["kind"] != target["kind"] or src["kind"] == "UNSUPPORTED":
            counts[match_type + "ConnectorMismatch"] += 1
        elif not compatible_power(src["power"], target["power"], src["kind"]):
            counts[match_type + "PowerMismatch"] += 1
        else:
            metres = distance_metres(src["lat"], src["lon"], target["lat"], target["lon"])
            if metres is None:
                counts[match_type + "MissingGPS"] += 1
            elif metres > 10:
                counts[match_type + "GPSConflict"] += 1
            else:
                counts[match_type + "Verified"] += 1
    counts["napLocations"] = len(nap_locations)
    counts["napDistinctEVSE"] = len(nap_points)
    counts["sourceDuplicateExternalIds"] = sum(v - 1 for k, v in source_ids.items() if k and v > 1)
    return dict(counts)


def audit_tariff_shapes(stage):
    counts, shapes, types, months = Counter(), Counter(), Counter(), Counter()
    for site in stage["static"]["sites"]:
        for station in site["stations"]:
            rates = station.get("stationRatesUnassignedToEvse") or []
            if not rates:
                counts["stationsWithoutRate"] += 1
            for rate in rates:
                prices = rate.get("priceComponents") or []
                shapes["+".join(sorted(set(p["priceType"] for p in prices)))] += 1
                has_window, has_threshold = False, False
                for price in prices:
                    types[price["priceType"]] += 1
                    for leaf in price.get("rawApplicabilityLeaves") or []:
                        path = leaf.get("path") or ""
                        if "recurringTimePeriodOfDay" in path:
                            has_window = True
                        if path.endswith("/fromMinute") or path.endswith("/toMinute"):
                            has_threshold = True
                counts["stationAdhocRates"] += 1
                if has_window:
                    counts["ratesWithClockWindows"] += 1
                if has_threshold:
                    counts["ratesWithSessionMinuteThresholds"] += 1
                if len(prices) == 1 and not has_window and not has_threshold:
                    counts["simpleSingleComponentStationRates"] += 1
                else:
                    counts["rulesRequiringComponentSemanticsReview"] += 1
                months[str(rate.get("sourceLastUpdated") or "")[:7]] += 1
    return {
        "counts": dict(counts), "shapes": dict(shapes),
        "componentTypes": dict(types), "sourceLastUpdatedByMonth": dict(sorted(months.items())),
    }


def reconcile(stage, nap):
    return {
        "provider": "EnergyVision", "country": "BE",
        "collectedAt": stage.get("collectedAt"),
        "sourceStaticSha256": stage["sourceStatic"]["sha256"],
        "napManifest": "data/belgium/nap-belgium-manifest.json",
        "identity": audit_identity(stage, nap),
        "tariffShapes": audit_tariff_shapes(stage),
        "v9PricePublicationReady": False,
        "note": "Do not assign station adHoc rates to PDC or add to ranking without proof of scope, timing, status, public access and numerical oracle.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--manifest", default="data/belgium/nap-belgium-manifest.json")
    parser.add_argument("--report", default="reports/belgium/energyvision-nap-exact-audit.json")
    args = parser.parse_args()
    with gzip.open(args.stage, "rt", encoding="utf-8") as fp:
        stage = json.load(fp)
    if stage.get("provider") != "EnergyVision" or stage.get("country") != "BE":
        raise ValueError("Wrong stage provider/country")
    report = reconcile(stage, nap_connectors(args.manifest))
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "identity": report["identity"],
        "tariffCounts": report["tariffShapes"]["counts"],
        "tariffShapes": report["tariffShapes"]["shapes"],
        "v9PricePublicationReady": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
