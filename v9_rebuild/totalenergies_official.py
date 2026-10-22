#!/usr/bin/env python3
"""Run preserved TotalEnergies France CPO, eMSP and local tariff rules."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/totalenergies_official.py")
TEMP = Path("out/totalenergies/totalenergies_official_france.json")
TEMP_REPORT = Path("out/totalenergies/SUMMARY.md")
OUTPUT = Path("data/operator_direct/totalenergies_official_france.json")
REPORT = Path("reports/totalenergies/latest_summary.md")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    archived = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))
    source = payload.get("sourceEvidence") or {}
    rows = source.get("sources") or []
    if (payload.get("schemaVersion") != "1.0.0" or payload.get("dataset") != "totalenergies-official-france"
            or payload.get("country") != "FR" or payload.get("operator") != "TotalEnergies"
            or payload.get("publicationStatus") != "candidate_validated_source"
            or payload.get("classification") != archived.get("classification")
            or payload.get("operatorDirect") != archived.get("operatorDirect")
            or payload.get("mobilityProvider") != archived.get("mobilityProvider")
            or payload.get("localNetworks") != archived.get("localNetworks")
            or payload.get("officialCpoEmspModel") != archived.get("officialCpoEmspModel")
            or payload.get("mobilityProvider", {}).get("chargePlus", {}).get("operatorDirect") is not False
            or payload.get("classification", {}).get("singleNationalOperatorTariff") is not False
            or source.get("officialOnly") is not True
            or {row.get("key") for row in rows} != {"stationPricing", "stationIdle", "chargePlus", "chargePlusHome", "zenPoints", "cityAmp", "cpoEmsp"}
            or any(row.get("httpStatus") != 200 for row in rows)
            or not isinstance(payload.get("zenEligibleInventory", {}).get("officialTableRowCount"), int)
            or not isinstance(payload.get("stationValidationSamples"), list)
            or not (out / REPORT).read_text(encoding="utf-8").strip()):
        raise ValueError("TotalEnergies official CPO/eMSP/local tariff contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("TotalEnergies work must be off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    completed = runner([sys.executable, str(script), "--out", str(out / "out/totalenergies")],
                       cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if completed.returncode:
        raise RuntimeError("Historical TotalEnergies official method failed")
    for old, new in ((TEMP, OUTPUT), (TEMP_REPORT, REPORT)):
        destination = out / new
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / old, destination)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
