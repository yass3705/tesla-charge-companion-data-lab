#!/usr/bin/env python3
"""One isolated, provenance-pinned 16-part Electroverse status census.

Offline verification never calls the supplier. In collect mode, each historical
partition is acquired at most once per job. A 429, incomplete partition, loss of
freshness or runner-budget reserve yields a non-promotable checkpoint.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from v9_rebuild.electroverse import CACHE, read_json, validate_state
from v9_rebuild.electroverse_status import (
    PARTITION_COUNT, STATUS, STATUS_REPORT, IncompleteStatus, cache_fingerprint,
    is_fresh_complete, part_path, run, stage, validate_complete, validate_part,
    validate_partial,
)
from v9_rebuild.orchestrator import artifact_digest, sha256, validated_dependency

SOURCE_RUN = 45024846774
SOURCE_ARTIFACT = 14760747281
SOURCE_ZIP_SHA = "0d3abcc15dc4762b360c5816b6e783accdcafa664442c8ce99b7c0500743a5fe"
SOURCE_FILESET = "c06886fec4b9117e920d7ee50af66d5fb0ebfa00944c452012d771a033a9b965"
SOURCE_COUNT = 22818
BRANCH = "rebuild/v9-20261020"


def checked_source(bundle: Path) -> Path:
    manifest = read_json(bundle / "manifest.json")
    if (manifest.get("status") != "complete" or
            len(manifest.get("sources", [])) != 1):
        raise ValueError("Pinned Electroverse tariff bundle must be complete and single-source")
    source = manifest["sources"][0]
    if (source.get("source") != "FR:electroverse_full" or
            source.get("module") != "electroverse" or
            source.get("artifact_set_sha256") != SOURCE_FILESET):
        raise ValueError("Pinned Electroverse tariff fileset differs from audited generation")
    root = validated_dependency(bundle, "FR:electroverse_full", "electroverse")
    m = validate_state(root)
    if m.get("totalStations") != SOURCE_COUNT:
        raise ValueError("Reviewed tariff source population unexpectedly changed")
    if (root / "v9-electroverse-checkpoint.json").exists():
        raise ValueError("Incomplete tariff checkpoint is not a valid status source")
    return root


def finish_checkpoint(work: Path, out: Path, reason: str, last_report: dict | None) -> None:
    state = validate_partial(work)
    digest, files = artifact_digest(work)
    checkpoint = out / "checkpoints/FR_electroverse_status"
    if checkpoint.exists():
        raise ValueError("Destination checkpoint already exists")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(work), str(checkpoint))
    metadata = {
        "schemaVersion": 1, "source": "FR:electroverse_status",
        "branch": BRANCH, "state": "partial_checkpoint",
        "parentRun": SOURCE_RUN, "parentArtifact": SOURCE_ARTIFACT,
        "parentZipSha256": SOURCE_ZIP_SHA,
        "sourceFingerprint": state["fingerprint"],
        "sha256": digest, "files": files, "verifiedLocations": state["verified_locations"],
        "partitionCount": len(state["partitions"]),
        "reason": reason, "completeSnapshotValidated": False,
    }
    (out / "checkpoint-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (out / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "status": "partial_failure",
        "sources": [{"source": "FR:electroverse_status", "module": "electroverse_status",
                     "status": "failed", "reason": reason,
                     "verifiedLocations": state["verified_locations"],
                     "sourceFingerprint": state["fingerprint"],
                     "lastPartitionReport": last_report}],
    }, indent=2) + "\n")
    print(json.dumps({"result": "checkpointed", "reason": reason,
                      "verifiedLocations": state["verified_locations"],
                      "partitions": len(state["partitions"])}))


def finish_complete(work: Path, out: Path) -> None:
    full = validate_complete(work)
    digest, files = artifact_digest(work)
    target = out / "objects/FR_electroverse_status" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(work), str(target))
    relative = Path("objects/FR_electroverse_status") / digest / STATUS / "manifest.json"
    national = target / STATUS / "manifest.json"
    source = {
        "source": "FR:electroverse_status",
        "module": "electroverse_status",
        "status": "ok", "attempts": 1,
        "artifact": relative.as_posix(),
        "sha256": sha256(national),
        "artifact_set_sha256": digest, "files": files,
    }
    (out / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete", "sources": [source],
        "tariffParent": {"run": SOURCE_RUN, "artifact": SOURCE_ARTIFACT,
                         "zipSha256": SOURCE_ZIP_SHA},
    }, indent=2) + "\n")
    validated_dependency(out, "FR:electroverse_status", "electroverse_status")
    print(json.dumps({"result": "complete", "completedLocations": full["completedLocations"],
                      "partitions": full["partitionCount"], "digest": digest}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mode", choices=("verify", "collect"), required=True)
    ap.add_argument("--budget-seconds", type=int, default=18000)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.out.resolve()
    if (out.exists() or out == root or root in out.parents
            or os.environ.get("GITHUB_REF_NAME") != BRANCH):
        raise ValueError("Fresh isolated status output on the reconstruction branch required")
    if args.budget_seconds != 18000:
        raise ValueError("Unapproved status census budget")
    parent = checked_source(args.bundle.resolve())
    print(json.dumps({"event": "verified_tariff_parent", "run": SOURCE_RUN,
                      "artifact": SOURCE_ARTIFACT, "fileSet": SOURCE_FILESET,
                      "locations": SOURCE_COUNT}))
    if args.mode == "verify":
        print(json.dumps({"result": "verified_only", "supplierCalls": 0}))
        return
    if not os.environ.get("ELECTROVERSE_API_KEY"):
        raise ValueError("Missing status API credential; cannot collect")
    out.mkdir(parents=True, exist_ok=False)
    work = out / "work"
    stage(parent, work)
    started = time.monotonic()
    reason = "all_partitions_complete"
    last_report = None
    for i in range(PARTITION_COUNT):
        # The historical per-partition subprocess can use up to 3600s.
        # Reserve a full partition timeout and 10 min for checkpoint upload.
        if time.monotonic() - started > args.budget_seconds - 4200:
            reason = "runner_budget_reserve"
            break
        try:
            run(work, source=parent, partition=i)
        except IncompleteStatus:
            pass
        last_report = read_json(work / STATUS_REPORT)
        part = validate_part(work, i)
        remaining = part["expectedLocations"] - len(part["entries"])
        print(json.dumps({"event": "partition_result", "partition": i,
                          "expected": part["expectedLocations"],
                          "verified": len(part["entries"]), "remaining": remaining,
                          "errors": len(part["errors"]),
                          "rateLimit": last_report.get("rateLimit")}))
        if (last_report.get("partition") != i
                or last_report.get("sourceFingerprint") != cache_fingerprint(work)):
            raise ValueError("Status report is not from the selected partition")
        if last_report.get("rateLimit"):
            reason = "provider_rate_limited"
            break
        if not is_fresh_complete(part, datetime.now(timezone.utc)):
            reason = "partition_incomplete_or_stale"
            break
    if reason == "all_partitions_complete":
        try:
            finish_complete(work, out)
            state = "complete"
        except (IncompleteStatus, FileNotFoundError):
            reason = "national_finalize_incomplete"
            finish_checkpoint(work, out, reason, last_report)
            state = "checkpointed"
    else:
        finish_checkpoint(work, out, reason, last_report)
        state = "checkpointed"
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fp:
            fp.write("collection_state=" + state + "\n")
            fp.write("stop_reason=" + reason + "\n")


if __name__ == "__main__":
    main()
