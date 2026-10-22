#!/usr/bin/env python3
"""Finalize Swiss eCarUp coverage from one signed coordinate artifact."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.cwd_script import validate_output as validate_coordinate
from v9_rebuild.electroverse import ROOT

EXACT = Path("data/switzerland/ecarup-owner-direct-tariffs.json")
COORDINATE = Path("data/switzerland/ecarup-owner-coordinate-safe-overlay.json")
REPORT = Path("docs/switzerland-ecarup-finalization-2026-09-28.json")
SCRIPT = Path("scripts/finalize_swiss_ecarup_owner.py")


def validate_output(out: Path) -> dict:
    coordinate = validate_coordinate(out, "swiss_ecarup_coordinate")
    exact = json.loads((out / EXACT).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    priced = {row["evseId"] for row in exact["evses"]
              if row["classification"] == "priced_public_direct"}
    restricted = {row["evseId"] for row in exact["evses"]
                  if row["classification"] in {"restricted_or_nonpublic_connector",
                                                 "restricted_no_public_direct_tariff"}}
    overlay = {row["evseId"] for row in coordinate["evses"]}
    total = exact["counts"]["nationalEvseCount"]
    unresolved = total - len(priced) - len(restricted) - len(overlay)
    if (report.get("schemaVersion") != 1 or report.get("country") != "CH"
            or report.get("operatorId") != "CH*ECU"
            or total != coordinate.get("nationalEvseCount")
            or any(not identity or not identity.startswith("CH*ECU*E") for identity in priced | restricted | overlay)
            or priced & restricted or overlay & (priced | restricted) or unresolved < 0
            or report.get("nationalEvseCount") != total
            or report.get("exactConnectorPricedCount") != len(priced)
            or report.get("exactRestrictedCount") != len(restricted)
            or report.get("safeCoordinateOverlayCount") != len(overlay)
            or report.get("pricedEvseCount") != len(priced) + len(overlay)
            or report.get("unresolvedEvseCount") != unresolved
            or report.get("status") != ("complete" if unresolved == 0 else "partial")
            or report.get("productionSources") != [str(EXACT), str(COORDINATE)]):
        raise ValueError("Swiss eCarUp finalization scope invalid")
    return report


def run(out: Path, source: Path, *, runner=subprocess.run) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents:
        raise ValueError("Swiss eCarUp finalization must use isolated paths")
    validate_coordinate(source, "swiss_ecarup_coordinate")
    for relative in (EXACT, COORDINATE,
                     Path("docs/switzerland-ecarup-owner-coordinate-safe-overlay-2026-09-28.json")):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Swiss eCarUp finalizer failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.source)


if __name__ == "__main__":
    main()
