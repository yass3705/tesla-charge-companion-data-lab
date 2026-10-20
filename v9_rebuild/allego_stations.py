#!/usr/bin/env python3
"""Run the preserved Allego DXP, normalization and coordinate fallback chain."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

DATA = Path("data/national/allego_direct_stations_france.json.gz")
REPORT = Path("data/reports/allego_station_tariffs_report.json")
SCRIPTS = ("allego_dxp_national.py", "allego_normalize_v8.py", "allego_coordinate_fallbacks_v8.py")


def validate_output(out: Path) -> dict:
    with gzip.open(out / DATA, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    evses = payload.get("evses")
    stations = payload.get("stations")
    counts = payload.get("counts") or {}
    scope = payload.get("scope") or {}
    if (payload.get("dataset") != "allego-direct-operated-evse-france"
            or payload.get("operator") != "Allego" or payload.get("country") != "FR"
            or scope.get("operatorDirectOnly") is not True
            or scope.get("roamingIncluded") is not False
            or scope.get("countryDefaultsAreRankable") is not False
            or not isinstance(evses, list) or not isinstance(stations, list)
            or counts.get("franceEvseCount") != len(evses)
            or counts.get("franceStationCount") != len(stations)
            or counts.get("rankableEvseCount") + counts.get("blockedEvseCount") != len(evses)
            or report.get("counts", {}).get("franceEvseCount") != len(evses)):
        raise ValueError("Allego station contract or accounting invalid")
    ids = [row.get("evseId") for row in evses]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Allego EVSE identity collision")
    by_id = {row["evseId"]: row for row in evses}
    seen = []
    for station in stations:
        if not station.get("stationId") or not isinstance(station.get("evses"), list):
            raise ValueError("Allego station identity invalid")
        for row in station["evses"]:
            evse_id = row.get("evseId")
            if evse_id not in by_id or row != by_id[evse_id]:
                raise ValueError("Allego station/EVSE relation invalid")
            seen.append(evse_id)
    if len(seen) != len(set(seen)) or set(seen) != set(ids):
        raise ValueError("Allego station/EVSE completeness invalid")
    for row in evses:
        if row.get("rankableDirect") and (not isinstance(row.get("directEurPerKwh"), (int, float))
                                         or row.get("blockingReason") is not None
                                         or row.get("isOwnNetwork") is False):
            raise ValueError("Allego rankable EVSE has incomplete tariff")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Allego output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "scripts") + os.pathsep + env.get("PYTHONPATH", "")
    for name in SCRIPTS:
        result = runner([sys.executable, str(ROOT / "scripts" / name)], cwd=out, env=env,
                        capture_output=True, text=True, timeout=3600, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Allego method failed: {name}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
