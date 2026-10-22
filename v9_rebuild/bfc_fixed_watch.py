#!/usr/bin/env python3
"""Preserved BFC semantic watches and SIED70 parser on isolated last-good files."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/refresh_fixed_tariffs_bfc.py")
DATA = tuple(Path("data/operator_direct") / f"{name}.json" for name in (
    "siceco_cotedor_official", "sieeen_nievre_official", "sdey_official_yonne",
    "tde90_belfort_official", "syded_doubs_official", "sied70_official_haute_saone"))
REPORT = Path("reports/fixed-tariff-refresh-bfc-latest.json")


def validate_output(out: Path, seeds: dict[Path, Path] | None = None) -> dict:
    seeds = seeds or {path: ROOT / path for path in DATA}
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = report.get("results")
    if (not isinstance(rows, list) or len(rows) != len(DATA)
            or any(row.get("status") != "unchanged" for row in rows)
            or len({row.get("operator") for row in rows}) != len(DATA)):
        raise ValueError("BFC source context or parser requires review")
    for path in DATA:
        before = json.loads(seeds[path].read_text(encoding="utf-8"))
        after = json.loads((out / path).read_text(encoding="utf-8"))
        for key in ("refresh", "generatedAt"):
            before.pop(key, None)
            after.pop(key, None)
        if before != after:
            raise ValueError("BFC archived tariff changed")
    return report


def run(out: Path, *, seeds: dict[Path, Path] | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("BFC workspace must be off checkout")
    seeds = seeds or {path: ROOT / path for path in DATA}
    for source, dest in ((ROOT / SCRIPT, out / SCRIPT), *((seeds[path], out / path) for path in DATA)):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical BFC fixed tariff method failed")
    validate_output(out, seeds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
