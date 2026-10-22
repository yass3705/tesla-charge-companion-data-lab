#!/usr/bin/env python3
"""Build the preserved public Swiss dataset from an immutable Swiss bundle."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.orchestrator import ROOT
from v9_rebuild.swiss_bundle import BUNDLE, validate_output as validate_bundle

SCRIPT = Path("scripts/build_switzerland_v9_dataset.py")
OUTPUT = Path("data/national/switzerland_public_charging_v9.json")
REPORT = Path("docs/switzerland-v9-canonical-integration-2026-09-28.json")
PUBLIC = {"Free publicly accessible", "Paying publicly accessible"}
EXCLUDED = {"Restricted access", "Test Station"}


def validate_output(out: Path) -> dict:
    original = json.loads((out / BUNDLE).read_text(encoding="utf-8"))
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    raw = original["evses"]
    expected = {row["evseId"]: row for row in raw if row["accessibility"] in PUBLIC}
    observed = payload.get("evses")
    if not isinstance(observed, list) or len(expected) != len(observed):
        raise ValueError("Swiss public EVSE set inconsistent")
    seen = set()
    for row in observed:
        eid = row.get("evseId")
        if eid not in expected or eid in seen or row.get("accessibility") not in PUBLIC:
            raise ValueError("Swiss public EVSE identity or access invalid")
        seen.add(eid)
        source = expected[eid]
        if (row.get("chargingStationId") != source.get("stationId")
                or row.get("directTariff", {}).get("overlays") != source.get("directTariffs")
                or row.get("directTariff", {}).get("status") != ("priced" if source.get("directTariffStatus") == "resolved" else source.get("directTariffStatus"))
                or row.get("plugs") != source.get("plugs")
                or row.get("chargingFacilities") != source.get("chargingFacilities")
                or row.get("operatorId") != source.get("operatorId")):
            raise ValueError("Swiss public EVSE tariff or station mutated")
    excluded = sum(row["accessibility"] in EXCLUDED for row in raw)
    summary = payload.get("summary") or {}
    if (payload.get("schemaVersion") != 3 or payload.get("country") != "CH"
            or summary.get("rawNationalEvseCount") != len(raw)
            or summary.get("nationalEvseCount") != len(observed)
            or summary.get("excludedNonPublicEvseCount") != excluded
            or report.get("summary") != summary):
        raise ValueError("Swiss public dataset summary invalid")
    return report


def run(out: Path, source: Path) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents or out == source:
        raise ValueError("Swiss integration must use isolated paths")
    validate_bundle(source)
    target = out / BUNDLE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / BUNDLE, target)
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([sys.executable, str(script)], cwd=out, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f"Historical Swiss integration failed: {result.stderr[-1000:]}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.source)


if __name__ == "__main__":
    main()
