#!/usr/bin/env python3
"""Run the preserved Electra residual tariff audit on isolated signed inputs."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/france/audit_electra_pricing_residuals.mjs")
BASE = Path("data/platforms/electra/france")
NATIONAL = Path("data/national/france-irve-static-v9/all.json.gz")
INPUTS = (BASE / "manifest.json", BASE / "residuals.json.gz", BASE / "source-locations.json.gz", NATIONAL)
REPORT = Path("reports/france/irve/electra-pricing-residual-audit-2026-10-08.json")
CASES = Path("reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz")
QUEUE = Path("reports/france/irve/electra-pricing-action-queue-latest.csv")
PROVENANCE = Path("reports/france/irve/electra-pricing-audit-input-manifest.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_output(out: Path) -> dict:
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    with gzip.open(out / CASES, "rt", encoding="utf-8") as handle:
        archive = json.load(handle)
    provenance = json.loads((out / PROVENANCE).read_text(encoding="utf-8"))
    with (out / QUEUE).open("r", encoding="utf-8-sig", newline="") as handle:
        queue_rows = list(csv.reader(handle, delimiter=";"))
    cases = archive.get("cases")
    counts = report.get("counts") or {}
    if (report.get("schemaVersion") != 2 or archive.get("schemaVersion") != 2
            or not isinstance(cases, list) or counts.get("total") != len(cases)
            or counts.get("unsupported", 0) + counts.get("heterogeneous", 0) != len(cases)
            or report.get("caseArchive") != CASES.as_posix()
            or report.get("triage", {}).get("eligibleForAutomaticPublication") != 0
            or any(row.get("triage", {}).get("decision") != "hold_electra_emsp_price_unattributed" for row in cases)
            or len(queue_rows) != len(cases) + 1
            or len({row.get("locationId") for row in cases}) != len(cases)
            or provenance.get("schemaVersion") != 1
            or provenance.get("inputSha256", {}).keys() != {path.as_posix() for path in INPUTS}
            or provenance.get("outputSha256") != {path.as_posix(): sha256(out / path) for path in (REPORT, CASES, QUEUE)}):
        raise ValueError("Electra residual audit archive, queue or provenance invalid")
    return report


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Electra residual audit must be off checkout")
    for path in (SCRIPT, *INPUTS):
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, target)
    source_manifest = json.loads((out / INPUTS[0]).read_text(encoding="utf-8"))
    if (source_manifest.get("country") != "FR"
            or source_manifest.get("sourceArchive", {}).get("file") != "source-locations.json.gz"
            or source_manifest["sourceArchive"].get("sha256") != sha256(out / INPUTS[2])):
        raise ValueError("Electra source archive SHA or country invalid")
    result = runner(["node", str(out / SCRIPT)], cwd=out,
                    capture_output=True, text=True, timeout=1800, check=False)
    if result.returncode:
        raise RuntimeError("Historical Electra residual audit failed")
    manifest = {"schemaVersion": 1,
                "inputSha256": {path.as_posix(): sha256(out / path) for path in INPUTS},
                "outputSha256": {path.as_posix(): sha256(out / path) for path in (REPORT, CASES, QUEUE)}}
    target = out / PROVENANCE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    validate_output(out)
    for path in INPUTS:
        (out / path).unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
