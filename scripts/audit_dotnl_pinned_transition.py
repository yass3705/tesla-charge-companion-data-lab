#!/usr/bin/env python3
"""Report exact DOT-NL identity and priced-configuration transitions between pins."""
import argparse
import collections
import gzip
import io
import json
import subprocess
from pathlib import Path


SOURCE = "data/national/netherlands_dotnl/runtime/all.json.gz"
NORMALIZED_SOURCE = "data/national/netherlands_dotnl/normalized.json.gz"


def source_json(repo, ref, path):
    blob = subprocess.check_output(["git", "-C", str(repo), "show", f"{ref}:{path}"])
    return json.load(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(blob)), encoding="utf-8"))


def priced_count(station):
    return sum(bool(group[5]) for group in station[8] or [])


def identity(station):
    return (round(station[3], 5), round(station[4], 5), station[5], station[1])


def summary(repo, old_ref, new_ref):
    old_rows = source_json(repo, old_ref, SOURCE)
    new_rows = source_json(repo, new_ref, SOURCE)
    normalized = source_json(repo, new_ref, NORMALIZED_SOURCE)
    normalized_ids = {station["stationId"] for station in normalized["stations"]}
    if len(normalized_ids) != len(normalized["stations"]):
        raise ValueError("Duplicate station IDs in new normalized DOT-NL source")
    old = {row[0]: row for row in old_rows}
    new = {row[0]: row for row in new_rows}
    if len(old) != len(old_rows) or len(new) != len(new_rows):
        raise ValueError("Duplicate DOT-NL station IDs in a pin")
    old_only, new_only = old.keys() - new.keys(), new.keys() - old.keys()
    replacements = collections.defaultdict(list)
    for station_id in new_only:
        station = new[station_id]
        replacements[identity(station)].append(station)
    lost_priced, exact_place_candidates, unresolved = [], [], []
    for station_id in sorted(old_only):
        station = old[station_id]
        count = priced_count(station)
        if not count:
            continue
        record = {"oldStationId": station_id, "name": station[1], "operator": station[5],
                  "latitude": station[3], "longitude": station[4], "lastSourceStatus": station[10],
                  "oldPricedConfigurationCount": count}
        lost_priced.append(record)
        matches = replacements.get(identity(station), [])
        if len(matches) == 1 and priced_count(matches[0]):
            exact_place_candidates.append({**record, "newStationId": matches[0][0],
                                           "newPricedConfigurationCount": priced_count(matches[0]),
                                           "decision": "new source has its own price; do not copy old rate"})
        else:
            unresolved.append({**record, "candidateCountAtExactNameOperatorCoordinates": len(matches)})
    old_config = sum(len(row[8] or []) for row in old_rows)
    new_config = sum(len(row[8] or []) for row in new_rows)
    old_priced = sum(priced_count(row) for row in old_rows)
    new_priced = sum(priced_count(row) for row in new_rows)
    return {
        "oldRef": old_ref, "newRef": new_ref, "sourcePath": SOURCE,
        "newNormalizedSourcePath": NORMALIZED_SOURCE,
        "newNormalizedGeneratedAt": normalized.get("generatedAt"),
        "method": "exact station ID, then diagnostic same name/operator/coordinates; no tariff migration",
        "counts": {"oldStations": len(old), "newStations": len(new),
                   "retainedStationIds": len(old.keys() & new.keys()),
                   "oldOnlyStationIds": len(old_only), "newOnlyStationIds": len(new_only),
                   "oldConfigurations": old_config, "newConfigurations": new_config,
                   "oldPricedConfigurations": old_priced, "newPricedConfigurations": new_priced,
                   "oldOnlyPricedStations": len(lost_priced),
                   "oldOnlyPricedConfigurations": sum(x["oldPricedConfigurationCount"] for x in lost_priced),
                   "diagnosticRekeyCandidatesWithNewPrices": len(exact_place_candidates),
                   "unresolvedOldPricedStations": len(unresolved),
                   "unresolvedOldPricedIdsInNewNormalizedSource": sum(
                       row["oldStationId"] in normalized_ids for row in unresolved)},
        "unresolvedStatusCounts": dict(sorted(collections.Counter(x["lastSourceStatus"] for x in unresolved).items())),
        "unresolvedOperatorCounts": dict(sorted(collections.Counter(x["operator"] for x in unresolved).items())),
        "diagnosticRekeyCandidates": exact_place_candidates,
        "unresolvedOldPricedStations": unresolved,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--old-ref", default="047e1911a5dfd4dcce741ad9b461c6096effb9cd")
    parser.add_argument("--new-ref", default="2cc230af128b316bf980d9e7cd7fc5408301b6a4")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summary(args.repo, args.old_ref, args.new_ref)
    data = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data)
    else:
        print(data)


if __name__ == "__main__":
    main()
