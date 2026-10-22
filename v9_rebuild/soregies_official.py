#!/usr/bin/env python3
"""Run the preserved Sorégies official-rule method without promoting headline prices."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/soregies_mobilites_official.py")
TEMP = Path("out/soregies/soregies_mobilites_official_vienne.json")
TEMP_REPORT = Path("out/soregies/SUMMARY.md")
OUTPUT = Path("data/operator_direct/soregies_mobilites_official_vienne.json")
REPORT = Path("reports/soregies/latest_summary.md")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    archived = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))
    evidence = payload.get("sourceEvidence") or {}
    sources = evidence.get("machineValidatedSources") or []
    marketing = payload.get("currentMarketingOffer") or {}
    decision = payload.get("tccDecision") or {}
    if (payload.get("schemaVersion") != "1.2.0"
            or payload.get("dataset") != "soregies-mobilites-official-vienne"
            or payload.get("country") != "FR" or payload.get("operator") != "Sorégies Mobilités"
            or payload.get("publicationStatus") != "candidate_validated_source_current_price_manual_check_required"
            or payload.get("currentMarketingOffer") != archived.get("currentMarketingOffer")
            or payload.get("legacyDetailedGrid") != archived.get("legacyDetailedGrid")
            or marketing.get("headlineValuesSafeAsUniversalStationTariff") is not False
            or marketing.get("headlinePriceCardsMachineVerifiedInWorkflow") is not False
            or decision.get("currentExactCalculatorGridValidated") is not False
            or decision.get("currentHeadlineOfferMachineVerified") is not False
            or evidence.get("officialOnly") is not True
            or {row.get("key") for row in sources} != {"currentOffer", "plusOffer", "proOffer", "dataGouvPage", "dataGouvCsv"}
            or any(row.get("httpStatus") != 200 or len(str(row.get("sha256") or "")) != 64 for row in sources)
            or not isinstance((payload.get("technical") or {}).get("stationExamplesFromOfficialDataset"), list)
            or not (out / REPORT).read_text(encoding="utf-8").strip()):
        raise ValueError("Sorégies official technical or price-scope contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Sorégies work must be off checkout")
    target = out / SCRIPT
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, target)
    completed = runner([sys.executable, str(target)], cwd=out,
                       capture_output=True, text=True, timeout=600, check=False)
    if completed.returncode:
        raise RuntimeError("Historical Sorégies official method failed")
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
