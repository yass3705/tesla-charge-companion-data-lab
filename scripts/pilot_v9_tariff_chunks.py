#!/usr/bin/env python3
"""Run the preserved full tariff chunks sequentially in one bounded pilot.

An incomplete/failed chunk is retained, never passed to Production. A successful
chunk boundary can continue in the same job without repeating acquired rows.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v9_rebuild.electroverse import CHUNK_SIZE, MAPPING, read_json, validate_state
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_batch

SOURCE = "FR:electroverse_full"
BRANCH = "rebuild/v9-20261020"


def advance(out, *, specs, chunk_count, execute=run_batch):
    checkpoint = out / "checkpoints/FR_electroverse_full"
    previous_completed = []
    for number in range(chunk_count):
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
        if (state.get("mode") != "full" or state.get("pending") is not None
                or completed != [*previous_completed, number * CHUNK_SIZE]
                or result.get("sources", [{}])[0].get("reason") != "collector_exit_nonzero"):
            raise RuntimeError("Incomplete tariff chunk retained; no automatic provider retry")
        previous_completed = completed
    raise RuntimeError("Tariff collection did not finalize within its mapping chunks")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    if out.exists() or out == ROOT or ROOT in out.parents or os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise ValueError("New isolated pilot directory on reconstruction branch required")
    chunks = max(1, (len(read_json(ROOT / MAPPING)["mappings"]) + CHUNK_SIZE - 1) // CHUNK_SIZE)
    result = advance(out, specs=[s for s in read_sources() if s["id"] == SOURCE], chunk_count=chunks)
    print(json.dumps({"status": result["status"], "chunks": chunks}))


if __name__ == "__main__":
    main()
