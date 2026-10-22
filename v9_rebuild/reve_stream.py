#!/usr/bin/env python3
"""Isolate the preserved REVE two-stream collector and its resumable state."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/reve_es_stream_collect.py")
DATA = Path("data/spain_reve/full_20261018")
FILES = ("tariff_status_stream_state.json", "reve_connector_tariffs_raw.json.gz",
         "reve_operational_status_raw.json.gz", "tariff_status_stream_last_run.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_data(folder: Path, *, require_complete: bool) -> dict:
    from scripts.reve_es_stream_collect import status_key, tariff_key, validate_checkpoint
    state = json.loads((folder / FILES[0]).read_text(encoding="utf-8"))
    with gzip.open(folder / FILES[1], "rt", encoding="utf-8") as file:
        tariffs = json.load(file)
    with gzip.open(folder / FILES[2], "rt", encoding="utf-8") as file:
        statuses = json.load(file)
    report = json.loads((folder / FILES[3]).read_text(encoding="utf-8"))
    if (not isinstance(tariffs, dict) or not isinstance(statuses, dict)
            or not isinstance(report, dict) or state.get("schemaVersion") != 1
            or state.get("country") != "ES" or state.get("source") != "REVE"
            or state.get("integrationStatus") != "PRE_INTEGRATION_ONLY"
            or report.get("mode") not in {"collect", "seed-probe"}
            or report.get("requestsAttempted", 0) > 5
            or report.get("stateAfter") != state
            or any(tariff_key(row) != key for key, row in tariffs.items())
            or any(status_key(row) != key for key, row in statuses.items())):
        raise ValueError("REVE checkpoint format invalid")
    validate_checkpoint(state, tariffs, statuses)
    if require_complete and (state.get("complete") is not True
                             or report.get("stoppedAfterError")
                             or report.get("requestsAttempted", 0) != report.get("requestsSucceeded", 0)):
        raise ValueError("REVE source streams incomplete")
    return state


def validate_checkpoint(checkpoint: Path) -> Path | None:
    pointer = checkpoint / "current.json"
    if not pointer.exists():
        if checkpoint.exists() and any(checkpoint.iterdir()):
            raise ValueError("REVE checkpoint pointer missing")
        return None
    manifest = json.loads(pointer.read_text(encoding="utf-8"))
    sha = manifest.get("sha256")
    if not isinstance(sha, dict) or set(sha) != set(FILES):
        raise ValueError("REVE checkpoint manifest invalid")
    generation = manifest.get("generation")
    if not isinstance(generation, str) or len(generation) != 64 or any(c not in "0123456789abcdef" for c in generation):
        raise ValueError("REVE checkpoint generation invalid")
    folder = checkpoint / "generations" / generation
    if any(not (folder / name).is_file() or digest(folder / name) != sha[name] for name in FILES):
        raise ValueError("REVE checkpoint SHA mismatch")
    validate_data(folder, require_complete=False)
    return folder


def save_checkpoint(folder: Path, checkpoint: Path) -> None:
    validate_data(folder, require_complete=False)
    sha = {name: digest(folder / name) for name in FILES}
    generation = hashlib.sha256(json.dumps(sha, sort_keys=True).encode()).hexdigest()
    target = checkpoint / "generations" / generation
    if target.exists() and any(not (target / name).is_file() or digest(target / name) != sha[name]
                               for name in FILES):
        shutil.rmtree(target)
    if not target.exists():
        target.mkdir(parents=True)
        for name in FILES:
            shutil.copy2(folder / name, target / name)
    pointer = checkpoint / "current.json.tmp"
    pointer.write_text(json.dumps({"generation": generation, "sha256": sha}, sort_keys=True) + "\n")
    pointer.replace(checkpoint / "current.json")
    validate_checkpoint(checkpoint)


def validate_output(out: Path) -> dict:
    return validate_data(out / DATA, require_complete=True)


def run(out: Path, checkpoint: Path, *, runner=subprocess.run) -> None:
    out, checkpoint = out.resolve(), checkpoint.resolve()
    if (out == ROOT or ROOT in out.parents or checkpoint == ROOT or ROOT in checkpoint.parents
            or out == checkpoint or out in checkpoint.parents or checkpoint in out.parents):
        raise ValueError("REVE output/checkpoint must be distinct and off checkout")
    previous = validate_checkpoint(checkpoint)
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    folder = out / DATA
    folder.mkdir(parents=True, exist_ok=True)
    if previous:
        for name in FILES:
            shutil.copy2(previous / name, folder / name)
    env = os.environ.copy()
    env["REVE_DATA_DIR"] = str(folder)
    result = runner([sys.executable, str(script), "--collect"], cwd=out, env=env,
                    capture_output=True, text=True, timeout=900, check=False)
    if all((folder / name).is_file() for name in FILES):
        save_checkpoint(folder, checkpoint)
    if result.returncode:
        raise RuntimeError("Historical REVE stream batch failed; validated checkpoint retained")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.checkpoint)


if __name__ == "__main__":
    main()
