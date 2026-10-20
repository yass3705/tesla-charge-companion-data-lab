#!/usr/bin/env python3
"""Isolated wrapper for the preserved Electroverse France daily/full scripts.

The extraction, selection, API, pagination and tariff projection remain in
the existing JavaScript files. This module only stages state and validates it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("data/electroverse/tariff_cache")
MAPPING = Path("data/electroverse/irve_location_mapping.json")
INVENTORY = Path("data/electroverse/inventory")
REPORTS = Path("reports/electroverse")
CHUNK_SIZE = 6000  # Preserved from the four legacy full-refresh jobs.


class IncompleteCollection(RuntimeError):
    """A retryable chunk failed after retaining its successful shard writes."""


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def stage_state(source: Path, target: Path) -> None:
    """Copy mutable inputs; hard links would let JS overwrite the checkout."""
    if source.resolve() == target.resolve() or source.resolve() in target.resolve().parents:
        raise ValueError("Electroverse state must be copied to an independent directory")
    for relative in (CACHE, MAPPING, INVENTORY):
        src = source / relative
        if not src.exists():
            if relative == INVENTORY:
                continue
            raise FileNotFoundError(src)
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)
    for name in ("hybrid-refresh-failures.json", "daily-delta.json", "incremental-selection.json"):
        src = source / REPORTS / name
        if src.is_file():
            dest = target / REPORTS / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    (target / REPORTS).mkdir(parents=True, exist_ok=True)
    checkpoint = source / "v9-electroverse-checkpoint.json"
    if checkpoint.is_file():
        shutil.copy2(checkpoint, target / checkpoint.name)


def shard_index(pk: str) -> int:
    return hashlib.sha1(pk.encode("utf-8")).digest()[0] % 128


def validate_state(out: Path, *, require_complete: bool = True) -> dict:
    """Check technical integrity without historical volume thresholds."""
    state_paths = [out / MAPPING, out / CACHE, out / INVENTORY, out / REPORTS, out / "v9-electroverse-checkpoint.json"]
    if out.is_symlink() or any(path.is_symlink() or (path.is_dir() and any(child.is_symlink() for child in path.rglob("*"))) for path in state_paths):
        raise ValueError("Symlink is forbidden in Electroverse staged state")
    mapping = read_json(out / MAPPING)
    if not isinstance(mapping.get("mappings"), list):
        raise ValueError("Invalid Electroverse mapping")
    manifest = read_json(out / CACHE / "manifest.json")
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != 128:
        raise ValueError("Electroverse manifest must enumerate all 128 shards")
    seen_ids: set[str] = set()
    actual_total = 0
    for position, meta in enumerate(shards):
        if not isinstance(meta, dict) or meta.get("shard") != position or meta.get("file") != f"shard-{position:03d}.json":
            raise ValueError("Invalid shard order or filename")
        path = out / CACHE / meta["file"]
        shard = read_json(path)
        if shard.get("shard") != position or shard.get("shardCount") != 128 or not isinstance(shard.get("stations"), dict):
            raise ValueError(f"Invalid shard schema: {position}")
        if meta.get("count") != len(shard["stations"]) or meta.get("sizeBytes") != path.stat().st_size:
            raise ValueError(f"Shard manifest mismatch: {position}")
        for pk, row in shard["stations"].items():
            if (pk in seen_ids or shard_index(pk) != position or not isinstance(row, dict)
                    or str(row.get("electroverseLocationPk")) != pk or not isinstance(row.get("tariff"), dict)
                    or not isinstance(row.get("tariffHash"), str)):
                raise ValueError(f"Invalid or duplicate station in shard {position}: {pk}")
            seen_ids.add(pk)
        actual_total += len(shard["stations"])
    if manifest.get("totalStations") != actual_total:
        raise ValueError("Electroverse total differs from shard contents")
    if require_complete:
        failure_path = out / REPORTS / "hybrid-refresh-failures.json"
        if failure_path.is_file() and read_json(failure_path).get("failures"):
            raise IncompleteCollection("Unresolved Electroverse locations remain")
        checkpoint = out / "v9-electroverse-checkpoint.json"
        if checkpoint.is_file() and read_json(checkpoint).get("pending"):
            raise IncompleteCollection("Electroverse chunk remains pending")
    return manifest


def run_script(name: str, out: Path, env: dict[str, str], runner=subprocess.run) -> int:
    result = runner(["node", str(ROOT / "scripts" / name)], cwd=out, env=env,
                    capture_output=True, text=True, check=False, timeout=18000)
    return result.returncode


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(out: Path, mode: str, *, source: Path = ROOT, resume: Path | None = None,
        runner=subprocess.run, chunk_size: int = CHUNK_SIZE, max_chunks: int | None = None) -> None:
    if mode not in {"daily", "full"} or chunk_size < 1 or (max_chunks is not None and max_chunks < 1):
        raise ValueError("Unsupported Electroverse mode or chunk size")
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Electroverse output must be outside the checkout")
    out.mkdir(parents=True, exist_ok=True)
    if not (out / CACHE / "manifest.json").is_file():
        stage_state(resume or source, out)
    validate_state(out, require_complete=False)
    env = os.environ.copy()
    if not env.get("ELECTROVERSE_API_KEY"):
        raise ValueError("ELECTROVERSE_API_KEY is required")
    checkpoint_path = out / "v9-electroverse-checkpoint.json"
    checkpoint = read_json(checkpoint_path) if checkpoint_path.is_file() else {"mode": mode, "completed": [], "pending": None}
    if checkpoint.get("mode") != mode:
        raise ValueError("Checkpoint mode differs from requested mode")
    if mode == "daily":
        if not checkpoint.get("pending"):
            if run_script("electroverse_daily_delta_selector.mjs", out, env, runner):
                raise IncompleteCollection("Daily selector failed")
            selection = read_json(out / REPORTS / "incremental-selection.json")
            if not isinstance(selection.get("selected"), list):
                raise ValueError("Daily selection contract invalid")
            checkpoint["pending"] = {"offset": 0, "pks": [str(row["pk"]) for row in selection["selected"]]}
            write_json(checkpoint_path, checkpoint)
        tasks = [(0, checkpoint["pending"]["pks"])]
    else:
        rows = read_json(out / MAPPING)["mappings"]
        tasks = [(offset, min(chunk_size, len(rows) - offset)) for offset in range(0, len(rows), chunk_size)]
        if not tasks:
            tasks = [(0, 0)]
    processed = 0
    for offset, task in tasks:
        if offset in checkpoint["completed"]:
            continue
        if max_chunks is not None and processed >= max_chunks:
            validate_state(out, require_complete=False)
            raise IncompleteCollection("More Electroverse chunks remain; resume from this checkpoint")
        pending = checkpoint.get("pending")
        if pending and pending["offset"] != offset:
            raise ValueError("Checkpoint pending offset is inconsistent")
        if pending:
            selected_pks = pending["pks"]
            selection = {"generatedAt": None, "storage": "sharded-v1", "policy": {"mode": "retry_failed_chunk"},
                         "selectedCount": len(selected_pks), "selected": [{"pk": pk, "reason": "retry_failed_chunk"} for pk in selected_pks]}
            write_json(out / REPORTS / "incremental-selection.json", selection)
        elif mode == "full":
            env["CHUNK_OFFSET"] = str(offset)
            env["CHUNK_COUNT"] = str(chunk_size)
            if run_script("electroverse_force_chunk_selection.mjs", out, env, runner):
                raise IncompleteCollection(f"Full selector failed at offset {offset}")
            selection = read_json(out / REPORTS / "incremental-selection.json")
            if selection.get("selectedCount") != task:
                raise ValueError("Full selection does not match the mapping slice")
        else:
            selection = read_json(out / REPORTS / "incremental-selection.json")
        selected_pks = [str(row["pk"]) for row in selection.get("selected", [])]
        if len(selected_pks) != len(set(selected_pks)):
            raise ValueError("Duplicate selected Electroverse location")
        checkpoint["pending"] = {"offset": offset, "pks": selected_pks}
        write_json(checkpoint_path, checkpoint)
        if selected_pks:
            rc = run_script("electroverse_hybrid_refresh.mjs", out, env, runner)
            failure_path = out / REPORTS / "hybrid-refresh-failures.json"
            failures = read_json(failure_path).get("failures") if failure_path.is_file() else None
            if rc or not isinstance(failures, list) or failures:
                if isinstance(failures, list) and failures:
                    retry_pks = [str(row["pk"]) for row in failures if isinstance(row, dict) and row.get("pk")]
                    if not retry_pks or len(retry_pks) != len(failures):
                        raise IncompleteCollection("Failure report lacks retryable IDs")
                    checkpoint["pending"]["pks"] = retry_pks
                    write_json(checkpoint_path, checkpoint)
                raise IncompleteCollection(f"Electroverse chunk {offset} failed")
        checkpoint["pending"] = None
        checkpoint["completed"].append(offset)
        write_json(checkpoint_path, checkpoint)
        validate_state(out, require_complete=False)
        processed += 1
    validate_state(out)
    checkpoint_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("daily", "full"), required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--max-chunks", type=int)
    args = parser.parse_args()
    run(args.out, args.mode, resume=args.resume, max_chunks=args.max_chunks)


if __name__ == "__main__":
    main()
