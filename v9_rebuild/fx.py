#!/usr/bin/env python3
"""Run preserved FX updater with prior rates in isolated staging."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

RATES = Path("data/fx/exchange_rates.json")
META = Path("data/fx/metadata.json")


def validate_output(out: Path) -> dict:
    rates = json.loads((out / RATES).read_text(encoding="utf-8"))
    meta = json.loads((out / META).read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "scripts"))
    from update_fx import SUPPORTED
    values = rates.get("rates") or {}
    if (rates.get("base") != "EUR" or values.get("EUR") != 1.0
            or set(values) != set(SUPPORTED)
            or any(not isinstance(values[code], (int, float)) or values[code] <= 0 for code in SUPPORTED)
            or not rates.get("date") or not rates.get("checkedAt") or not rates.get("source")
            or meta.get("fxUpdated") != rates["date"]
            or meta.get("fxCheckedAt") != rates["checkedAt"]
            or meta.get("fxSource") != rates["source"]):
        raise ValueError("FX technical contract invalid")
    return rates


def run(out: Path, *, source: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("FX output must be outside checkout")
    (out / RATES).parent.mkdir(parents=True, exist_ok=True)
    if source is not None:
        validate_output(source)
    for relative in (RATES, META):
        shutil.copy2((source or ROOT) / relative, out / relative)
    result = runner([sys.executable, str(ROOT / "scripts/update_fx.py")],
                    cwd=out, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode:
        raise RuntimeError("Historical FX updater failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    run(args.out, source=args.source)


if __name__ == "__main__":
    main()
