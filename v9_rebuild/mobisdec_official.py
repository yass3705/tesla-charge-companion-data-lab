#!/usr/bin/env python3
"""Isolated execution of the archived MobiSDEC official extraction method."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/mobisdec_official.py")
TEMP = Path("out/mobisdec/mobisdec_official_calvados.json")
TEMP_REPORT = Path("out/mobisdec/SUMMARY.md")
OUTPUT = Path("data/operator_direct/mobisdec_official_calvados.json")
REPORT = Path("reports/mobisdec/latest_summary.md")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    archived = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))
    evidence = payload.get("sourceEvidence") or {}
    sources = evidence.get("sources") or []
    classification = payload.get("classification") or {}
    technical = payload.get("technical") or {}
    for key in ("regionalPublicNetwork", "scope", "networkOwner", "serviceBrand", "technicalOperator2026",
                "energyTariffMachineVerified", "immobilizationFeeSourceDiscrepancy", "formal2026PdfCurrentReachability"):
        if classification.get(key) != archived["classification"].get(key):
            raise ValueError(f"MobiSDEC classification changed: {key}")
    if (payload.get("schemaVersion") != "1.0.0" or payload.get("dataset") != "mobisdec-official-calvados"
            or payload.get("country") != "FR" or payload.get("operator") != "MobiSDEC / SDEC Énergie"
            or payload.get("publicationStatus") != "candidate_validated_source"
            or payload.get("operatorDirect") != archived.get("operatorDirect")
            or payload.get("accessChannels") != archived.get("accessChannels")
            or payload.get("roaming") != archived.get("roaming")
            or any(technical.get(k) != archived["technical"].get(k) for k in
                   ("slowPowerKwRange", "normalAcPowerKw", "normalDcPowerKva", "rapidPowerKwRange"))
            or not isinstance(classification.get("officialTechnicalDatasetRows"), int)
            or not isinstance(technical.get("stationExamplesFromOfficialDataset"), dict)
            or evidence.get("officialOnly") is not True
            or {row.get("key") for row in sources} != {"mobisdecOfficial", "sdecMobilityOfficial", "sdecFormal2026Decision", "dataGouvDatasetPage", "dataGouvTechnicalCsv"}
            or any(row.get("httpStatus") != 200 for row in sources if row.get("key") != "sdecFormal2026Decision")
            or any(len(str(row.get("rawSha256") or "")) != 64 for row in sources if row.get("key") != "sdecFormal2026Decision")
            or not (out / REPORT).read_text(encoding="utf-8").strip()):
        raise ValueError("MobiSDEC official technical or price-scope contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("MobiSDEC work must be off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    completed = runner([sys.executable, str(script)], cwd=out,
                       capture_output=True, text=True, timeout=900, check=False)
    if completed.returncode:
        raise RuntimeError("Historical MobiSDEC official method failed")
    for old, new in ((TEMP, OUTPUT), (TEMP_REPORT, REPORT)):
        dest = out / new
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / old, dest)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
