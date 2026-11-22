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


def advance(out, *, specs, chunk_count, execute=run_batch, budget_seconds=75*60, clock=time.monotonic,
            max_provider_windows=None):
    # A new provider window needs 30 min, plus 5 min for artifact upload.
    reserve = 1800 + 300
    if budget_seconds < reserve:
        raise ValueError("Process timeout and upload reserve required")
    checkpoint = out / "checkpoints/FR_electroverse_full"
    started = clock()
    saved = checkpoint / "v9-electroverse-checkpoint.json"
    previous_completed = read_json(saved)["completed"] if saved.is_file() else []
    if previous_completed != list(range(0, len(previous_completed) * CHUNK_SIZE, CHUNK_SIZE)):
        raise ValueError("Checkpoint chunk offsets are inconsistent")
    previous_cursor = None
    completed_provider_windows = 0
    if max_provider_windows is not None and max_provider_windows < 1:
        raise ValueError("Maximum provider windows must be positive")
    while len(previous_completed) < chunk_count:
        if max_provider_windows is not None and completed_provider_windows >= max_provider_windows:
            if not (out / "checkpoint-manifest.json").is_file():
                raise RuntimeError("No durable checkpoint for bounded provider stop")
            validate_state(checkpoint, require_complete=False)
            return {"status": "checkpointed", "reason": "pilot_provider_window_limit",
                    "completeSnapshotValidated": False}
        if clock() - started > budget_seconds - reserve:
            if (out / "checkpoint-manifest.json").is_file():
                validate_state(checkpoint, require_complete=False)
                return {"status": "checkpointed", "reason": "runner_budget",
                        "completeSnapshotValidated": False}
            raise RuntimeError("Not enough time for first provider window")
        number = len(previous_completed)
        result = execute(specs, out, workers=1, attempts=1)
        completed_provider_windows += 1
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
        guarded_finish = len(specs) == 1 and specs[0].get("finish_remaining_chunks") is True
        if guarded_finish and (completed[:len(previous_completed)] != previous_completed
                               or completed != list(range(0, len(completed) * CHUNK_SIZE, CHUNK_SIZE))):
            raise RuntimeError("Full-run completion cursor lost its verified chunk lineage")
        # Continue only after a fully successful historical chunk boundary.
        # A failure/timeout is NOT an invitation to consume more supplier calls.
        reason = result.get("sources", [{}])[0].get("reason")
        pending = state.get("pending")
        if pending is not None:
            expected_offset = len(completed) * CHUNK_SIZE if guarded_finish else number * CHUNK_SIZE
            if (not isinstance(pending, dict) or pending.get("offset") != expected_offset
                    or not isinstance(pending.get("pks"), list) or not pending["pks"]
                    or len(set(pending["pks"])) != len(pending["pks"])):
                raise RuntimeError("Invalid pending Electroverse cursor; no automatic provider retry")
        cursor = (tuple(completed), pending["offset"] if pending else None,
                  len(pending["pks"]) if pending else 0)
        if cursor == previous_cursor:
            raise RuntimeError("Electroverse checkpoint did not advance")
        previous_cursor = cursor
        if (reason == "collector_window_budget" and state.get("mode") == "full"
                and (completed == previous_completed or guarded_finish) and pending is not None):
            # One audited diagnostic window per run until provider stability is demonstrated.
            if max_provider_windows is not None and completed_provider_windows >= max_provider_windows:
                return {"status": "checkpointed", "reason": "pilot_provider_window_limit",
                        "completeSnapshotValidated": False}
            continue
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
    p.add_argument("--max-provider-windows", type=int)
    p.add_argument("--finish-remaining", action="store_true",
                   help="One authorized long run across all remaining France chunks; stop at first failure")
    a = p.parse_args()
    if a.finish_remaining and (a.window_budget_seconds != 16200 or a.max_provider_windows != 1
                               or not a.incoming):
        raise ValueError("Full completion requires a pinned parent, 16200s budget and exactly one process")
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
    if a.finish_remaining:
        if len(specs) != 1 or specs[0]["id"] != SOURCE or specs[0]["module"] != "electroverse" or specs[0]["mode"] != "full":
            raise ValueError("Unexpected Electroverse source for guarded full completion")
        specs = [dict(specs[0], finish_remaining_chunks=True)]
    result = advance(out, specs=specs, chunk_count=chunks,
                     max_provider_windows=a.max_provider_windows)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("collection_state=" + result["status"] + "\n")
    print(json.dumps({"status": result["status"], "chunks": chunks}))


if __name__ == "__main__":
    main()
