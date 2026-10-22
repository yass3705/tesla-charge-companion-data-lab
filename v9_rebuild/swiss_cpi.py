#!/usr/bin/env python3
"""Run the archived ChargePoint Switzerland exact-EVSE closeout off checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/finalize_swiss_cpi.py")
ATLAS = Path("data/switzerland/cpi-direct-tariffs-second-pass.json")
REC = Path("docs/switzerland-owner-gap-normalized-reconciliation-2026-09-28.json")
CTX = Path("docs/switzerland-cpi-residual-national-context-2026-09-28.json")
OUTPUT = Path("data/switzerland/cpi-current-direct-tariffs.json")
REPORT = Path("docs/switzerland-cpi-finalization-2026-09-28.json")
INPUTS = (ATLAS, REC, CTX)


def validate_output(out: Path) -> dict:
    atlas = json.loads((out / ATLAS).read_text(encoding="utf-8"))
    rec = json.loads((out / REC).read_text(encoding="utf-8"))
    ctx = json.loads((out / CTX).read_text(encoding="utf-8"))
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    owner = next((row for row in rec.get("operators", []) if row.get("operatorId") == "CH*CPI"), None)
    restricted = {row.get("evseId"): row.get("record") for row in ctx.get("hits", [])}
    evidence = {eid for station in atlas.get("stations", [])
                for point in station.get("chargePoints", [])
                if point.get("directTariffs")
                for eid in (point.get("chargePoint") or {}).get("evse_ids", [])}
    rows = payload.get("evses")
    if not isinstance(rows, list) or owner is None:
        raise ValueError("Swiss CPI closeout or reconciliation missing")
    ids = [row.get("evseId") for row in rows]
    priced = [row for row in rows if row.get("classification") == "priced_direct_atlas"]
    limited = [row for row in rows if row.get("classification") == "restricted_no_public_direct_tariff"]
    if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
            or payload.get("operatorId") != "CH*CPI"
            or len(ids) != len(set(ids)) or any(not eid for eid in ids)
            or payload.get("nationalEvseCount") != len(rows)
            or owner.get("nationalEvseCount") != len(rows)
            or payload.get("pricedEvseCount") != len(priced)
            or payload.get("classifiedNoPublicDirectTariffCount") != len(limited)
            or payload.get("unresolvedEvseCount") != 0
            or len(priced) + len(limited) != len(rows)
            or any(row["evseId"] not in evidence or not row.get("evidence", {}).get("directTariffs")
                   for row in priced)
            or any(row["evseId"] not in restricted
                   or (restricted[row["evseId"]] or {}).get("Accessibility") != "Restricted access"
                   or (restricted[row["evseId"]] or {}).get("AuthenticationModes")
                   for row in limited)
            or report.get("productionSource") != str(OUTPUT)
            or report.get("nationalEvseCount") != len(rows)
            or report.get("pricedEvseCount") != len(priced)
            or report.get("classifiedNoPublicDirectTariffCount") != len(limited)):
        raise ValueError("Swiss CPI exact EVSE scope invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Swiss CPI closeout must run outside checkout")
    for relative in INPUTS:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    (out / OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Swiss CPI closeout failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
