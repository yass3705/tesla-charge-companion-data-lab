#!/usr/bin/env python3
"""Run the preserved REVE v2 national builders outside the checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from scripts.validate_reve_v2_runtime import validate as validate_bundle
from v9_rebuild.electroverse import ROOT

SCRIPTS = tuple(Path("scripts") / f"reve-v2-{name}.mjs" for name in
                ("web-extract", "snapshot", "analyze", "build-canonical", "build-tcc"))
VALIDATOR = Path("scripts/validate_reve_v2_runtime.py")
BASELINE = Path("data/reve_v2/validated_runtime")
REPORT = Path("data/reve-v2/tcc-integration/spain-tcc-build-report.json")
CANONICAL_REPORT = Path("data/reve-v2/canonical/build-report.json")
STATIONS = Path("data/reve_v2/validated_runtime/spain-static")
OFFERS = Path("data/reve_v2/validated_runtime/spain-reve-offers")


def validate_output(out: Path) -> dict:
    result = validate_bundle(out / BASELINE)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    canonical = json.loads((out / CANONICAL_REPORT).read_text(encoding="utf-8"))
    raw = list((out / "data/reve-v2/raw").glob("*/manifest.json"))
    if (len(raw) != 1 or not report.get("ok") or not canonical.get("ok")
            or report.get("generatedAt") != result["generatedAt"]
            or report.get("stations") != result["stations"]
            or report.get("directOffers") != result["directOffers"]):
        raise ValueError("REVE national build reports differ from bundle")
    source = json.loads(raw[0].read_text(encoding="utf-8"))
    pages = list(raw[0].parent.glob("locations-page-*.json"))
    if (source.get("status") != "captured" or source.get("paginationComplete") is not True
            or source.get("failures") or source.get("pagesSucceeded") != len(pages)
            or source.get("reportedTotalPages") not in (None, len(pages))):
        raise ValueError("REVE raw pagination incomplete")
    return result


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("REVE workspace must be off checkout")
    validate_bundle(ROOT / BASELINE)
    for relative in (*SCRIPTS, VALIDATOR):
        dest = out / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, dest)
    for relative in SCRIPTS:
        if relative.name == "snapshot":
            continue
        result = runner(["node", str(out / relative)], cwd=out,
                        capture_output=True, text=True, timeout=10800, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical REVE national method failed: {relative.name}")
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    if report.get("ok") is not True:
        raise ValueError("REVE national builder reported failure")
    source = out / "data/reve-v2/tcc-integration"
    for target, pattern, manifest in ((STATIONS, "tile_*.json.gz", "spain-static-manifest.json"),
                                      (OFFERS, "offers_*.json.gz", "spain-reve-offers-manifest.json")):
        dest = out / target
        dest.mkdir(parents=True, exist_ok=True)
        for file in source.glob(pattern):
            shutil.copy2(file, dest / file.name)
        shutil.copy2(source / manifest, dest / "manifest.json")
    shutil.copy2(source / "all.json.gz", out / STATIONS / "all.json.gz")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
