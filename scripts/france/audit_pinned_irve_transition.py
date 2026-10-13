#!/usr/bin/env python3
"""Compare the pinned France identity hub with a newer static IRVE snapshot.

This is an identity audit, not a tariff migration: an offer is never assigned
using coordinates, operator, station name, or power alone.
"""
import argparse
import collections
import gzip
import io
import json
import subprocess
import hashlib
from pathlib import Path


def norm(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def load_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def pinned_rows(repo, ref):
    blob = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{ref}:v9-production-runtime/data/v9/france-static/all.json.gz"]
    )
    return json.load(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(blob)), encoding="utf-8"))


def index(rows):
    by_evse = collections.defaultdict(set)
    by_station = {}
    for row in rows:
        station = norm(row[0])
        by_station[station] = row
        for group in row[8] or []:
            for raw_id in group[6] or []:
                by_evse[norm(raw_id)].add(station)
    return by_evse, by_station


def offers(root, platform):
    folder = root / "data/platforms" / platform
    manifest = json.loads((folder / "manifest.json").read_text())
    for tile in manifest["tiles"]:
        with gzip.open(folder / tile["file"], "rt", encoding="utf-8") as handle:
            yield from json.load(handle).get("emspOffers", [])


def compare_offers(root, platform, old_index, new_index):
    transitions = collections.Counter()
    reparented_unique = 0
    old_only_stations = collections.Counter()
    new_only_stations = collections.Counter()
    ambiguous_examples = []
    for offer in offers(root, platform):
        ids = {norm(value) for value in offer.get("evseIds") or [] if norm(value)}
        old = set().union(*(old_index.get(value, ()) for value in ids)) if ids else set()
        new = set().union(*(new_index.get(value, ()) for value in ids)) if ids else set()
        old_state = "unique" if len(old) == 1 else "absent" if not old else "ambiguous"
        new_state = "unique" if len(new) == 1 else "absent" if not new else "ambiguous"
        transitions[f"{old_state}->{new_state}"] += 1
        if old_state == "unique" and new_state == "absent":
            old_only_stations[next(iter(old))] += 1
        if old_state == "absent" and new_state == "unique":
            new_only_stations[next(iter(new))] += 1
        if old_state == new_state == "unique" and old != new:
            reparented_unique += 1
        if new_state == "ambiguous" and len(ambiguous_examples) < 10:
            ambiguous_examples.append({"offerId": offer.get("id"), "stationIds": sorted(new)})
    return {
        "transitions": dict(sorted(transitions.items())),
        "lostStationCount": len(old_only_stations),
        "restoredStationCount": len(new_only_stations),
        "uniqueOffersWithChangedStationId": reparented_unique,
        "largestLostStations": old_only_stations.most_common(10),
        "largestRestoredStations": new_only_stations.most_common(10),
        "ambiguousExamples": ambiguous_examples,
    }


def belib_missing(root, old_index, new_index):
    catalogue = json.loads((root / "data/national/belib_stations_paris.json").read_text())
    with gzip.open(root / "data/national/france-irve-dynamic-status-v9.json.gz", "rt", encoding="utf-8") as handle:
        dynamic = json.load(handle)
    active = {norm(value) for value in dynamic.get("enServicePdcIds") or []}
    cases = []
    for station in catalogue["stations"]:
        for config in station.get("configurations") or []:
            ids = {norm(value) for value in config.get("roamingEvseIds") or []}
            if not ids or ids & old_index.keys():
                continue
            cases.append({"stationId": station["roamingStationId"], "name": station["name"],
                          "operatorUpdatedAt": station.get("lastUpdated"), "evseIds": sorted(ids),
                          "newStaticExactEvseIds": sorted(ids & new_index.keys()),
                          "newDynamicActiveEvseIds": sorted(ids & active)})
    return {"dynamicGeneratedAt": dynamic.get("generatedAt"), "cases": cases}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stable-repo", type=Path, required=True)
    parser.add_argument("--stable-ref", default="0a6d2c3415504397310d3dc92fae40be843b2435")
    parser.add_argument("--datalab", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    old_rows = pinned_rows(args.stable_repo, args.stable_ref)
    static_path = args.datalab / "data/national/france-irve-static-v9/all.json.gz"
    new_rows = load_rows(static_path)
    old, old_stations = index(old_rows)
    new, new_stations = index(new_rows)
    shared = old.keys() & new.keys()
    changed_station = {key for key in shared if old[key] != new[key]}
    same_place = sum(
        len(old[key]) == len(new[key]) == 1
        and old_stations[next(iter(old[key]))][1:5] == new_stations[next(iter(new[key]))][1:5]
        for key in changed_station
    )
    renamed = sum(old_stations[key][1] != new_stations[key][1] for key in old_stations.keys() & new_stations.keys())
    moved = sum((old_stations[key][3], old_stations[key][4]) !=
                (new_stations[key][3], new_stations[key][4]) for key in old_stations.keys() & new_stations.keys())
    result = {
        "scope": "Pinned Stable FR IRVE versus current Data Lab static FR IRVE; same pinned eMSP overlays",
        "pinnedStableRef": args.stable_ref,
        "newStaticSha256": hashlib.sha256(static_path.read_bytes()).hexdigest(),
        "identityOnly": True,
        "old": {"stations": len(old_rows), "evseIds": len(old)},
        "new": {"stations": len(new_rows), "evseIds": len(new)},
        "stationIdentity": {"retained": len(old_stations.keys() & new_stations.keys()),
                            "oldOnly": len(old_stations.keys() - new_stations.keys()),
                            "newOnly": len(new_stations.keys() - old_stations.keys()),
                            "renamedOnSameId": renamed, "coordinatesChangedOnSameId": moved},
        "evseIdentity": {"retained": len(shared), "oldOnly": len(old.keys() - new.keys()),
                         "newOnly": len(new.keys() - old.keys()),
                         "stationChangedOnSameEvseId": len(changed_station),
                         "sameNameAddressCoordinatesAmongChangedStationId": same_place,
                         "multiStationNew": sum(len(stations) > 1 for stations in new.values())},
        "platforms": {
            "electra": compare_offers(args.datalab, "electra/france", old, new),
            "electroverse": compare_offers(args.datalab, "electroverse/france-evse", old, new),
        },
        "belibAbsentFromPinned": belib_missing(args.datalab, old, new),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
