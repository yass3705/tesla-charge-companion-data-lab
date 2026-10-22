#!/usr/bin/env python3
"""Run Shell Recharge first-party station evidence with complete sample gate."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/shell_recharge_official.py")
TEMP = Path("out/shell_recharge/shell_recharge_official_france.json")
TEMP_REPORT = Path("out/shell_recharge/SUMMARY.md")
OUTPUT = Path("data/operator_direct/shell_recharge_official_france.json")
REPORT = Path("reports/shell_recharge/latest_summary.md")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    archived = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))
    direct = (payload.get("operatorDirect") or {}).get("fastShellRechargeWithShellApp") or {}
    samples = (payload.get("operatorDirect") or {}).get("renderedFirstPartySamples") or {}
    evidence = payload.get("sourceEvidence") or {}
    checks = payload.get("representativeStationChecks") or []
    source_rows = evidence.get("sources") or []
    expected_keys = {"sommesous", "roussillon", "cestas", "lesSalles", "criquetot"}
    if (payload.get("schemaVersion") != "1.3.0" or payload.get("dataset") != "shell-recharge-official-france"
            or payload.get("country") != "FR" or payload.get("operator") != "Shell Recharge"
            or payload.get("publicationStatus") != "candidate_validated_source"
            or direct.get("uniformAcrossFastShellRechargeStations") is not None
            or direct.get("exactStationLookupRecommended") is not True
            or direct.get("representativeCurrentEurPerKwh") != archived["operatorDirect"]["fastShellRechargeWithShellApp"]["representativeCurrentEurPerKwh"]
            or payload.get("fees", {}).get("representativeShellAppSessionFeeEur") != archived["fees"]["representativeShellAppSessionFeeEur"]
            or payload.get("roaming", {}).get("operatorDirect") is not False
            or payload.get("technical", {}).get("stationRenderErrors")
            or samples.get("count") != len(expected_keys)
            or len(checks) != len(expected_keys) or {row.get("key") for row in checks} != expected_keys
            or any(row.get("eurPerKwh") != direct.get("representativeCurrentEurPerKwh") for row in checks)
            or len(source_rows) != 10 or any(row.get("httpStatus") != 200 for row in source_rows)
            or evidence.get("officialOnly") is not True
            or not (out / REPORT).read_text(encoding="utf-8").strip()):
        raise ValueError("Shell official sample completeness, price or channel contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Shell work must be off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    completed = runner([sys.executable, str(script), "--out", str(out / "out/shell_recharge")],
                       cwd=out, capture_output=True, text=True, timeout=1800, check=False)
    if completed.returncode:
        raise RuntimeError("Historical Shell official method failed")
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
