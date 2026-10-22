#!/usr/bin/env python3
"""Run the preserved France fixed-tariff watch against isolated last-good files."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/refresh_fixed_tariffs_france_watch.py")
DATA = tuple(Path("data/operator_direct") / name for name in (
    "dream_energy_promotional_tariff_france_2026.json",
    "soregies_tariff_rules_france_2026.json",
    "mobive_official_france.json"))
REPORT = Path("reports/fixed-tariff-refresh-france-watch-latest.json")


def validate_output(out: Path, seeds: dict[Path, Path] | None = None) -> dict:
    seeds = seeds or {item: ROOT / item for item in DATA}
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("France fixed watch report incomplete")
    expected = {"Dream Energy": "unchanged", "Sorégies Mobilités": "unchanged", "Mobive": "unchanged"}
    if {row.get("operator"): row.get("status") for row in rows} != expected:
        raise ValueError("France fixed watch needs source or price review")
    for relative in DATA:
        before = json.loads(seeds[relative].read_text(encoding="utf-8"))
        after = json.loads((out / relative).read_text(encoding="utf-8"))
        before.pop("refresh", None)
        after.pop("refresh", None)
        if before != after:
            raise ValueError("France fixed watch altered archived tariff values")
    return report


def run(out: Path, *, seeds: dict[Path, Path] | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("France fixed watch workspace must be off checkout")
    seeds = seeds or {item: ROOT / item for item in DATA}
    for source, target in ((ROOT / SCRIPT, out / SCRIPT),
                           *((seeds[item], out / item) for item in DATA)):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical France fixed watch failed")
    validate_output(out, seeds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
