#!/usr/bin/env python3
"""Build the existing exact France Electroverse eMSP overlay in isolation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from v9_rebuild.electroverse import ROOT, stage_state, validate_state
from v9_rebuild.electroverse_status import STATUS, cache_fingerprint, validate_complete


OUT = Path("data/platforms/electroverse/france-evse")
REPORT = Path("reports/electroverse/status-gate-postbuild.json")
VALIDATED = Path("data/platforms/electroverse/validated-mappings")
DIRECT = (
    Path("data/operator_direct/driveco_evse_tariffs.json"),
    Path("data/operator_direct/powerdot_evse_technical_inventory.json"),
    Path("data/operator_direct/vianeo_official_identity_map.json"),
)


def copy_input(source: Path, out: Path, relative: Path) -> None:
    src = source / relative
    if not src.exists():
        raise FileNotFoundError(src)
    dest = out / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)


def validate_output(out: Path) -> dict:
    manifest = json.loads((out / OUT / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("country") != "FR" or manifest.get("dataset") != "electroverse-france-evse-national-overlay"
            or not isinstance(manifest.get("tiles"), list)
            or manifest.get("tileCount") != len(manifest["tiles"])):
        raise ValueError("Invalid Electroverse France overlay manifest")
    seen = set()
    total_rows = 0
    for tile in manifest["tiles"]:
        name = tile.get("file")
        if not isinstance(name, str) or name in seen or Path(name).name != name:
            raise ValueError("Duplicate or unsafe overlay tile")
        seen.add(name)
        path = out / OUT / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != tile.get("sha256") or path.stat().st_size != tile.get("bytes"):
            raise ValueError("Overlay tile integrity mismatch")
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or not isinstance(payload.get("emspOffers"), list):
            raise ValueError("Invalid overlay tile schema")
        if tile.get("count") != len(payload["emspOffers"]):
            raise ValueError("Overlay tile offer count mismatch")
        total_rows += len(payload["emspOffers"])
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    if any(report.get(field) != 0 for field in ("invalidPublishedSourceRefs", "missingProvenanceOffers", "statusPkConflicts")):
        raise ValueError("Overlay status gate failed")
    if report.get("offers") != total_rows:
        raise ValueError("Overlay audit count differs from tiles")
    return manifest


def run(out: Path, *, source: Path = ROOT, status_source: Path, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Overlay output must be outside checkout")
    validate_complete(status_source, require_fresh_parts=False)
    validate_state(source)
    status_manifest = json.loads((status_source / STATUS / "manifest.json").read_text(encoding="utf-8"))
    generated = datetime.fromisoformat(status_manifest["generatedAt"].replace("Z", "+00:00"))
    if not 0 <= (datetime.now(timezone.utc) - generated).total_seconds() <= 72 * 3600:
        raise ValueError("National status ledger is outside the existing 72-hour overlay window")
    out.mkdir(parents=True, exist_ok=True)
    stage_state(source, out)
    copy_input(status_source, out, STATUS)
    copy_input(ROOT, out, VALIDATED)
    for relative in DIRECT:
        copy_input(ROOT, out, relative)
    if cache_fingerprint(out) != status_manifest["sourceFingerprint"]:
        raise ValueError("Status ledger and tariff cache have different provenance")
    for script in ("build_electroverse_france_evse_overlay.mjs", "audit_electroverse_status_gate_postbuild.mjs"):
        completed = runner(["node", str(ROOT / "scripts" / script)], cwd=out,
                           capture_output=True, text=True, check=False, timeout=1200)
        if completed.returncode:
            raise RuntimeError(f"Historical Electroverse overlay script failed: {script}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--status-source", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, source=args.source, status_source=args.status_source)


if __name__ == "__main__":
    main()
