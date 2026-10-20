#!/usr/bin/env python3
"""Isolated SuC Tracker catalogue refresh; independent of Tesla/Mac acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

DATA = Path("data/suc-tracker")
OUTPUTS = ("europe.json", "tesla_stations.json", "metadata.json")


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate_output(out: Path) -> dict:
    source = json.loads((out / DATA / OUTPUTS[0]).read_text(encoding="utf-8"))
    catalogue = json.loads((out / DATA / OUTPUTS[1]).read_text(encoding="utf-8"))
    meta = json.loads((out / DATA / OUTPUTS[2]).read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "scripts/suc_tracker"))
    from core import validate_source
    validate_source(source)
    if (not isinstance(catalogue, list) or meta.get("schemaVersion") != 1
            or meta.get("source") != "https://suc-tracker.eu/data/europe.json"
            or meta.get("sourceGeneratedAt") != source.get("generatedAt")
            or meta.get("sourceSha256") != canonical_digest(source)
            or meta.get("catalogueSha256") != canonical_digest(catalogue)
            or meta.get("sourceStationCount") != len(source["stations"])
            or meta.get("exportStationCount") != len(catalogue)
            or len({row.get("id") for row in catalogue}) != len(catalogue)):
        raise ValueError("SuC technical contract invalid")
    return meta


def run(out: Path, *, source: Path | None = None, fixture: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("SuC output must be outside checkout")
    prior = source or ROOT
    if source is not None:
        validate_output(source)
    (out / DATA).mkdir(parents=True, exist_ok=True)
    for name in OUTPUTS:
        shutil.copy2(prior / DATA / name, out / DATA / name)
    shutil.copy2(ROOT / DATA / "access-seed.json", out / DATA / "access-seed.json")
    command = [sys.executable, str(ROOT / "scripts/suc_tracker/update.py"),
               "--out", str(out / DATA), "--config", str(ROOT / "config/countries.json")]
    if fixture is not None:
        command.extend(["--source-json", str(fixture)])
    result = runner(command, cwd=out, capture_output=True, text=True, timeout=180, check=False)
    (out / DATA / "access-seed.json").unlink()
    if result.returncode:
        raise RuntimeError("Historical SuC Tracker method failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    run(args.out, source=args.source)


if __name__ == "__main__":
    main()
