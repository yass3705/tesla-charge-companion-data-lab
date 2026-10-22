#!/usr/bin/env python3
"""Preserved Spain secondary tariff watchers with fail-closed archived prices."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/refresh_fixed_tariffs_spain_secondary.py")
DATA = tuple(Path("data/operator_direct") / name for name in (
    "emt_madrid_official_spain.json", "endesa_official_spain.json", "plenergy_official_spain.json"))
REPORT = Path("reports/fixed-tariff-refresh-spain-secondary-latest.json")


def validate_output(out: Path, seeds: dict[Path, Path] | None = None) -> dict:
    seeds = seeds or {path: ROOT / path for path in DATA}
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = report.get("results")
    if (not isinstance(rows, list) or len(rows) != 3
            or {row.get("operator"): row.get("status") for row in rows}
            != {"EMT Madrid": "unchanged", "Endesa": "unchanged", "Plenergy": "unchanged"}):
        raise ValueError("Spain secondary source or tariff requires review")
    for path in DATA:
        before = json.loads(seeds[path].read_text(encoding="utf-8"))
        after = json.loads((out / path).read_text(encoding="utf-8"))
        for field in ("refresh", "verifiedAt"):
            before.pop(field, None)
            after.pop(field, None)
        if before != after:
            raise ValueError("Spain secondary archived tariff changed")
    plenergy = next(row for row in rows if row["operator"] == "Plenergy")
    stations = json.loads((out / DATA[2]).read_text(encoding="utf-8"))["stationTariffs"]
    if (plenergy.get("changed") or plenergy.get("failures")
            or len(plenergy.get("checked") or []) != len(stations)
            or len({row.get("station") for row in plenergy["checked"]}) != len(stations)):
        raise ValueError("Spain secondary exact station check incomplete")
    return report


def run(out: Path, *, seeds: dict[Path, Path] | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Spain secondary workspace must be off checkout")
    seeds = seeds or {path: ROOT / path for path in DATA}
    for source, dest in ((ROOT / SCRIPT, out / SCRIPT), *((seeds[path], out / path) for path in DATA)):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Spain secondary refresh failed")
    validate_output(out, seeds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
