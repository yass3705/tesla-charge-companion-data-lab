#!/usr/bin/env python3
"""Read-only GPS proximity audit: Ionity locations against official PUN stations.

Distances describe station candidates ONLY. Never attach prices to EVSEs.
"""
import argparse
import gzip
import json
import math
from pathlib import Path


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
                                       "evseCount":len(station.get("evses", []))})
        candidates.sort(key=lambda c:c["distanceM"])
        ionity_candidates = [c for c in candidates if c["operatorIsIonity"]]
        results.append({"ionityIndex":i, "city":location.get("city"),
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
              "stations":results,"evseTariffMatchesCertified":False,
              "readyForProductionSwitch":False}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report["counts"],indent=2))


if __name__ == "__main__":
    main()
