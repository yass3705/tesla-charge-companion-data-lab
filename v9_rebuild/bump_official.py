#!/usr/bin/env python3
"""Run the preserved Bump official rule extractor outside the checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

OUTPUT = Path("data/operator_direct/bump_official_france.json")
REPORT = Path("reports/bump/latest_summary.md")
TEMP = Path("out/bump")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    evidence = payload.get("sourceEvidence") or {}
    if (payload.get("dataset") != "bump-official-france" or payload.get("operator") != "Bump"
            or payload.get("country") != "FR" or evidence.get("officialOnly") is not True
            or len(evidence.get("sources") or []) != 5
            or any(row.get("httpStatus") != 200 for row in evidence["sources"])
            or payload.get("classification", {}).get("singleGuaranteedNationalCpoDirectTariff") is not False
            or payload.get("classification", {}).get("stationLevelPriceLookupRequiredForExactCpoDirect") is not True
            or payload.get("operatorDirect", {}).get("bumpOperatedStations", {}).get("nationalEurPerKwh") is not None
            or payload.get("roaming", {}).get("operatorDirect") is not False
            or not (out / REPORT).is_file()):
        raise ValueError("Bump official method contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Bump output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(ROOT / "scripts/bump_official.py"), "--out", str(out / TEMP)],
                    cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError("Historical Bump official method failed")
    (out / OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / TEMP / "bump_official_france.json", out / OUTPUT)
    shutil.copy2(out / TEMP / "SUMMARY.md", out / REPORT)
    shutil.rmtree(out / "out")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
