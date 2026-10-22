#!/usr/bin/env python3
"""Run the preserved Spain core parsers with archived-price publication guard."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/refresh_fixed_tariffs_spain_core.py")
DATA = tuple(Path("data/operator_direct") / f"{name}_official_spain.json" for name in
             ("repsol", "eranovum", "wenea", "zunder", "acciona"))
REPORT = Path("reports/fixed-tariff-refresh-spain-latest.json")


def validate_output(out: Path, seeds: dict[Path, Path] | None = None) -> dict:
    seeds = seeds or {path: ROOT / path for path in DATA}
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = report.get("results")
    if (not isinstance(rows, list) or len(rows) != len(DATA)
            or {row.get("operator"): row.get("status") for row in rows}
            != {"Repsol": "unchanged", "Eranovum": "unchanged", "Wenea": "unchanged",
                "Zunder": "unchanged", "ACCIONA": "unchanged"}):
        raise ValueError("Spain core source failed or tariff changed")
    for path in DATA:
        before = json.loads(seeds[path].read_text(encoding="utf-8"))
        after = json.loads((out / path).read_text(encoding="utf-8"))
        for key in ("refresh", "verifiedAt"):
            before.pop(key, None)
            after.pop(key, None)
        if before != after:
            raise ValueError("Spain core archived tariff changed")
    history = out / "data/tariff_history"
    if history.exists() and list(history.glob("*.jsonl")):
        raise ValueError("Spain core created a price-change history")
    return report


def run(out: Path, *, seeds: dict[Path, Path] | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Spain core workspace must be off checkout")
    seeds = seeds or {path: ROOT / path for path in DATA}
    for source, dest in ((ROOT / SCRIPT, out / SCRIPT), *((seeds[path], out / path) for path in DATA)):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Spain core refresh failed")
    validate_output(out, seeds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
