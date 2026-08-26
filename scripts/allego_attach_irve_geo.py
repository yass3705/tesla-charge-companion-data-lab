#!/usr/bin/env python3
"""Attach official France IRVE coordinates/identifiers to Allego station records."""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

DATA_GOUV_URL = "https://www.data.gouv.fr/fr/datasets/r/6523db3c-05f2-4c61-9308-e53a92deab37"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"


def norm_evse(row: dict) -> str:
    for key in ("id_pdc_itinerance", "id_pdc_local", "id_pdc"):
        value = str(row.get(key) or "").upper().strip().replace("*", "")
        match = re.search(r"FRALLEGO[0-9A-Z_-]+", value)
        if match:
            return match.group(0)
    return ""


def parse_coords(row: dict):
    for lat_key, lon_key in (
        ("consolidated_latitude", "consolidated_longitude"),
        ("latitude", "longitude"),
    ):
        try:
            lat = float(str(row.get(lat_key) or "").replace(",", "."))
            lon = float(str(row.get(lon_key) or "").replace(",", "."))
            if 41 <= lat <= 52 and -6 <= lon <= 11:
                return [lat, lon]
        except Exception:
            pass
    raw = str(row.get("coordonneesXY") or row.get("coordonnees_xy") or "").strip()
    if raw:
        try:
            pair = json.loads(raw)
            if isinstance(pair, list) and len(pair) >= 2:
                a, b = float(pair[0]), float(pair[1])
                if 41 <= b <= 52 and -6 <= a <= 11:
                    return [b, a]
                if 41 <= a <= 52 and -6 <= b <= 11:
                    return [a, b]
        except Exception:
            nums = re.findall(r"-?\d+(?:[.,]\d+)?", raw)
            if len(nums) >= 2:
                a, b = (float(x.replace(",", ".")) for x in nums[:2])
                if 41 <= b <= 52 and -6 <= a <= 11:
                    return [b, a]
                if 41 <= a <= 52 and -6 <= b <= 11:
                    return [a, b]
    return None


def fetch_rows() -> list[dict]:
    req = urllib.request.Request(DATA_GOUV_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read().decode("utf-8-sig", "replace")
    dialect = csv.Sniffer().sniff(raw[:10000], delimiters=",;\t")
    return list(csv.DictReader(io.StringIO(raw), dialect=dialect))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("data/national/allego_direct_stations_france.json.gz"))
    args = parser.parse_args()

    payload = json.loads(gzip.decompress(args.path.read_bytes()))
    rows = fetch_rows()
    by_evse: dict[str, dict] = {}
    for row in rows:
        evse = norm_evse(row)
        if not evse:
            continue
        by_evse[evse] = {
            "coordinates": parse_coords(row),
            "stationId": str(row.get("id_station_itinerance") or row.get("id_station_local") or "").strip(),
            "stationName": str(row.get("nom_station") or "").strip(),
            "address": str(row.get("adresse_station") or "").strip(),
            "operator": str(row.get("nom_operateur") or "").strip(),
        }

    geo_stations = 0
    linked_evses = 0
    for station in payload.get("stations", []):
        meta = []
        for evse in station.get("evses", []):
            item = by_evse.get(str(evse.get("evseId") or "").upper())
            if item:
                linked_evses += 1
                meta.append(item)
        coords = [tuple(item["coordinates"]) for item in meta if item.get("coordinates")]
        if coords:
            # Official rows for one station normally share coordinates. Mode is
            # more robust than an average when one EVSE row is malformed.
            lat, lon = Counter(coords).most_common(1)[0][0]
            station["coordinates"] = [lat, lon]
            geo_stations += 1
        station["irveStationIds"] = sorted({item["stationId"] for item in meta if item.get("stationId")})
        station["dataGouvEvseIds"] = sorted({str(e.get("evseId") or "") for e in station.get("evses", []) if str(e.get("evseId") or "").upper() in by_evse})
        addresses = [item["address"] for item in meta if item.get("address")]
        if addresses:
            station["irveAddress"] = Counter(addresses).most_common(1)[0][0]

    payload.setdefault("counts", {})["irveLinkedEvseCount"] = linked_evses
    payload["counts"]["stationsWithCoordinates"] = geo_stations
    payload.setdefault("sources", {})["officialIrveGeo"] = DATA_GOUV_URL
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    args.path.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))
    print(f"IRVE Allego geo attached: stationsWithCoordinates={geo_stations} linkedEVSE={linked_evses}")


if __name__ == "__main__":
    main()
