#!/usr/bin/env python3
"""Fill rare missing Allego station coordinates from Allego's own station pages.

The primary geometry source remains Allego's official IRVE publication. This file
contains only explicit, auditable operator-page fallbacks for stations whose IRVE
rows omit coordinates. Never geocode an address heuristically here.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

DATA = Path("data/national/allego_direct_stations_france.json.gz")

OFFICIAL_FALLBACKS = {
    "FRSITE00000325": {
        "coordinates": [47.779187, -3.342502],
        "name": "Rue Michael Faraday LANESTER",
        "addressContains": "michael faraday",
        "evseIds": {
            "FRALLEGO6001471",
            "FRALLEGO6001472",
            "FRALLEGO6001481",
            "FRALLEGO6001482",
        },
        "source": "https://www.allego.eu/charging-station/rue-michael-faraday-lanester/",
        "sourceDetail": "Official Allego station page Take-me-there map target",
    },
}


def normalize(value: object) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").split())


def main() -> None:
    payload = json.loads(gzip.decompress(DATA.read_bytes()))
    stations = payload.get("stations") or []
    applied = []

    by_id = {str(st.get("stationId") or ""): st for st in stations}
    for station_id, fallback in OFFICIAL_FALLBACKS.items():
        station = by_id.get(station_id)
        if station is None:
            raise RuntimeError(f"Expected Allego station missing for coordinate fallback: {station_id}")
        if station.get("coordinates"):
            continue

        address = normalize(station.get("irveAddress") or station.get("address"))
        if fallback["addressContains"] not in address:
            raise RuntimeError(f"Coordinate fallback address mismatch for {station_id}: {address!r}")
        actual_evses = {str(row.get("evseId") or "") for row in station.get("evses") or []}
        if actual_evses != fallback["evseIds"]:
            raise RuntimeError(
                f"Coordinate fallback EVSE mismatch for {station_id}: "
                f"expected={sorted(fallback['evseIds'])}, actual={sorted(actual_evses)}"
            )

        station["coordinates"] = list(fallback["coordinates"])
        station["coordinatesSource"] = "allego-official-station-page"
        station["coordinatesSourceUrl"] = fallback["source"]
        station["coordinatesSourceDetail"] = fallback["sourceDetail"]
        applied.append(station_id)

    actual_with_coords = sum(
        1 for station in stations
        if isinstance(station.get("coordinates"), list) and len(station["coordinates"]) >= 2
    )
    payload.setdefault("counts", {})["stationsWithCoordinates"] = actual_with_coords
    payload.setdefault("sources", {})["officialCoordinateFallbacks"] = {
        station_id: fallback["source"] for station_id, fallback in OFFICIAL_FALLBACKS.items()
    }
    payload["coordinateFallbacksApplied"] = applied

    rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    DATA.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))
    print(json.dumps({
        "officialCoordinateFallbacksApplied": applied,
        "stationsWithCoordinates": actual_with_coords,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
