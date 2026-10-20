#!/usr/bin/env python3
"""Build the preserved France canonical evidence set from isolated inputs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

OUTPUT = Path("data/national/france_public_charging_canonical.json")
INPUT_DIRS = (Path("data/regional_coverage"), Path("data/operator_direct"), Path("data/station_verifications"))
LEDGER = Path("reports/france/irve-public-access-validation-ledger.json")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    counts = payload.get("counts") or {}
    regional = payload.get("regionalCoverageSources") or []
    direct = payload.get("operatorDirectSources") or []
    stations = payload.get("stationVerifications") or []
    access = payload.get("publicAccessValidation") or {}
    policy = payload.get("policy") or {}
    if (payload.get("schemaVersion") != "1.0.0"
            or payload.get("dataset") != "france-public-charging-canonical"
            or payload.get("country") != "FR" or payload.get("deterministicBuild") is not True
            or counts.get("regionalCoverageSources") != len(regional)
            or counts.get("operatorDirectSources") != len(direct)
            or counts.get("stationVerificationSources") != len(stations)
            or policy.get("doNotInventDepartmentDefaults") is not True
            or policy.get("directCpoAndRoamingSeparate") is not True
            or policy.get("unresolvedDirectPricesRemainUnranked") is not True
            or len({row.get("sourcePath") for row in regional + direct + stations}) != len(regional + direct + stations)
            or access.get("sourcePath") != LEDGER.as_posix()):
        raise ValueError("France canonical technical contract invalid")
    for row in regional + direct + stations:
        relative = Path(row["sourcePath"])
        if relative.is_absolute() or ".." in relative.parts or not (out / relative).is_file():
            raise ValueError("France canonical input provenance invalid")
        original = json.loads((out / relative).read_text(encoding="utf-8"))
        if row.get("payload") != original:
            raise ValueError("France canonical input payload differs from provenance")
    return payload


def run(out: Path) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("France canonical output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    for relative in INPUT_DIRS:
        (out / relative).mkdir(parents=True, exist_ok=True)
        for source in (ROOT / relative).glob("*.json"):
            shutil.copy2(source, out / relative / source.name)
    (out / LEDGER).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / LEDGER, out / LEDGER)
    script = ROOT / "scripts/build_france_canonical_dataset.py"
    spec = importlib.util.spec_from_file_location("historical_france_canonical", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("France canonical historical script missing")
    historical = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(historical)
    historical.ROOT = out
    historical.DEFAULT_OUT = out / OUTPUT
    historical.OVERRIDES = out / "data/regional_coverage/manual_status_overrides_2026_08_22.json"
    historical.BOURGES = out / "data/station_verifications/modulo_bourges_maurice_roy_adhoc_2026_08_22.json"
    historical.PUBLIC_ACCESS_LEDGER = out / LEDGER
    old_args = sys.argv
    try:
        sys.argv = [str(script), "--out", str(out / OUTPUT)]
        if historical.main() != 0:
            raise RuntimeError("Historical France canonical builder failed")
    finally:
        sys.argv = old_args
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
