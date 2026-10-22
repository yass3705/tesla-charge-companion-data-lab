#!/usr/bin/env python3
"""Run the preserved Swiss PowerUp national/Monta exact-ID collector off checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/collect_powerup_monta_public.py")
DATA = Path("data/switzerland/powerup-monta-direct-tariffs.json")
REPORT = Path("docs/switzerland-powerup-finalization-2026-09-28.json")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / DATA).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = payload.get("evses")
    missing = payload.get("missingCurrentEvseIds")
    extra = payload.get("montaExtraEvseIds")
    counts = payload.get("counts") or {}
    if not all(isinstance(item, list) for item in (rows, missing, extra)):
        raise ValueError("Swiss PowerUp exact-ID lists missing")
    ids = [row.get("evseId") for row in rows]
    national = payload.get("nationalSourceEvseIds")
    monta = payload.get("montaSourceEvseIds")
    if not isinstance(national, list) or not isinstance(monta, list):
        raise ValueError("Swiss PowerUp original source EVSE IDs missing")
    priced = [row for row in rows if any(row.get(key) is not None for key in
              ("pricePerKwh", "pricePerMinute", "startFee", "idleFee"))]
    status = "complete" if (not missing and len(priced) == len(rows)
                            and counts.get("nationalEvseCount") == len(rows)) else "partial"
    if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
            or payload.get("operatorId") != "CH*POW"
            or len(ids) != len(set(ids))
            or len(national) != len(set(national)) or len(monta) != len(set(monta))
            or any(not eid or not eid.startswith("CH*POW*E") for eid in ids + missing + extra)
            or set(ids) != set(national) & set(monta)
            or set(missing) != set(national) - set(monta)
            or set(extra) != set(monta) - set(national)
            or len(set(ids) & set(missing)) or len(set(ids) & set(extra))
            or counts.get("currentMatchedEvseCount") != len(rows)
            or counts.get("currentPricedEvseCount") != len(priced)
            or counts.get("currentMissingInMontaCount") != len(missing)
            or counts.get("montaExtraVsNationalCount") != len(extra)
            or counts.get("nationalEvseCount") != len(rows) + len(missing)
            or report.get("status") != status
            or report.get("productionSource") != str(DATA)
            or any(report.get(key) != value for key, value in counts.items())):
        raise ValueError("Swiss PowerUp national/Monta correspondence invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Swiss PowerUp collector must run outside checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError("Historical Swiss PowerUp/Monta method failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
