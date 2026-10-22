#!/usr/bin/env python3
"""Run archived Belgium EnergyVision stage and reconciliation outside Git."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

STAGE = Path("artifacts/energyvision-datex-stage.json.gz")
STAGE_REPORT = Path("reports/belgium/energyvision-datex-semantic-audit.json")
INDEPENDENT = Path("data/belgium/energyvision-official-2026-10-13.json.gz")
INDEPENDENT_REPORT = Path("reports/belgium/energyvision-official-2026-10-13-audit.json")
NAP_REPORT = Path("reports/belgium/energyvision-nap-exact-audit.json")
NAP_MANIFEST = Path("data/belgium/nap-belgium-manifest.json")
METHODS = ("energyvision_datex_inventory_probe.py", "energyvision_datex_semantic_stage.py",
           "energyvision_datex_independent_cpo.py", "energyvision_datex_nap_audit.py")


def _read(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_output(out: Path) -> dict:
    stage, audit = _read(out / STAGE), _read(out / STAGE_REPORT)
    independent, independent_audit = _read(out / INDEPENDENT), _read(out / INDEPENDENT_REPORT)
    nap = _read(out / NAP_REPORT)
    counts = independent.get("counts") or {}
    stage_counts = audit.get("counts") or {}
    if (stage.get("provider") != "EnergyVision" or stage.get("country") != "BE"
            or stage.get("schemaVersion") != 1 or stage.get("v9PublicationReady") is not False
            or audit.get("v9ReadyForPriceRanking") is not False
            or audit.get("collectedAt") != stage.get("collectedAt")
            or audit.get("sourceStatic") != stage.get("sourceStatic")
            or audit.get("sourceDynamic") != stage.get("sourceDynamic")
            or stage_counts.get("sites") != len(stage.get("static", {}).get("sites") or [])
            or independent.get("provider") != "EnergyVision" or independent.get("country") != "BE"
            or independent.get("sourceSha256") != stage.get("sourceStatic", {}).get("sha256")
            or independent.get("collectedAt") != stage.get("collectedAt")
            or independent.get("v9PublicationReady") is not False
            or independent.get("v9PricedPDC") != 0
            or counts.get("sourcePDC") != counts.get("distinctExternalEvseIds")
            or independent_audit.get("counts") != counts
            or independent_audit.get("v9PublicationReady") is not False
            or independent_audit.get("v9PricedPDC") != 0
            or nap.get("provider") != "EnergyVision" or nap.get("country") != "BE"
            or nap.get("collectedAt") != stage.get("collectedAt")
            or nap.get("sourceStaticSha256") != stage.get("sourceStatic", {}).get("sha256")
            or nap.get("v9PricePublicationReady") is not False):
        raise ValueError("EnergyVision source identity or no-price publication contract invalid")
    sites = independent.get("sites")
    if not isinstance(sites, list) or len(sites) != counts.get("sites"):
        raise ValueError("EnergyVision independent site count invalid")
    points = [point for site in sites for station in site.get("stations", [])
              for point in station.get("pdc", [])]
    if len(points) != counts.get("sourcePDC") or any(point.get("priceable") is not False for point in points):
        raise ValueError("EnergyVision EVSE price attribution forbidden")
    return independent


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("EnergyVision methods must run outside checkout")
    scripts = out / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for name in METHODS:
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    (scripts / "__init__.py").touch()
    manifest = _read(ROOT / NAP_MANIFEST)
    (out / NAP_MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / NAP_MANIFEST, out / NAP_MANIFEST)
    for page in manifest.get("pages", []):
        relative = Path(page["canonicalPath"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:3] != ("data", "belgium", "pages"):
            raise ValueError("Unsafe Belgium NAP page path")
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    commands = (
        [sys.executable, "-m", "scripts.energyvision_datex_semantic_stage", "--staging", str(STAGE), "--report", str(STAGE_REPORT)],
        [sys.executable, "-m", "scripts.energyvision_datex_independent_cpo", "--stage", str(STAGE),
         "--manifest", str(NAP_MANIFEST), "--output", str(INDEPENDENT), "--report", str(INDEPENDENT_REPORT)],
        [sys.executable, "-m", "scripts.energyvision_datex_nap_audit", "--stage", str(STAGE),
         "--manifest", str(NAP_MANIFEST), "--report", str(NAP_REPORT)],
    )
    for command in commands:
        result = runner(command, cwd=out, capture_output=True, text=True, timeout=1200, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical EnergyVision method failed: {command[2]}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
