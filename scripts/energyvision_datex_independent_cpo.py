#!/usr/bin/env python3
"""Independent EnergyVision BE CPO inventory diagnostic, NEVER a direct EVSE tariff.

Station-level DATEX rates are retained by reference, not assigned to PDC.
No claim of public access is made from the source's infrastructure site type.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path

KINDS = {"iec62196t2": "TYPE2", "iec62196t2combo": "CCS"}
ACTIVE = {"available", "charging"}

def number(x):
    try:
        value = float(x)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None

def analyze(stage, nap_identity=None):
    if stage.get("provider") != "EnergyVision" or stage.get("country") != "BE":
        raise ValueError("Incorrect provider/country")
    if stage.get("v9PublicationReady") is not False:
        raise ValueError("Expected non-publication staging only")
    hash_value = stage.get("sourceStatic", {}).get("sha256")
    if not isinstance(hash_value, str) or len(hash_value) != 64:
        raise ValueError("Missing source SHA256")
    status_by_id = defaultdict(list)
    for entry in stage["dynamic"]["refillPointStatuses"]:
        identifier = entry.get("sourceReferenceId")
        if identifier:
            status_by_id[identifier].append(str(entry.get("status") or "unknown").lower())
    counts, rate_policies = Counter(), Counter()
    seen_point, seen_external, seen_site = set(), set(), set()
    sites = []
    for site in stage["static"]["sites"]:
        site_id = site.get("sourceSiteId")
        if not site_id or site_id in seen_site:
            raise ValueError("Duplicate or missing source site")
        seen_site.add(site_id)
        lat, lon = number(site.get("latitude")), number(site.get("longitude"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Invalid source coordinates")
        counts["sites"] += 1
        station_entries = []
        for station in site["stations"]:
            counts["stations"] += 1
            rates = station.get("stationRatesUnassignedToEvse") or []
            if not rates:
                counts["stationsWithoutRate"] += 1
            for rate in rates:
                counts["unassignedStationRates"] += 1
                rate_policies[str(rate.get("ratePolicy") or "unknown")] += 1
            points = []
            for point in station["refillPoints"]:
                pid = point.get("sourceRefillPointId")
                if not pid or pid in seen_point:
                    raise ValueError("Duplicate or empty PDC identifier")
                seen_point.add(pid)
                connectors = point.get("connectors") or []
                if len(connectors) != 1:
                    raise ValueError("Unresolved connector multiplicity")
                conn = connectors[0]
                external_id = conn.get("sourceExternalIdentifier")
                if not external_id or external_id in seen_external:
                    raise ValueError("Duplicate or missing external EVSE identity")
                seen_external.add(external_id)
                kind = KINDS.get(str(conn.get("sourceConnectorType") or "").lower())
                if kind is None:
                    counts["unsupportedConnectorPDC"] += 1
                    continue
                power = number(conn.get("sourcePowerW") or point.get("sourcePowerW"))
                if power is None or power <= 0:
                    raise ValueError("Invalid connector watts")
                candidates = status_by_id.get(pid, [])
                if len(candidates) != 1:
                    status = "unknown"
                    counts["ambiguousOrMissingStatusPDC"] += 1
                else:
                    status = candidates[0]
                counts["pdc_" + kind] += 1
                counts["status_" + status] += 1
                if status in ACTIVE:
                    counts["activePDC"] += 1
                counts["sourcePDC"] += 1
                points.append({
                    "sourcePointId": pid,
                    "externalEvseId": external_id,
                    "connectorType": kind,
                    "powerW": round(power, 3),
                    "status": status,
                    "publicAccessVerified": False,
                    "priceable": False,
                    "priceState": "station_rate_scope_unverified" if rates else "no_rate_source",
                })
            station_entries.append({
                "sourceStationId": station.get("sourceStationId"),
                "declaredRefillPoints": station.get("declaredRefillPoints"),
                "authenticationMethods": station.get("authenticationMethods", []),
                "unassignedStationRateIds": [rate.get("sourceRateId") for rate in rates],
                "pdc": points,
            })
        sites.append({
            "sourceSiteId": site_id,
            "sourceSiteType": site.get("sourceSiteType"),
            "latitude": lat, "longitude": lon,
            "city": site.get("city"), "postalCode": site.get("postalCode"),
            "publicAccessVerified": False,
            "stations": station_entries,
        })
    counts["distinctSiteIds"] = len(seen_site)
    counts["distinctExternalEvseIds"] = len(seen_external)
    counts["staticPointStatusLinks"] = len(seen_point & set(status_by_id))
    counts["dynamicReferencesNotInStatic"] = len(set(status_by_id) - seen_point)
    if nap_identity is not None:
        linked = sum(v for k,v in nap_identity.items() if k.endswith("Verified"))
        if linked:
            raise ValueError("Potential NAP duplicates: quarantine individually before supplement")
    return {
        "provider": "EnergyVision", "country": "BE", "schemaVersion": 1,
        "sourceSha256": hash_value, "collectedAt": stage.get("collectedAt"),
        "mode": "diagnostic_inventory_supplement_only",
        "v9PublicationReady": False, "v9PricedPDC": 0,
        "publicAccessEvidence": "unknown_source_site_type_not_equivalent_to_access",
        "rateScope": "station_level_unassigned",
        "napCrosswalk": nap_identity, "counts": dict(counts),
        "ratePolicies": dict(rate_policies), "sites": sites,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--output", default="artifacts/energyvision-independent-cpo-supplement.json.gz")
    ap.add_argument("--report", default="reports/belgium/energyvision-cpo-supplement-audit.json")
    opts = ap.parse_args()
    with gzip.open(opts.stage, "rt", encoding="utf-8") as f:
        stage = json.load(f)
    nap = None
    if opts.manifest:
        from scripts.energyvision_datex_nap_audit import audit_identity, nap_connectors
        nap = audit_identity(stage, nap_connectors(opts.manifest))
    data = analyze(stage, nap)
    if data["counts"]["sourcePDC"] != 3791 or data["counts"]["distinctExternalEvseIds"] != 3791:
        raise ValueError("Unexpected reference count: fail closed")
    if data["v9PublicationReady"] or data["v9PricedPDC"]:
        raise ValueError("Pricing promotion forbidden")
    dest = Path(opts.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dest, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    report = {key: val for key,val in data.items() if key != "sites"}
    target = Path(opts.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
