#!/usr/bin/env python3
"""Run the preserved DRIVECO exact-EVSE CSV method off checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

OUTPUT = Path("data/operator_direct/driveco_evse_tariffs.json")
REPORT = Path("reports/driveco/evse_tariffs_summary.md")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    report = (out / REPORT).read_text(encoding="utf-8")
    resolved = payload.get("resolved")
    unresolved = payload.get("unresolved")
    summary = payload.get("summary") or {}
    policy = payload.get("policy") or {}
    if not isinstance(resolved, list) or not isinstance(unresolved, list):
        raise ValueError("DRIVECO exact EVSE lists missing")
    ids = [row.get("evseId") for row in resolved + unresolved if row.get("evseId")]
    if (payload.get("schemaVersion") != "1.0.0"
            or payload.get("dataset") != "driveco-evse-direct-tariffs"
            or policy.get("operatorDirectOnly") is not True
            or policy.get("roamingExcluded") is not True
            or policy.get("referencePricesNeverUsedAsFallback") is not True
            or policy.get("matrixOSFNotInterpretedUntilSemanticsValidated") is not True
            or summary.get("rowCount") != len(resolved) + len(unresolved)
            or summary.get("resolvedEnergyPriceRows") != len(resolved)
            or summary.get("unresolvedRows") != len(unresolved)
            or len(ids) != len(set(ids))
            or any(row.get("networkClass") not in {"driveco_network", "partner_network", "other_or_unspecified"}
                   or not isinstance(row.get("tariff", {}).get("energyPriceEurPerKwh"), (int, float))
                   or row.get("feeSemantics", {}).get("matrixOSF") != "published_raw_not_yet_interpreted"
                   or (bool(row.get("tariff", {}).get("matrixOSF")) and row.get("feeSemantics", {}).get("safeForFullSessionCost") is not False)
                   for row in resolved)
            or any(row.get("unresolvedReason") != "official_driveco_irve_row_has_no_machine_readable_tarification" for row in unresolved)
            or "DRIVECO EVSE direct tariff base" not in report):
        raise ValueError("DRIVECO exact EVSE technical contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("DRIVECO EVSE output must be outside checkout")
    work = out / "out/driveco-evse"
    work.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(ROOT / "scripts/driveco_evse_tariffs.py"), "--out", str(work)],
                    cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError("Historical DRIVECO exact EVSE method failed")
    (out / OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(work / "driveco_evse_tariffs.json", out / OUTPUT)
    shutil.copy2(work / "SUMMARY.md", out / REPORT)
    shutil.rmtree(out / "out")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
