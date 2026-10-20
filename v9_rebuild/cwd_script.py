#!/usr/bin/env python3
"""Run preserved scripts that write relative paths in an isolated directory."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

METHODS = {
    "etotem_inventory": ("scripts/etotem_direct_station_inventory.py", "data/national/etotem_direct_stations_france.json.gz"),
}


def validate_output(out: Path, method: str) -> dict:
    if method not in METHODS:
        raise ValueError("Unsupported relative-output method")
    with gzip.open(out / METHODS[method][1], "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    stations = payload.get("stations") or []
    ids = [row.get("stationId") for row in stations]
    if (payload.get("schemaVersion") != "1.0.0" or payload.get("operator") != "e-Totem"
            or payload.get("country") != "FR"
            or payload.get("scope", {}).get("physicalCpoDirectOnly") is not True
            or payload.get("scope", {}).get("roamingIncluded") is not False
            or not isinstance(payload.get("sourceDatasets"), list)
            or payload.get("counts", {}).get("stationCount") != len(stations)
            or any(not x for x in ids) or len(ids) != len(set(ids))
            or payload.get("counts", {}).get("pdcCount") != sum(len(row.get("pdcs") or []) for row in stations)
            or any(row.get("pdcCount") != len(row.get("pdcs") or []) for row in stations)):
        raise ValueError("e-Totem technical contract invalid")
    return payload


def run(out: Path, method: str, *, runner=subprocess.run) -> None:
    if method not in METHODS:
        raise ValueError("Unsupported relative-output method")
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Relative-output method must run outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(ROOT / METHODS[method][0])],
                    cwd=out, capture_output=True, text=True, timeout=1200, check=False)
    if result.returncode:
        raise RuntimeError(f"Historical {method} method failed")
    validate_output(out, method)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=sorted(METHODS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.method)


if __name__ == "__main__":
    main()
