#!/usr/bin/env python3
"""Run the two preserved Bump national inventory methods in isolated staging."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT


INVENTORY = Path("data/national/bump_direct_inventory_france.json.gz")
STATIONS = Path("data/national/bump_direct_stations_france.json.gz")
REPORTS = (Path("reports/bump_direct_inventory_france.md"),
           Path("data/reports/bump_direct_tariffs_report.json"))


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Bump output is not an object: {path}")
    return payload


def validate_output(out: Path) -> dict[str, dict]:
    inventory = read_gzip(out / INVENTORY)
    stations = read_gzip(out / STATIONS)
    if (inventory.get("dataset") != "bump-direct-operated-stations-france-inventory"
            or inventory.get("operator") != "Bump" or inventory.get("country") != "FR"
            or not isinstance(inventory.get("stations"), list)
            or not inventory.get("source", {}).get("resourceSha256")):
        raise ValueError("Bump official inventory contract invalid")
    if (stations.get("operator") != "Bump" or stations.get("country") != "FR"
            or not isinstance(stations.get("stations"), list)
            or stations.get("source", {}).get("resourceId") is None):
        raise ValueError("Bump tabular station contract invalid")
    if inventory.get("counts", {}).get("stationCount") != len(inventory["stations"]):
        raise ValueError("Bump inventory station relation mismatch")
    if inventory.get("counts", {}).get("pointCount") != sum(len(row.get("points", [])) for row in inventory["stations"]):
        raise ValueError("Bump inventory point relation mismatch")
    if stations.get("counts", {}).get("franceStationCount") != len(stations["stations"]):
        raise ValueError("Bump tabular station relation mismatch")
    if stations.get("counts", {}).get("franceEvseCount") != sum(len(row.get("evses", [])) for row in stations["stations"]):
        raise ValueError("Bump tabular EVSE relation mismatch")
    ids = [row.get("stationKey") for row in inventory["stations"]]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Bump inventory station identity collision")
    ids = [row.get("stationId") for row in stations["stations"]]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Bump tabular station identity collision")
    if any(not path.is_file() for path in (out / REPORTS[0], out / REPORTS[1])):
        raise ValueError("Bump technical report missing")
    report = json.loads((out / REPORTS[1]).read_text(encoding="utf-8"))
    if report.get("counts") != stations["counts"]:
        raise ValueError("Bump tabular report differs from dataset")
    return {"inventory": inventory, "stations": stations}


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Bump output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    for script in ("bump_direct_inventory.py", "bump_direct_station_tariffs.py"):
        result = runner([sys.executable, str(ROOT / "scripts" / script)], cwd=out,
                        capture_output=True, text=True, timeout=1800, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Bump method failed: {script}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
