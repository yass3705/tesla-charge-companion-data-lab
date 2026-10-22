#!/usr/bin/env python3
"""Apply only archived exact residual and restricted-access Plenitude rules."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.cwd_script import validate_output as validate_initial
from v9_rebuild.electroverse import ROOT

DATA = Path("data/switzerland/plenitude-official-direct-tariffs.json")
REPORT = Path("docs/switzerland-plenitude-finalization-2026-09-28.json")
CONTEXT = Path("docs/switzerland-plenitude-residual-national-context-2026-09-28.json")
ATLAS = Path("data/switzerland/pln-direct-tariffs.json")
INITIAL = Path("inputs/plenitude-initial.json")
SCRIPTS = ("close_swiss_plenitude_known_residuals.py",
           "close_swiss_plenitude_restricted_residuals.py")


def validate_output(out: Path) -> dict:
    initial = json.loads((out / INITIAL).read_text(encoding="utf-8"))
    payload = json.loads((out / DATA).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    context = json.loads((out / CONTEXT).read_text(encoding="utf-8"))
    rows, unresolved, restricted = (payload.get(key) for key in
                                    ("evses", "unresolved", "classifiedNoPublicDirectTariff"))
    if not all(isinstance(group, list) for group in (rows, unresolved, restricted)):
        raise ValueError("Swiss Plenitude closeout lists missing")
    old_rows = {row["evseId"]: row for row in initial["evses"]}
    old_unresolved = {row["evseId"]: row for row in initial["unresolved"]}
    ids = [row.get("evseId") for group in (rows, unresolved, restricted) for row in group]
    counts = payload.get("counts") or {}
    if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
            or payload.get("operatorId") != "CH*PLN"
            or any(not value or not value.startswith("CH*PLN*E") for value in ids)
            or len(ids) != len(set(ids))
            or set(ids) != set(old_rows) | set(old_unresolved)
            or counts.get("nationalEvseCount") != len(ids)
            or counts.get("pricedEvseCount") != len(rows)
            or counts.get("classifiedNoPublicDirectTariffCount") != len(restricted)
            or counts.get("unresolvedEvseCount") != len(unresolved)
            or report.get("nationalEvseCount") != len(ids)
            or report.get("pricedEvseCount") != len(rows)
            or report.get("classifiedNoPublicDirectTariffCount") != len(restricted)
            or report.get("unresolvedEvseCount") != len(unresolved)
            or report.get("status") != ("complete" if not unresolved else "partial")
            or any(row != old_rows[row["evseId"]] for row in rows if row["evseId"] in old_rows)
            or any(row != old_unresolved[row["evseId"]] for row in unresolved)
            or any(row["evseId"] not in old_unresolved or row.get("currency") != "CHF"
                   or not isinstance(row.get("pricePerKwh"), (int, float))
                   or not row.get("connectorEvidenceUrl") for row in rows
                   if row["evseId"] not in old_rows)
            or any(row["evseId"] not in old_unresolved
                   or (context.get(row["evseId"]) or {}).get("Accessibility") != "Restricted access"
                   or (context.get(row["evseId"]) or {}).get("AuthenticationModes")
                   for row in restricted)):
        raise ValueError("Swiss Plenitude exact price or restricted scope invalid")
    return payload


def run(out: Path, source: Path, *, runner=subprocess.run) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents:
        raise ValueError("Swiss Plenitude closeout must run outside checkout")
    validate_initial(source, "swiss_plenitude")
    for relative in (DATA, REPORT, ATLAS):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    target = out / CONTEXT
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / CONTEXT, target)
    initial = out / INITIAL
    initial.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / DATA, initial)
    for name in SCRIPTS:
        script = out / "scripts" / name
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts" / name, script)
        result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                        text=True, timeout=300, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Swiss Plenitude closeout failed: {name}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.source)


if __name__ == "__main__":
    main()
