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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v9_rebuild.electroverse import CACHE, read_json, validate_state
from v9_rebuild.electroverse_status import (
    FRESH_SECONDS, PARTITION_COUNT, STATUS, STATUS_REPORT, IncompleteStatus,
    cache_fingerprint, is_fresh_complete, part_path, run, stage, validate_complete,
    validate_part, validate_partial,
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



def checked_status_checkpoint(
    bundle: Path, parent: Path, *, fileset_sha: str,
    verified_locations: int, error_count: int, partition_count: int,
) -> tuple[Path, dict, dict]:
    """Validate an explicitly pinned checkpoint before any supplier call."""
    metadata = read_json(bundle / "checkpoint-manifest.json")
    collection = read_json(bundle / "manifest.json")
    root = bundle / "checkpoints/FR_electroverse_status"
    if (metadata.get("schemaVersion") != 1 or
            metadata.get("source") != "FR:electroverse_status" or
            metadata.get("branch") != BRANCH or
            metadata.get("state") != "partial_checkpoint" or
            metadata.get("completeSnapshotValidated") is not False or
            metadata.get("parentRun") != SOURCE_RUN or
            metadata.get("parentArtifact") != SOURCE_ARTIFACT or
            metadata.get("parentZipSha256") != SOURCE_ZIP_SHA or
            metadata.get("sha256") != fileset_sha or
            metadata.get("verifiedLocations") != verified_locations or
            metadata.get("partitionCount") != partition_count):
        raise ValueError("Status checkpoint provenance or declared counts mismatch")
    if (collection.get("schema_version") != 1 or
            collection.get("status") != "partial_failure" or
            len(collection.get("sources", [])) != 1 or
            collection["sources"][0].get("source") != "FR:electroverse_status" or
            collection["sources"][0].get("status") != "failed" or
            collection["sources"][0].get("reason") != metadata.get("reason")):
        raise ValueError("Status checkpoint must remain unpromotable")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Missing or unsafe status checkpoint root")
    digest, files = artifact_digest(root)
    if digest != fileset_sha or files != metadata.get("files"):
        raise ValueError("Status checkpoint file inventory or SHA-256 mismatch")
    # Every national mapping, inventory, tariff shard and source report must
    # remain byte-identical to the separately verified COMPLETE tariff parent.
    # Only status partitions and their report may differ.
    for record in files:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe status checkpoint member")
        if relative.parts[:3] == ("data", "electroverse", "live_statuses"):
            continue
        if relative == STATUS_REPORT:
            continue
        original = parent / relative
        if (not original.is_file() or original.stat().st_size != record["bytes"]
                or sha256(original) != record["sha256"]):
            raise ValueError("Checkpoint unexpectedly modified its tariff parent: " + str(relative))
    partial = validate_partial(root)
    if (partial["fingerprint"] != cache_fingerprint(parent) or
            partial["fingerprint"] != metadata.get("sourceFingerprint") or
            partial["verified_locations"] != verified_locations or
            len(partial["partitions"]) != partition_count or
            sum(len(p["errors"]) for p in partial["partitions"]) != error_count):
        raise ValueError("Status partition coverage, failures or source fingerprint mismatch")
    if ((root / STATUS / "manifest.json").exists() or
            (root / STATUS / "evses.json.gz").exists()):
        raise ValueError("Partial status checkpoint cannot include national publication")
    report = read_json(root / STATUS_REPORT)
    recorded = collection["sources"][0].get("lastPartitionReport")
    if (report != recorded or
            report.get("sourceFingerprint") != partial["fingerprint"] or
            not report_matches_partition(partial, report)):
        raise ValueError("Status checkpoint report differs from retained partitions")
    deferred_file = root / STATUS / "deferred-failures.json"
    if deferred_file.is_file():
        deferred = read_json(deferred_file)
        actual = deferred_failure_summary(partial)
        if any(deferred.get(k) != actual[k] for k in
               ("sourceFingerprint", "verifiedLocations", "partitionCount",
                "remainingLocations", "errorCount", "partitionDetails")):
            raise ValueError("Deferred-error queue does not match source partitions")
    if metadata.get("reason") == "provider_rate_limited":
        limit = report.get("rateLimit") or {}
        if (limit.get("httpStatus") != 429 or not limit.get("resumeNotBeforeUtc")):
            raise ValueError("Rate-limited checkpoint lacks a verified cooldown")
    return root, partial, report


def resume_eligibility(partial: dict, report: dict, now: datetime) -> tuple[bool, str]:
    """Never silently discard good rows when the 16-hour freshness gate has expired."""
    for partition in partial["partitions"]:
        try:
            started = datetime.fromisoformat(partition["startedAt"].replace("Z", "+00:00"))
            age = (now - started).total_seconds()
        except (KeyError, TypeError, ValueError):
            return False, "invalid_partition_start"
        if not 0 <= age < FRESH_SECONDS - 600:
            return False, "checkpoint_stale_or_near_expiry"
    limit = report.get("rateLimit") or {}
    if limit.get("resumeNotBeforeUtc"):
        try:
            resume_at = datetime.fromisoformat(limit["resumeNotBeforeUtc"].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False, "invalid_rate_limit_cooldown"
        if now < resume_at:
            return False, "provider_cooldown_active"
    return True, "fresh_and_cooldown_satisfied"

def report_matches_partition(partial: dict, report: dict) -> bool:
    """Recovery may end at any partition; the latest report need not be partition 15."""
    selected = next((p for p in partial["partitions"]
                     if p["partition"] == report.get("partition")), None)
    return selected is not None and report.get("verifiedLocations") == len(selected["entries"])


def deferred_failure_summary(partial: dict) -> dict:
    """Audit-only queue: no invented statuses, no promotion of incomplete data."""
    details = []
    for part in sorted(partial["partitions"], key=lambda p: p["partition"]):
        errors = [{"pk": pk, "error": str(problem.get("error", "unknown"))}
                  for pk, problem in sorted(part["errors"].items())]
        missing = part["expectedLocations"] - len(part["entries"])
        if missing < len(errors):
            raise ValueError("More recorded failures than unresolved locations")
        details.append({
            "partition": part["partition"], "verified": len(part["entries"]),
            "remaining": missing, "errors": errors,
            "unvisited": missing - len(errors),
        })
    return {
        "schemaVersion": 1,
        "sourceFingerprint": partial["fingerprint"],
        "partitionCount": len(details),
        "verifiedLocations": partial["verified_locations"],
        "remainingLocations": sum(p["remaining"] for p in details),
        "errorCount": sum(len(p["errors"]) for p in details),
        "partitionDetails": details,
    }


def finish_checkpoint(work: Path, out: Path, reason: str, last_report: dict | None,
                      resume_from: dict | None = None) -> None:
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
        "resumedFrom": resume_from,
    }
    (out / "checkpoint-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (out / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "status": "partial_failure",
        "sources": [{"source": "FR:electroverse_status", "module": "electroverse_status",
                     "status": "failed", "reason": reason,
                     "verifiedLocations": state["verified_locations"],
                     "sourceFingerprint": state["fingerprint"],
                     "lastPartitionReport": last_report, "resumedFrom": resume_from}],
    }, indent=2) + "\n")
    print(json.dumps({"result": "checkpointed", "reason": reason,
                      "verifiedLocations": state["verified_locations"],
                      "partitions": len(state["partitions"])}))


def finish_complete(work: Path, out: Path, resume_from: dict | None = None) -> None:
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
        "resumedFrom": resume_from,
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
    ap.add_argument("--checkpoint", type=Path)
    ap.add_argument("--checkpoint-fileset", type=str)
    ap.add_argument("--checkpoint-run", type=int)
    ap.add_argument("--checkpoint-artifact", type=int)
    ap.add_argument("--checkpoint-verified", type=int)
    ap.add_argument("--checkpoint-errors", type=int)
    ap.add_argument("--checkpoint-partitions", type=int)
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
    required = (args.checkpoint, args.checkpoint_fileset, args.checkpoint_run,
                args.checkpoint_artifact, args.checkpoint_verified,
                args.checkpoint_errors, args.checkpoint_partitions)
    if any(item is None for item in required):
        raise ValueError("An exact previously audited status checkpoint is required")
    checkpoint_root, partial, report = checked_status_checkpoint(
        args.checkpoint.resolve(), parent, fileset_sha=args.checkpoint_fileset,
        verified_locations=args.checkpoint_verified, error_count=args.checkpoint_errors,
        partition_count=args.checkpoint_partitions,
    )
    eligible, eligibility_reason = resume_eligibility(partial, report, datetime.now(timezone.utc))
    print(json.dumps({"event": "verified_status_checkpoint",
                      "run": args.checkpoint_run, "artifact": args.checkpoint_artifact,
                      "verifiedLocations": partial["verified_locations"],
                      "errors": sum(len(p["errors"]) for p in partial["partitions"]),
                      "sourceFingerprint": partial["fingerprint"],
                      "resumeEligible": eligible, "eligibilityReason": eligibility_reason}))
    if args.mode == "verify":
        print(json.dumps({"result": "verified_only", "supplierCalls": 0,
                          "checkpointValidated": True, "resumeEligible": eligible}))
        return
    if not eligible:
        raise ValueError("Refusing supplier requests and unsafe replay: " + eligibility_reason)
    if not os.environ.get("ELECTROVERSE_API_KEY"):
        raise ValueError("Missing status API credential; cannot collect")
    out.mkdir(parents=True, exist_ok=False)
    work = out / "work"
    shutil.copytree(checkpoint_root, work)
    resumed = validate_partial(work)
    if resumed["verified_locations"] != partial["verified_locations"]:
        raise ValueError("Validated checkpoint was not preserved during isolated staging")
    # Keep per-station 429 counters within this run's sweep/recovery only.
    # A new authorized GitHub run obtains a new allowance for every PK.
    # This edits the isolated working copy, never the immutable source artifact.
    cleared = 0
    for index in range(PARTITION_COUNT):
        path = part_path(work, index)
        if path.is_file():
            old_part = read_json(path)
            if "station429WaitSeconds" in old_part:
                old_part.pop("station429WaitSeconds")
                path.write_text(json.dumps(old_part, indent=2) + "\n")
                cleared += 1
    print(json.dumps({"event": "new_run_station_budgets_reset",
                      "partitionsReset": cleared}))
    resume_from = {"run": args.checkpoint_run, "artifact": args.checkpoint_artifact,
                   "filesetSha256": args.checkpoint_fileset,
                   "verifiedLocations": partial["verified_locations"]}
    started = time.monotonic()
    reason = "all_partitions_complete"
    last_report = None
    attempted = []

    def budget_available() -> bool:
        # Leave up to 70 min for a partition subprocess and uploading evidence.
        return time.monotonic() - started <= args.budget_seconds - 4200

    def attempt_partition(i: int, phase: str) -> bool:
        nonlocal last_report
        existing_path = part_path(work, i)
        existing = read_json(existing_path) if existing_path.is_file() else None
        if existing and not resume_eligibility(
                {"partitions": [existing]}, {}, datetime.now(timezone.utc))[0]:
            raise ValueError("Existing status partition became stale: refusing silent replay")
        before = dict(existing["entries"]) if existing else {}
        # Each charging-location PK has its own 480s 429 budget.
        # No carryover of waits from other PKs, partitions or subprocesses.
        os.environ.pop("ELECTROVERSE_STATUS_429_BUDGET_SECONDS", None)
        os.environ["ELECTROVERSE_STATUS_429_MAX_SECONDS_PER_STATION"] = "480"
        os.environ["ELECTROVERSE_STATUS_DEFER_FAILED"] = "1" if phase == "sweep" else "0"
        os.environ["ELECTROVERSE_STATUS_RECOVERY_ONLY"] = "1" if phase == "recovery" else "0"
        try:
            run(work, source=parent, partition=i)
        except IncompleteStatus:
            pass
        last_report = read_json(work / STATUS_REPORT)
        recovery = last_report.get("rateLimitRecovery")
        if not isinstance(recovery, dict) or recovery.get("budgetScope") != "station_pk":
            raise ValueError("Status 429 recovery must report a per-station budget")
        if recovery.get("maxSecondsPerStation") != 480:
            raise ValueError("Unexpected per-station 429 wait allowance")
        used_wait = recovery.get("totalWaitSeconds")
        max_station = recovery.get("maxStationWaitSeconds")
        if (isinstance(used_wait, bool) or not isinstance(used_wait, (int, float))
                or not 0 <= used_wait
                or isinstance(max_station, bool) or not isinstance(max_station, (int, float))
                or not 0 <= max_station <= 480):
            raise ValueError("Status 429 per-station report is missing or invalid")
        print(json.dumps({"event": "status_429_station_metrics", "partition": i,
                          "phase": phase, "totalWaitSeconds": used_wait,
                          "maxStationWaitSeconds": max_station,
                          "budgetScope": "station_pk"}))
        part = validate_part(work, i)
        if any(part["entries"].get(pk) != statuses for pk, statuses in before.items()):
            raise ValueError("A previously verified status row was replayed or replaced")
        if (last_report.get("partition") != i
                or last_report.get("sourceFingerprint") != cache_fingerprint(work)
                or last_report.get("verifiedLocations") != len(part["entries"])):
            raise ValueError("Status report is not from the selected partition")
        remaining = part["expectedLocations"] - len(part["entries"])
        attempted.append((phase, i))
        print(json.dumps({"event": "partition_result", "phase": phase,
                          "partition": i, "expected": part["expectedLocations"],
                          "verified": len(part["entries"]), "remaining": remaining,
                          "errors": len(part["errors"]),
                          "rateLimit": last_report.get("rateLimit")}))
        return not bool(last_report.get("rateLimit"))

    # Sweep every national partition first. Individual errors do not stop the loop.
    for i in range(PARTITION_COUNT):
        if not budget_available():
            reason = "runner_budget_reserve"
            break
        if not attempt_partition(i, "sweep"):
            reason = "provider_rate_limited"
            break

    # Only after all 16 partitions have been visited, revisit outstanding
    # individuals and any unvisited PK from a previous partition's failure budget.
    if reason == "all_partitions_complete":
        initial = validate_partial(work)
        if len(initial["partitions"]) != PARTITION_COUNT:
            raise ValueError("Sweep did not retain all sixteen status partitions")
        pending = [p["partition"] for p in initial["partitions"]
                   if len(p["entries"]) < p["expectedLocations"]]
        print(json.dumps({"event": "deferred_recovery_plan",
                          "partitions": pending, "count": len(pending),
                          "errors": sum(len(p["errors"]) for p in initial["partitions"])}))
        for i in pending:
            if not budget_available():
                reason = "runner_budget_reserve"
                break
            if not attempt_partition(i, "recovery"):
                reason = "provider_rate_limited"
                break

    final_partial = validate_partial(work)
    summary = deferred_failure_summary(final_partial)
    queue_file = work / STATUS / "deferred-failures.json"
    if summary["remainingLocations"]:
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text(json.dumps(summary, indent=2) + "\n")
    else:
        queue_file.unlink(missing_ok=True)
    print(json.dumps({"event": "deferred_queue_final",
                      "partitionsVisited": len(final_partial["partitions"]),
                      "attempts": len(attempted),
                      "verifiedLocations": summary["verifiedLocations"],
                      "remainingLocations": summary["remainingLocations"],
                      "errorCount": summary["errorCount"]}))
    if reason == "all_partitions_complete" and summary["remainingLocations"]:
        reason = "deferred_errors_remaining"
    if reason == "all_partitions_complete":
        try:
            finish_complete(work, out, resume_from)
            state = "complete"
        except (IncompleteStatus, FileNotFoundError):
            reason = "national_finalize_incomplete"
            finish_checkpoint(work, out, reason, last_report, resume_from)
            state = "checkpointed"
    else:
        finish_checkpoint(work, out, reason, last_report, resume_from)
        state = "checkpointed"
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fp:
            fp.write("collection_state=" + state + "\n")
            fp.write("stop_reason=" + reason + "\n")


if __name__ == "__main__":
    main()
