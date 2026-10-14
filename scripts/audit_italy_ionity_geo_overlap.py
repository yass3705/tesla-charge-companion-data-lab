#!/usr/bin/env python3
"""Read-only GPS proximity audit: Ionity locations against official PUN stations.

Distances describe station candidates ONLY. Never attach prices to EVSEs.
"""
import argparse
import gzip
import json
import math
import re
import unicodedata
from pathlib import Path
from collections import Counter


def power_counts(value):
    """Discover explicit powerKw fields only; no inferred charging power."""
    result = Counter()
    stack = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            v = node.get("powerKw")
            if v is None:
                v = node.get("maxPowerKw")
            try:
                n = float(v)
                if math.isfinite(n) and n > 0:
                    result[round(n, 3)] += 1
            except (TypeError, ValueError):
                pass
            stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return result


def load(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def distance_m(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(value)))


def location_coords(obj):
    if not isinstance(obj, dict):
        return None
    lat = obj.get("latitude", obj.get("lat"))
    lon = obj.get("longitude", obj.get("lon", obj.get("lng")))
    if (lat is None or lon is None) and isinstance(obj.get("coordinates"), dict):
        return location_coords(obj["coordinates"])
    try:
        result = (float(lat), float(lon))
        if -90 <= result[0] <= 90 and -180 <= result[1] <= 180:
            return result
    except (ValueError, TypeError):
        pass
    return None


def address_key(value):
    if isinstance(value, dict):
        value = " ".join(str(v) for v in value.values() if isinstance(v, (str, int)))
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.findall(r"[a-z0-9]+", value))


def address_matches(a, b):
    a, b = address_key(a), address_key(b)
    return bool(a and b and (a == b or a in b or b in a))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pun", type=Path, required=True)
    parser.add_argument("--ionity", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    pun, source = load(args.pun), load(args.ionity)
    stations = pun.get("stations", [])
    locations = source.get("locations", [])
    if not isinstance(locations, list) or not isinstance(stations, list):
        raise ValueError("Unexpected PUN/Ionity collection")
    pun_geo = []
    for station in stations:
        coords = station.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            try:
                a = (float(coords[0]), float(coords[1]))
                if all(math.isfinite(x) for x in a):
                    pun_geo.append((station, a))
            except (TypeError, ValueError):
                pass
    results = []
    for i, location in enumerate(locations):
        coord = location_coords(location)
        candidates = []
        if coord:
            for station, gps in pun_geo:
                # Cheap bounding-box filter before haversine
                if abs(coord[0]-gps[0]) > .001 or abs(coord[1]-gps[1]) > .002:
                    continue
                dist = distance_m(coord, gps)
                if dist <= 30:
                    candidates.append({"stationId":station.get("stationId") or station.get("stationKey"),
                                       "operator":station.get("operator"),
                                       "operatorIsIonity": "IONITY" in str(station.get("operator") or "").upper(),
                                       "punAddress":station.get("address"),
                                       "distanceM":round(dist, 2),
                                       "evseCount":len(station.get("evses", [])),
                                       "punPowerKw":dict(sorted(power_counts(station.get("evses", [])).items()))})
        candidates.sort(key=lambda c:c["distanceM"])
        ionity_candidates = [c for c in candidates if c["operatorIsIonity"]]
        ionity_powers = power_counts(location)
        matching_address = [c for c in ionity_candidates if address_matches(location.get("address"), c["punAddress"])]
        for c in candidates:
            source_set = set(ionity_powers)
            pun_set = set(float(k) for k in c["punPowerKw"])
            c["powerKwOverlap"] = sorted(source_set & pun_set)
            c["powerComparisonPossible"] = bool(source_set and pun_set)
        category = ("unmatched_30m" if not ionity_candidates else
                    "multiple_ionity_stations" if len(ionity_candidates) > 1 else
                    "unique_operator_address" if len(matching_address) == 1 else
                    "unique_operator_address_review")
        results.append({"ionityIndex":i, "matchClassification":category,
                        "ionityPowerKw":dict(sorted(ionity_powers.items())),
                        "powerEvidenceOnlyNotEvseTariffCertified":True,
                        "matchingIonityAddresses":len(matching_address), "city":location.get("city"),
                        "postalCode":location.get("postalCode"),
                        "address":location.get("address"),
                        "hasCoordinates":coord is not None,
                        "candidates5m":sum(c["distanceM"] <= 5 for c in candidates),
                        "candidates10m":sum(c["distanceM"] <= 10 for c in candidates),
                        "candidates30m":len(candidates),
                        "ionityOperatorCandidates30m":len(ionity_candidates),
                        "uniqueIonityOperatorCandidate30m":len(ionity_candidates) == 1,
                        "requiresAddressAndPowerReview":True,
                        "candidateStations":candidates[:8]})
    report = {"country":"IT","cpo":"IONITY","mode":"read-only-station-proximity",
              "punStationCount":len(stations),"ionityLocationCount":len(locations),
              "counts":{"withCoordinates":sum(x["hasCoordinates"] for x in results),
                        "uniqueWithin5m":sum(x["candidates5m"] == 1 for x in results),
                        "uniqueWithin10m":sum(x["candidates10m"] == 1 for x in results),
                        "uniqueWithin30m":sum(x["candidates30m"] == 1 for x in results),
                        "ambiguousWithin30m":sum(x["candidates30m"] > 1 for x in results),
                        "unmatchedWithin30m":sum(x["candidates30m"] == 0 for x in results),
                        "uniqueIonityOperatorWithin30m":sum(x["uniqueIonityOperatorCandidate30m"] for x in results),
                        "noIonityOperatorCandidateWithin30m":sum(x["ionityOperatorCandidates30m"] == 0 for x in results)},
              "classificationCounts":{k:sum(x["matchClassification"] == k for x in results) for k in sorted(set(x["matchClassification"] for x in results))},
              "stations":results,"evseTariffMatchesCertified":False,
              "readyForProductionSwitch":False}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report["counts"],indent=2))


if __name__ == "__main__":
    main()
