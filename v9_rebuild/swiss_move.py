#!/usr/bin/env python3
"""Run preserved Swiss MOVE CPO-level finalizers independently off checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

METHODS = {
    "cci": ("finalize_swiss_cci_cpo_level.py", "data/switzerland/cci-move-cpo-tariffs-national.json",
            "docs/switzerland-cci-finalization-2026-09-28.json", "CH*CCI"),
    "soc": ("finalize_swiss_soc_cpo_level.py", "data/switzerland/soc-move-cpo-tariffs-national.json",
            "docs/switzerland-soc-finalization-2026-09-28.json", "CH*SOC"),
    "mmn": ("finalize_swiss_mmn_move.py", "data/switzerland/mmn-move-cpo-tariffs.json",
            "docs/switzerland-mmn-finalization-2026-09-28.json", "CH*MMN"),
}
INPUTS = (Path("data/switzerland/cci-direct-tariffs-second-pass.json"),
          Path("data/switzerland/soc-direct-tariffs.json"))


def validate_output(out: Path, method: str) -> dict:
    if method not in METHODS:
        raise ValueError("Unknown Swiss MOVE method")
    _, output, document, operator = METHODS[method]
    payload = json.loads((out / output).read_text(encoding="utf-8"))
    report = json.loads((out / document).read_text(encoding="utf-8"))
    rows, unresolved = payload.get("evses"), payload.get("unresolved")
    if not isinstance(rows, list) or not isinstance(unresolved, list):
        raise ValueError("Swiss MOVE EVSE lists missing")
    ids = [row.get("evseId") for row in rows + unresolved]
    priced_count = payload.get("resolvedEvseCount") if method == "cci" else payload.get("pricedEvseCount")
    if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
            or payload.get("operatorId") != operator
            or any(not value or not value.startswith(operator + "*") for value in ids)
            or len(ids) != len(set(ids))
            or payload.get("nationalEvseCount") != len(ids)
            or priced_count != len(rows) or payload.get("unresolvedEvseCount") != len(unresolved)
            or report.get("operatorId") != operator
            or report.get("nationalEvseCount") != len(ids)
            or report.get("unresolvedEvseCount") != len(unresolved)
            or (method != "mmn" and report.get("productionSource") != output)
            or report.get("status") != ("complete" if not unresolved else "partial")
            or any(not isinstance(row.get("tariffs"), list) or not row["tariffs"]
                   or any(not tariff.get("matchedKwhSegments")
                          or tariff.get("currency") != "CHF"
                          or any(segment.get("dimension") != "kwh" or segment.get("price") is None
                                 for segment in tariff["matchedKwhSegments"])
                          for tariff in row["tariffs"]) for row in rows)):
        raise ValueError("Swiss MOVE exact EVSE tariff scope invalid")
    if method == "cci" and report.get("pricedEvseCount") != len(rows):
        raise ValueError("Swiss MOVE CCI priced count invalid")
    if method != "cci" and report.get("pricedEvseCount", len(rows)) != len(rows):
        raise ValueError("Swiss MOVE priced count invalid")
    if method == "mmn" and any(
        segment.get("charge_point_energy_type", "").lower() != "ac"
        for row in rows for tariff in row["tariffs"] for segment in tariff["matchedKwhSegments"]
    ):
        raise ValueError("Swiss MOVE MMN AC-only scope invalid")
    return payload


def run(out: Path, method: str, *, runner=subprocess.run) -> None:
    if method not in METHODS:
        raise ValueError("Unknown Swiss MOVE method")
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Swiss MOVE method must run outside checkout")
    for relative in INPUTS:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    script_name, output, document, _ = METHODS[method]
    script = out / "scripts" / script_name
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / script_name, script)
    (out / output).parent.mkdir(parents=True, exist_ok=True)
    (out / document).parent.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError(f"Historical Swiss MOVE {method} method failed")
    validate_output(out, method)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=sorted(METHODS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.method)


if __name__ == "__main__":
    main()
