#!/usr/bin/env python3
"""Run the preserved full tariff chunks sequentially in one bounded pilot.

An incomplete/failed chunk is retained, never passed to Production. A successful
chunk boundary can continue in the same job without repeating acquired rows.
"""
import argparse
import json
import shutil
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v9_rebuild.electroverse import CHUNK_SIZE, MAPPING, read_json, validate_state
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_batch

SOURCE = "FR:electroverse_full"
BRANCH = "rebuild/v9-20261020"


def verify_checkpoint(incoming, *, expected_sha, expected_head, expected_run):
    manifest = read_json(incoming / "checkpoint-manifest.json")
    state = incoming / "checkpoints/FR_electroverse_full"
    if (any(path.is_symlink() for path in incoming.rglob("*"))
            or manifest.get("source") != SOURCE or manifest.get("branch") != BRANCH
            or manifest.get("headSha") != expected_head or manifest.get("runId") != expected_run
            or manifest.get("state") != "partial_checkpoint"
            or manifest.get("completeSnapshotValidated") is not False
            or manifest.get("sha256") != expected_sha
            or artifact_digest(state) != (expected_sha, manifest.get("files"))):
        raise ValueError("Untrusted Electroverse tariff checkpoint")
    validate_state(state, require_complete=False)
    if (state / MAPPING).read_bytes() != (ROOT / MAPPING).read_bytes():
        raise ValueError("Checkpoint mapping and pinned collector differ")
    return state


def restore_checkpoint(incoming, out, *, expected_sha, expected_head, expected_run):
    state = verify_checkpoint(incoming, expected_sha=expected_sha, expected_head=expected_head,
                              expected_run=expected_run)
    shutil.copytree(state, out / "checkpoints/FR_electroverse_full")


def advance(out, *, specs, chunk_count, execute=run_batch, budget_seconds=75*60, clock=time.monotonic):
    if budget_seconds < 2700:
        raise ValueError("Process timeout and upload reserve required")
    checkpoint = out / "checkpoints/FR_electroverse_full"
    started = clock()
    saved = checkpoint / "v9-electroverse-checkpoint.json"
    previous_completed = read_json(saved)["completed"] if saved.is_file() else []
    if previous_completed != list(range(0, len(previous_completed) * CHUNK_SIZE, CHUNK_SIZE)):
        raise ValueError("Checkpoint chunk offsets are inconsistent")
    for number in range(len(previous_completed), chunk_count):
        if clock() - started > budget_seconds - 2700:
            raise RuntimeError("Tariff checkpoint retained at time budget; no new provider calls")
        result = execute(specs, out, workers=1, attempts=1)
        if result.get("status") == "complete":
            return result
        validate_state(checkpoint, require_complete=False)
        state = read_json(checkpoint / "v9-electroverse-checkpoint.json")
        digest, files = artifact_digest(checkpoint)
        (out / "checkpoint-manifest.json").write_text(json.dumps({
            "schemaVersion": 1, "source": SOURCE, "state": "partial_checkpoint",
            "headSha": os.environ["GITHUB_SHA"], "branch": BRANCH,
            "runId": int(os.environ["GITHUB_RUN_ID"]), "sha256": digest,
            "files": files, "completeSnapshotValidated": False,
        }, indent=2) + "\n")
        completed = state.get("completed", [])
        # Continue only after a fully successful historical chunk boundary.
        # A failure/timeout is NOT an invitation to consume more supplier calls.
        reason = result.get("sources", [{}])[0].get("reason")
        if (reason == "collector_window_budget" and state.get("mode") == "full"
                and completed == previous_completed and (state.get("pending") or {}).get("offset") == number * CHUNK_SIZE
                and state["pending"].get("pks")):
            return {"status": "checkpointed", "reason": reason, "completeSnapshotValidated": False}
        if (state.get("mode") != "full" or state.get("pending") is not None
                or completed != [*previous_completed, number * CHUNK_SIZE]
                or result.get("sources", [{}])[0].get("reason") != "collector_exit_nonzero"):
            raise RuntimeError("Incomplete tariff chunk retained; no automatic provider retry")
        previous_completed = completed
    raise RuntimeError("Tariff collection did not finalize within its mapping chunks")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--incoming", type=Path)
    p.add_argument("--expected-sha")
    p.add_argument("--expected-head")
    p.add_argument("--expected-run", type=int)
    p.add_argument("--window-budget-seconds", type=int)
    a = p.parse_args()
    out = a.out.resolve()
    if out.exists() or out == ROOT or ROOT in out.parents or os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise ValueError("New isolated pilot directory on reconstruction branch required")
    if a.incoming:
        if not all((a.expected_sha, a.expected_head, a.expected_run)):
            raise ValueError("Checkpoint receipt required")
        restore_checkpoint(a.incoming, out, expected_sha=a.expected_sha,
                           expected_head=a.expected_head, expected_run=a.expected_run)
    chunks = max(1, (len(read_json(ROOT / MAPPING)["mappings"]) + CHUNK_SIZE - 1) // CHUNK_SIZE)
    specs = [s for s in read_sources() if s["id"] == SOURCE]
    if a.window_budget_seconds is not None:
        specs = [dict(s, window_budget_seconds=a.window_budget_seconds) for s in specs]
    result = advance(out, specs=specs, chunk_count=chunks)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("collection_state=" + result["status"] + "\n")
    print(json.dumps({"status": result["status"], "chunks": chunks}))


if __name__ == "__main__":
    main()
