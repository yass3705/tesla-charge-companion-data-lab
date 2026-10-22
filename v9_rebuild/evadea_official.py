#!/usr/bin/env python3
"""Preserved e-Vadea image-discovery and official tariff grid, isolated."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPTS = (Path("scripts/evadea_official.py"), Path("scripts/evadea_tariff_image_discovery.py"))
TEMP = Path("out/evadea-final")
DISCOVERY = TEMP / "discovery/discovery.json"
OUTPUT = Path("data/operator_direct/evadea_official_france.json")
REPORT = Path("reports/evadea/latest_summary.md")


def validate_output(out: Path) -> dict:
    result = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    discovery = json.loads((out / DISCOVERY).read_text(encoding="utf-8"))
    archived = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))
    evidence = result.get("sourceEvidence") or {}
    if (result.get("schemaVersion") != "1.0.0" or result.get("dataset") != "evadea-official-france"
            or result.get("country") != "FR" or result.get("operator") != "e-Vadea"
            or discovery.get("operator") != "e-Vadea" or discovery.get("country") != "FR"
            or result.get("publicationStatus") != "candidate_validated_source"
            or result.get("classification") != archived.get("classification")
            or result.get("operatorDirect") != archived.get("operatorDirect")
            or result.get("fees") != archived.get("fees")
            or result.get("energyBilling") != archived.get("energyBilling")
            or result.get("roaming") != archived.get("roaming")
            or evidence.get("tariffImageSha256") != (discovery.get("tariffImage") or {}).get("sha256")
            or len(str(evidence.get("tariffImageSha256") or "")) != 64
            or evidence.get("officialOnly") is not True
            or result.get("classification", {}).get("stationContextLookupRequiredForExactSimulation") is not True
            or result.get("roaming", {}).get("operatorDirect") is not False
            or not (out / REPORT).read_text(encoding="utf-8").strip()):
        raise ValueError("e-Vadea official grid, image proof or channel scope invalid")
    return result


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("e-Vadea work must be off checkout")
    for script in SCRIPTS:
        target = out / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / script, target)
    completed = runner([sys.executable, str(out / SCRIPTS[0]), "--out", str(out / TEMP)],
                       cwd=out, capture_output=True, text=True, timeout=1200, check=False)
    if completed.returncode:
        raise RuntimeError("Historical e-Vadea method failed")
    for old, new in ((TEMP / "evadea_official_france.json", OUTPUT),
                     (TEMP / "SUMMARY.md", REPORT)):
        target = out / new
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / old, target)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
