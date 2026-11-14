#!/usr/bin/env python3
"""Bounded real status checkpoint pilot; never a publishable national snapshot."""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v9_rebuild.electroverse_status import PARTS, STATUS, STATUS_REPORT, validate_partial
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_batch

SOURCE = "FR:electroverse_status"
CHECKPOINT = Path("checkpoints/FR_electroverse_status")
BRANCH = "rebuild/v9-20261020"


def read(path):
    return json.loads(path.read_bytes())


def verify_package(folder, *, head, run_id):
    """Bind downloaded partial state to this controlled run and its full file set."""
    m = read(folder / "checkpoint-manifest.json")
    if (m.get("state") != "partial_checkpoint" or m.get("source") != SOURCE
            or m.get("branch") != BRANCH or m.get("headSha") != head
            or m.get("runId") != run_id or not re.fullmatch(r"[0-9a-f]{40}", head)):
        raise ValueError("Checkpoint provenance mismatch")
    state = folder / CHECKPOINT
    if any(p.is_symlink() for p in folder.rglob("*")):
        raise ValueError("Checkpoint symlink forbidden")
    validate_partial(state)
    digest, files = artifact_digest(state)
    if digest != m.get("sha256") or files != m.get("files"):
        raise ValueError("Checkpoint file integrity mismatch")
    if any((state / STATUS / name).exists() for name in ("manifest.json", "evses.json.gz")):
        raise ValueError("Partial checkpoint contains national publication")
    return state


def verify_resume(before, after, report):
    """The same observation window must retain every successful prior response."""
    selected = report["partition"]
    prior = {p["partition"]: p for p in before["partitions"]}
    current = {p["partition"]: p for p in after["partitions"]}
    if before["fingerprint"] != after["fingerprint"] or not set(prior) <= set(current):
        raise ValueError("Resume lost a partition or changed its cache")
    for index, old in prior.items():
        new = current[index]
        if index != selected and old != new:
            raise ValueError("Resume changed an independent partition")
        if index == selected:
            if old["startedAt"] != new["startedAt"]:
                raise ValueError("Resume reset the observation window")
            if any(new["entries"].get(k) != v for k, v in old["entries"].items()):
                raise ValueError("Resume lost successful source responses")


def pilot(out, *, incoming=None):
    out = out.resolve()
    head, run_id = os.environ["GITHUB_SHA"], int(os.environ["GITHUB_RUN_ID"])
    if (os.environ.get("GITHUB_REF_NAME") != BRANCH or out.exists()
            or out == ROOT or ROOT in out.parents):
        raise ValueError("New isolated pilot directory required")
    before = None
    if incoming:
        previous = verify_package(incoming, head=head, run_id=run_id)
        before = validate_partial(previous)
        shutil.copytree(previous, out / CHECKPOINT)
    # Historical collector settings, deliberately bounded for a resume pilot.
    os.environ.update(ELECTROVERSE_STATUS_RUN_LIMIT="30",
                      ELECTROVERSE_STATUS_FAILURE_BUDGET="6",
                      ELECTROVERSE_STATUS_REQUEST_DELAY_MS="800")
    specs = [s for s in read_sources() if s["id"] == SOURCE]
    result = run_batch(specs, out, workers=1, attempts=1)
    if result["status"] != "partial_failure" or result["sources"][0].get("reason") != "collector_exit_nonzero":
        raise ValueError("Expected a bounded partial checkpoint, not a promoted collection")
    state = out / CHECKPOINT
    after = validate_partial(state)
    report = read(state / STATUS_REPORT)
    if report.get("complete") is not False or not 0 < report.get("newSuccessful", 0) <= 30:
        raise ValueError("No demonstrated successful bounded acquisition")
    if before:
        verify_resume(before, after, report)
    if any(p.is_file() for p in (out / "objects").glob("**/*")):
        raise ValueError("Partial acquisition was promoted into immutable objects")
    digest, files = artifact_digest(state)
    manifest = {"schemaVersion": 1, "state": "partial_checkpoint", "source": SOURCE,
                "branch": BRANCH, "headSha": head, "runId": run_id,
                "sha256": digest, "files": files, "resumed": before is not None,
                "nationalSnapshotValidated": False, "report": report}
    (out / "checkpoint-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify_package(out, head=head, run_id=run_id)
    return {k: v for k, v in manifest.items() if k != "files"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--incoming", type=Path)
    a = p.parse_args()
    print(json.dumps(pilot(a.out, incoming=a.incoming)))
