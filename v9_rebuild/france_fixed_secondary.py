#!/usr/bin/env python3
"""Preserved France secondary parsers with archived-price guard."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/refresh_fixed_tariffs_france_secondary.py")
DATA = tuple(Path("data/operator_direct") / f"{name}.json" for name in (
    "indigo_official_france", "indigo_recharge_official_france",
    "interparking_tariff_rules_france", "seolis_alterbase_tariff_rules_france_2026"))
REPORT = Path("reports/fixed-tariff-refresh-france-secondary-latest.json")


def validate_output(out: Path, seeds: dict[Path, Path] | None = None) -> dict:
    seeds = seeds or {path: ROOT / path for path in DATA}
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = report.get("results")
    if (not isinstance(rows, list) or len(rows) != len(DATA)
            or any(row.get("status") != "unchanged" for row in rows)
            or len({row.get("path") for row in rows}) != len(DATA)):
        raise ValueError("France secondary parser failed or source price changed")
    for path in DATA:
        before = json.loads(seeds[path].read_text(encoding="utf-8"))
        after = json.loads((out / path).read_text(encoding="utf-8"))
        for key in ("refresh", "generatedAt", "retrievedAt", "date"):
            before.pop(key, None)
            after.pop(key, None)
        if before != after:
            raise ValueError("France secondary archived tariff changed")
    history = out / "data/tariff_history"
    if history.exists() and list(history.glob("*.jsonl")):
        raise ValueError("France secondary created price-change history")
    return report


def run(out: Path, *, seeds: dict[Path, Path] | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("France secondary workspace must be off checkout")
    seeds = seeds or {path: ROOT / path for path in DATA}
    for source, dest in ((ROOT / SCRIPT, out / SCRIPT), *((seeds[path], out / path) for path in DATA)):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical France secondary refresh failed")
    validate_output(out, seeds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
