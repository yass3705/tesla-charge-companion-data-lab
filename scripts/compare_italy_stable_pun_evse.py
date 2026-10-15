#!/usr/bin/env python3
"""Read-only EVSE/power delta between pinned Stable Italy and PUN compact candidate.

This reports identities and technical coverage only. It never joins or assigns prices.
"""
import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def stable_inventory(rows):
    result = defaultdict(lambda: {"stations": set(), "powersKw": set()})
    for station in rows:
        for group in station[8]:
            evse = str(group[0]).strip()
            if evse:
                result[evse]["stations"].add(str(station[0]))
                result[evse]["powersKw"].add(round(float(group[3]), 6))
    return result


def candidate_inventory(rows):
    result = defaultdict(lambda: {"stations": set(), "powersKw": set()})
    for station in rows:
        for group in station[8]:
            # PUN compact groups retain exact EVSE IDs in slot 6. Group IDs are
            # connector IDs and must never be treated as physical EVSE aliases.
            for evse in group[6]:
                result[str(evse)]["stations"].add(str(station[0]))
                result[str(evse)]["powersKw"].add(round(float(group[3]), 6))
    return result


def pun_inventory(pun):
    result = {}
    for evse in pun.get("evses", []):
        eid = str(evse.get("evseId") or "").strip()
        if not eid:
            continue
        supported = []
        for connector in evse.get("connectors") or []:
            standard = str(connector.get("standard") or "").upper()
            if "COMBO" in standard or "CCS" in standard or "TYPE_2" in standard or "TYPE2" in standard or standard == "IEC_62196_T2":
                power = connector.get("maxPowerKw")
                if isinstance(power, (int, float)) and power > 0:
                    supported.append(round(float(power), 6))
        result[eid] = {"station": str(evse.get("stationId") or ""),
                       "supportedPowersKw": sorted(set(supported))}
    return result


def compare(stable, candidate, pun):
    old, new = set(stable), set(candidate)
    lost = []
    for eid in sorted(old - new):
        source = pun.get(eid)
        reason = ("absent_from_pun" if source is None else
                  "pun_has_no_supported_powered_connector" if not source["supportedPowersKw"] else
                  "present_in_pun_but_missing_from_compact")
        lost.append({"evseId": eid, "reason": reason,
                     "stableStations": sorted(stable[eid]["stations"]),
                     "stablePowersKw": sorted(stable[eid]["powersKw"]),
                     "punStation": source["station"] if source else None,
                     "punSupportedPowersKw": source["supportedPowersKw"] if source else []})
    changed_power = [
        {"evseId": eid, "stablePowersKw": sorted(stable[eid]["powersKw"]),
         "candidatePowersKw": sorted(candidate[eid]["powersKw"])}
        for eid in sorted(old & new) if stable[eid]["powersKw"] != candidate[eid]["powersKw"]
    ]
    moved_station = [
        {"evseId": eid, "stableStations": sorted(stable[eid]["stations"]),
         "candidateStations": sorted(candidate[eid]["stations"])}
        for eid in sorted(old & new) if stable[eid]["stations"] != candidate[eid]["stations"]
    ]
    counts = {reason: sum(x["reason"] == reason for x in lost) for reason in
              ("absent_from_pun", "pun_has_no_supported_powered_connector", "present_in_pun_but_missing_from_compact")}
    return {"stableEvseIds": len(old), "candidateEvseIds": len(new),
            "sharedExactEvseIds": len(old & new), "stableOnlyEvseIds": len(lost),
            "candidateOnlyEvseIds": len(new - old), "stableOnlyReasons": counts,
            "sharedEvsePowerDifferences": len(changed_power),
            "sharedEvseStationDifferences": len(moved_station),
            "stableOnly": lost, "candidateOnly": sorted(new - old),
            "powerDifferences": changed_power, "stationDifferences": moved_station,
            "tariffParityCertified": False, "readyForProductionSwitch": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stable", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--pun", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = compare(stable_inventory(load(args.stable)),
                     candidate_inventory(load(args.candidate)),
                     pun_inventory(load(args.pun)))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, indent=2))


if __name__ == "__main__":
    main()
