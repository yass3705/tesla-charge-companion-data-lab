#!/usr/bin/env python3
"""Run preserved EVGO public hydration and three offline transforms in isolation."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.orchestrator import ROOT

BASE = Path("reports/morocco/evgo")
HYDRATION = BASE / "latest-pin-hydration.json"
STATUS = BASE / "latest-status-overlay.json"
NORMALIZED = BASE / "latest-normalized-stations.json"
OUTPUT = BASE / "latest-production-stations.json"
PROBE_OUTPUT = Path("artifacts/morocco-evgo-pin-hydration/summary.json")
SCRIPTS = (
    Path("scripts/morocco_evgo_pin_hydration_probe.py"),
    Path("scripts/morocco_evgo_status_overlay_from_hydration.py"),
    Path("scripts/morocco_evgo_normalize.py"),
    Path("scripts/morocco_evgo_apply_fresh_status_overlay.py"),
)
STATUS_FIELDS = ("status", "isAvailable", "isLongTermUnavailable", "isTemporarilyUnavailable")


def operational_class(evse: dict) -> str:
    status = str(evse.get("status") or "").lower()
    if evse.get("isLongTermUnavailable") or evse.get("isTemporarilyUnavailable"):
        return "out_of_service"
    if status in {"charging", "suspendedev", "finishing", "preparing"}:
        return "occupied_or_active_session"
    if status == "available" and evse.get("isAvailable") is True:
        return "available"
    if status in {"unavailable", "faulted", "offline", "unknown"}:
        return "out_of_service"
    return "unknown"


def validate_output(out: Path) -> dict:
    hydration = json.loads((out / HYDRATION).read_text(encoding="utf-8"))
    status = json.loads((out / STATUS).read_text(encoding="utf-8"))
    base = json.loads((out / NORMALIZED).read_text(encoding="utf-8"))
    production = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    if (status.get("source_generated_at") != hydration.get("generated_at")
            or base.get("source_generated_at") != hydration.get("generated_at")
            or production.get("source_generated_at") != hydration.get("generated_at")
            or base.get("source_api_version") != status.get("source_api_version")
            or status.get("policy", {}).get("derived_from_same_run_public_hydration") is not True
            or production.get("policy", {}).get("fresh_native_status_overlay_applied") is not True):
        raise ValueError("EVGO source provenance or version mismatch")
    source_rows = {int(row["locationId"]): row for row in base.get("stations") or []}
    overlay_rows = {int(row["locationId"]): row for row in status.get("stations") or []}
    final_rows = {int(row["locationId"]): row for row in production.get("stations") or []}
    if (len(source_rows) != len(base.get("stations") or [])
            or len(overlay_rows) != len(status.get("stations") or [])
            or len(final_rows) != len(production.get("stations") or [])
            or set(source_rows) != set(overlay_rows) or set(source_rows) != set(final_rows)):
        raise ValueError("EVGO station identity mismatch")
    evse_total = 0
    for lid, source in source_rows.items():
        overlay = overlay_rows[lid]
        final = final_rows[lid]
        src_evses = {str(row["id"]): row for row in source.get("evses") or []}
        ov_evses = {str(row["id"]): row for row in overlay.get("evses") or []}
        dst_evses = {str(row["id"]): row for row in final.get("evses") or []}
        if (len(src_evses) != len(source.get("evses") or [])
                or len(ov_evses) != len(overlay.get("evses") or [])
                or len(dst_evses) != len(final.get("evses") or [])
                or set(src_evses) != set(ov_evses) or set(src_evses) != set(dst_evses)):
            raise ValueError("EVGO EVSE identity mismatch")
        evse_total += len(src_evses)
        for eid, original in src_evses.items():
            expected = dict(original)
            for field in STATUS_FIELDS:
                expected[field] = ov_evses[eid].get(field)
            expected["operational_class"] = operational_class(expected)
            if dst_evses[eid] != expected:
                raise ValueError("EVGO non-status field or native state mutated")
        for field in ("latitude", "longitude", "operator_cpo_candidate", "tariff_channel"):
            if final.get(field) != source.get(field):
                raise ValueError("EVGO station metadata mutated")
    summary = production.get("summary") or {}
    if summary.get("station_count") != len(final_rows) or summary.get("evse_count") != evse_total:
        raise ValueError("EVGO internal counts inconsistent")
    meta = json.loads((out / "hydration-sha256.json").read_text(encoding="utf-8"))
    if meta.get("sha256") != hashlib.sha256((out / HYDRATION).read_bytes()).hexdigest():
        raise ValueError("EVGO hydration SHA mismatch")
    return production


def run(out: Path, fixture: Path | None = None) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("EVGO processing must run outside checkout")
    for script in SCRIPTS:
        target = out / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / script, target)
    (out / BASE).mkdir(parents=True, exist_ok=True)
    if fixture is None:
        result = subprocess.run([sys.executable, str(out / SCRIPTS[0])], cwd=out, capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError("Historical EVGO public hydration failed")
        shutil.copy2(out / PROBE_OUTPUT, out / HYDRATION)
    else:
        shutil.copy2(fixture, out / HYDRATION)
    (out / "hydration-sha256.json").write_text(json.dumps({"source": str(HYDRATION), "sha256": hashlib.sha256((out / HYDRATION).read_bytes()).hexdigest()}) + "\n")
    for script in SCRIPTS[1:]:
        result = subprocess.run([sys.executable, str(out / script)], cwd=out, capture_output=True, text=True, timeout=300)
        if result.returncode:
            raise RuntimeError(f"Historical EVGO transform failed: {script}: {result.stderr[-400:]}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
