#!/usr/bin/env python3
"""Reproduce the dated Belgium exact-gap decision from preserved inputs only."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/belgium_finalize_gap_reconciliation.py")
DETAIL = Path("reports/belgium/belgium-residual-unpriced-detail-v2-2026-09-28.json")
SHELL = Path("data/operator_direct/shell_belgium_official_2026-09-28.json")
FINAL = Path("reports/belgium/belgium-final-gap-reconciliation-2026-09-28.json")


def validate_output(out: Path) -> dict:
    detail = json.loads((out / DETAIL).read_text(encoding="utf-8"))
    shell = json.loads((out / SHELL).read_text(encoding="utf-8"))
    final = json.loads((out / FINAL).read_text(encoding="utf-8"))
    # This is a frozen 2026-09-28 decision, not a live tariff refresh. Equality
    # proves that the preserved script did not introduce an unreviewed price.
    if detail != json.loads((ROOT / DETAIL).read_text(encoding="utf-8")):
        raise ValueError("Belgium archived input changed")
    for path, payload in ((SHELL, shell), (FINAL, final)):
        if payload != json.loads((ROOT / path).read_text(encoding="utf-8")):
            raise ValueError("Belgium archived decision changed")
    items = (detail.get("targets") or {}).get("Shell Recharge", {}).get("items")
    if not isinstance(items, list) or shell.get("country") != "BE" or final.get("country") != "BE":
        raise ValueError("Belgium historical gap schema invalid")
    eligible = [row for row in items if max(row.get("powerW") or [0]) > 50000
                and row.get("externalIdentifiers")]
    entries = shell.get("entries")
    if (not isinstance(entries, list) or shell.get("count") != len(entries)
            or {tuple(row["externalIdentifiers"]) for row in entries}
            != {tuple(row["externalIdentifiers"]) for row in eligible}
            or any(row.get("tariff", {}).get("price") != 0.79
                   or row.get("tariff", {}).get("paymentMethod") != "bankCard"
                   or row.get("tariff", {}).get("currency") != "EUR" for row in entries)):
        raise ValueError("Belgium exact Shell EVSE decision invalid")
    return final


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Belgium archive replay must be off checkout")
    for path in (SCRIPT, DETAIL):
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, target)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out, capture_output=True,
                    text=True, timeout=120, check=False)
    if result.returncode:
        raise RuntimeError("Historical Belgium gap method failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
