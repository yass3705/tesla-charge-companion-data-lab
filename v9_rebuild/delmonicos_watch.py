#!/usr/bin/env python3
"""Isolate the preserved Delmonicos semantic watch without changing tariff values."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/refresh_fixed_tariffs_france_delmonicos.py")
DATA = Path("data/operator_direct/delmonicos_direct_france_20261001.json")
REPORT = Path("reports/fixed-tariff-refresh-france-delmonicos-latest.json")


def validate_output(out: Path, seed: Path = ROOT / DATA) -> dict:
    before = json.loads(seed.read_text(encoding="utf-8"))
    after = json.loads((out / DATA).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    old = dict(before)
    new = dict(after)
    old.pop("refresh", None)
    new.pop("refresh", None)
    entries = report.get("sources")
    mapped = (after.get("directMapped") or {}).get("stations") or []
    if (old != new or after.get("country") != "FR" or not isinstance(entries, list)
            or len(entries) != 2 or {item.get("url") for item in entries} != set(before["refresh"]["sourceHashes"])
            or any(item.get("status") != "unchanged" for item in entries)
            or after.get("refresh", {}).get("lastResult") != "validated"
            or any((station.get("directTariff") or {}).get("energyEurPerKwh")
                   != report.get("delmonicosOrneTariffEurPerKwh") for station in mapped)
            or report.get("resolvedStations") != len((after.get("directMapped") or {}).get("stations") or [])
               + len((after.get("migratedFreshmileHomecourt") or {}).get("stations") or [])):
        raise ValueError("Delmonicos source changed or preserved tariff altered")
    return after


def run(out: Path, *, seed: Path = ROOT / DATA, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Delmonicos workspace must be off checkout")
    for source, target in ((ROOT / SCRIPT, out / SCRIPT), (seed, out / DATA)):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Delmonicos watch failed")
    validate_output(out, seed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
