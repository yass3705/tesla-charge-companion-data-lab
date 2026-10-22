#!/usr/bin/env python3
"""Run the preserved France treated-source reliability audit on isolated inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/france_treated_reliability_audit.py")
CANON = Path("docs/france-cpo-progress-2026-09.json")
REGISTRY = Path("v9-production-runtime/data/v9/source-registry.json")
REPORT = Path("reports/france/cpo-treated-reliability-audit-latest.json")
MANIFEST = Path("reports/france/cpo-treated-reliability-input-manifest.json")


def inputs(root: Path) -> list[Path]:
    paths = {SCRIPT, CANON, REGISTRY}
    for base, patterns in (
        ("data/operator_direct", ("*.json",)),
        ("reports/france", ("**/*.json",)),
        ("data/reports", ("*.json",)),
        ("v9-production-runtime/data/v9", ("france-*.json",)),
    ):
        for pattern in patterns:
            for path in (root / base).glob(pattern):
                if path.is_file() and path.stat().st_size <= 8_000_000 and path.relative_to(root) != MANIFEST:
                    paths.add(path.relative_to(root))
    return sorted(paths)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_output(out: Path) -> dict:
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    manifest = json.loads((out / MANIFEST).read_text(encoding="utf-8"))
    files = manifest.get("inputSha256")
    if (report.get("schemaVersion") != 1 or report.get("country") != "FR"
            or report.get("type") != "treated-and-released-slot-reliability-audit"
            or not isinstance(files, dict) or not files.get(str(CANON)) or not files.get(str(REGISTRY))
            or manifest.get("reportSha256") != sha256(out / REPORT)):
        raise ValueError("France treated audit report or provenance invalid")
    released = report.get("releasedHistoricalSlots") or {}
    treated = report.get("treatedAuthorities") or {}
    runtime = report.get("runtimeFranceTariffSources") or {}
    if (released.get("count") != sum((released.get("classificationByMarker") or {}).values())
            or not isinstance(released.get("unclassified"), list)
            or treated.get("count") is None
            or not isinstance(treated.get("statusContradictions"), list)
            or not isinstance(treated.get("candidateCoverageGapMetrics"), list)
            or runtime.get("count") != len(runtime.get("sources") or [])
            or not isinstance(runtime.get("missingDeclaredPaths"), list)
            or report.get("decision", {}).get("treatedDoesNotMean100PercentPriced") is not True):
        raise ValueError("France treated audit internal accounting invalid")
    return report


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("France treated audit must run off checkout")
    selected = inputs(ROOT)
    provenance = {}
    for relative in selected:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
        provenance[relative.as_posix()] = sha256(target)
    result = runner([sys.executable, str(out / SCRIPT)], cwd=out,
                    capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError("Historical France treated audit failed")
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    if report.get("schemaVersion") != 1 or report.get("country") != "FR":
        raise ValueError("Historical France treated audit output invalid")
    manifest_path = out / MANIFEST
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"schemaVersion": 1, "inputSha256": provenance,
                                         "reportSha256": sha256(out / REPORT)}, sort_keys=True) + "\n")
    validate_output(out)
    # Only the signed input list and derived report belong in the versioned artifact.
    for relative in selected:
        if relative not in (SCRIPT, REPORT):
            (out / relative).unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
