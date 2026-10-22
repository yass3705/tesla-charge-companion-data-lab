#!/usr/bin/env python3
"""Apply only archived two-EVSE PowerUp direct-page closeout to signed state."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT
from v9_rebuild.swiss_powerup import DATA, REPORT, validate_output as validate_initial

SCRIPT = Path("scripts/close_powerup_residuals.py")
INITIAL = Path("inputs/powerup-initial.json")
TARGETS = {"CH*POW*E137808", "CH*POW*E137809"}


def validate_output(out: Path) -> dict:
    initial = json.loads((out / INITIAL).read_text(encoding="utf-8"))
    payload = json.loads((out / DATA).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    original = {row["evseId"]: row for row in initial["evses"]}
    rows = payload.get("evses")
    missing = payload.get("missingCurrentEvseIds")
    resolved = payload.get("resolvedByDirectPageEvidence")
    if not all(isinstance(value, list) for value in (rows, missing, resolved)):
        raise ValueError("Swiss PowerUp closeout lists missing")
    current = {row["evseId"]: row for row in rows}
    old_missing = set(initial["missingCurrentEvseIds"])
    additions = set(current) - set(original)
    counts = payload.get("counts") or {}
    priced = [row for row in rows if any(row.get(key) is not None for key in
              ("pricePerKwh", "pricePerMinute", "startFee", "idleFee"))]
    if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
            or payload.get("operatorId") != "CH*POW"
            or len(rows) != len(current) or len(resolved) != len(set(resolved))
            or set(resolved) != additions or not additions <= TARGETS & old_missing
            or set(missing) != old_missing - additions
            or set(current) | set(missing) != set(initial["nationalSourceEvseIds"])
            or any(current[eid] != row for eid, row in original.items())
            or counts.get("nationalEvseCount") != len(initial["nationalSourceEvseIds"])
            or counts.get("originalMontaMissingEvseCount") != len(old_missing)
            or counts.get("currentMatchedEvseCount") != len(rows)
            or counts.get("currentPricedEvseCount") != len(priced)
            or counts.get("currentMissingInMontaCount") != len(missing)
            or report.get("status") != ("complete" if not missing and len(priced) == len(rows) else "partial")
            or report.get("productionSource") != str(DATA)
            or any(report.get(key) != counts.get(key) for key in
                   ("currentMatchedEvseCount", "currentPricedEvseCount", "currentMissingInMontaCount"))
            or any(current[eid].get("currency") != "CHF"
                   or current[eid].get("source") != "Monta public direct-payment page"
                   or not current[eid].get("sourceUrl")
                   or not isinstance(current[eid].get("pricePerKwh"), (int, float))
                   for eid in additions)):
        raise ValueError("Swiss PowerUp exact residual scope invalid")
    return payload


def run(out: Path, source: Path, *, runner=subprocess.run) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents:
        raise ValueError("Swiss PowerUp closeout must run outside checkout")
    validate_initial(source)
    for relative in (DATA, REPORT):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    initial = out / INITIAL
    initial.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / DATA, initial)
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Swiss PowerUp residual closeout failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.source)


if __name__ == "__main__":
    main()
