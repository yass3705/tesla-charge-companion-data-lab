#!/usr/bin/env python3
"""Durable, bounded Electroverse status steps for GitHub Actions.

A separate upload-artifact step follows EVERY successful unit. Losing the
runner mid-unit can lose only that unit; previous immutable units remain
available from the same GitHub run.

Never publish an incomplete status ledger or alter the pinned tariff parent.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.pilot_v9_electroverse_status import (
    BRANCH, checked_source, checked_status_checkpoint, deferred_failure_summary,
    finish_checkpoint, finish_complete, resume_eligibility,
)
from v9_rebuild.electroverse import read_json
from v9_rebuild.electroverse_status import (
    PARTITION_COUNT, STATUS, STATUS_REPORT, IncompleteStatus, cache_fingerprint,
    is_fresh_complete, part_path, run, validate_complete, validate_part,
    validate_partial,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def send_output(**values: object) -> None:
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination:
        with open(destination, "a", encoding="utf-8") as file:
            for key, val in values.items():
                if not isinstance(val, (bool, int, str)):
                    raise ValueError("Invalid workflow output type")
                file.write(f"{key}={str(val).lower() if isinstance(val, bool) else val}\n")


def progress_path(out: Path) -> Path:
    return out / "progress.json"


def read_progress(out: Path) -> dict:
    state = read_json(progress_path(out))
    if state.get("schemaVersion") != 1 or state.get("phase") not in ("sweep", "recovery", "finished"):
        raise ValueError("Missing or untrusted segmented status progress")
    if state.get("sourceFingerprint") != cache_fingerprint(out / "work"):
        raise ValueError("Segmented status source fingerprint mismatch")
    for key in ("sweepNext", "recoveryNext"):
        if type(state.get(key)) is not int or not 0 <= state[key] <= PARTITION_COUNT:
            raise ValueError("Invalid segmented status cursor")
    return state


def require_runner() -> None:
    if os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise ValueError("Electroverse status steps require the reconstruction branch")


def prepare(args: argparse.Namespace) -> None:
    require_runner()
    out = args.out.resolve()
    root = Path(__file__).resolve().parents[1]
    if out.exists() or out == root or root in out.parents:
        raise ValueError("Fresh, isolated segmented status output required")
    parent = checked_source(args.bundle.resolve())
    checkpoint, partial, last_report = checked_status_checkpoint(
        args.checkpoint.resolve(), parent,
        fileset_sha=args.checkpoint_fileset,
        verified_locations=args.checkpoint_verified,
        error_count=args.checkpoint_errors,
        partition_count=args.checkpoint_partitions,
    )
    eligible, why = resume_eligibility(partial, last_report, datetime.now(timezone.utc))
    print(json.dumps({"event": "segmented_preflight",
                      "verifiedLocations": partial["verified_locations"],
                      "partitions": len(partial["partitions"]),
                      "resumeEligible": eligible, "reason": why}))
    if not eligible:
        raise ValueError("Refusing unsafe/stale status resumption: " + why)
    if not os.environ.get("ELECTROVERSE_API_KEY"):
        raise ValueError("Electroverse credential missing")
    out.mkdir(parents=True)
    work = out / "work"
    shutil.copytree(checkpoint, work)
    if validate_partial(work)["verified_locations"] != partial["verified_locations"]:
        raise ValueError("Verified source successes were not preserved")
    # Per-station wait counters belong to this run only, never the parent run.
    cleared = 0
    for i in range(PARTITION_COUNT):
        path = part_path(work, i)
        if path.exists():
            part = read_json(path)
            if "station429WaitSeconds" in part:
                del part["station429WaitSeconds"]
                write_json(path, part)
                cleared += 1
    state = {
        "schemaVersion": 1,
        "phase": "sweep", "sweepNext": 0, "recoveryNext": 0,
        "halted": False, "stopReason": None,
        "sourceFingerprint": partial["fingerprint"],
        "resumedFrom": {
            "run": args.checkpoint_run,
            "artifact": args.checkpoint_artifact,
            "filesetSha256": args.checkpoint_fileset,
            "verifiedLocations": partial["verified_locations"],
        },
        "lastReport": last_report,
        "preparedUtc": datetime.now(timezone.utc).isoformat(),
        "sweepElapsedSeconds": 0,
        "lastSegment": None,
    }
    write_json(progress_path(out), state)
    print(json.dumps({"event": "segmented_prepared", "sourceVerified": True,
                      "previouslyVerified": partial["verified_locations"],
                      "stationWaitBudgetsReset": cleared, "supplierCalls": 0}))


def require_fresh(work: Path) -> None:
    partial = validate_partial(work)
    eligible, reason = resume_eligibility(partial, {}, datetime.now(timezone.utc))
    if not eligible:
        raise IncompleteStatus("checkpoint_stale_or_near_expiry:" + reason)


def make_checkpoint(out: Path, state: dict) -> None:
    """Build a separately validated, immutable snapshot without moving live work."""
    work = out / "work"
    partial = validate_partial(work)
    queue = deferred_failure_summary(partial)
    queue_file = work / STATUS / "deferred-failures.json"
    if queue["remainingLocations"]:
        write_json(queue_file, queue)
    else:
        queue_file.unlink(missing_ok=True)
    staging = out / "staged"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    snapshot = out / "staged_work_copy"
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(work, snapshot)
    # A partial checkpoint must NEVER contain an old or new national ledger.
    for fname in ("manifest.json", "evses.json.gz"):
        (snapshot / STATUS / fname).unlink(missing_ok=True)
    report = state.get("lastReport")
    if not isinstance(report, dict):
        raise ValueError("No trustworthy partition report for intermediate checkpoint")
    reason = state["stopReason"] or (
        "awaiting_deferred_recovery" if state["phase"] == "recovery"
        else "partition_stage_checkpoint"
    )
    finish_checkpoint(snapshot, staging, reason, report, state["resumedFrom"])
    # Revalidate exactly as the next authorized run would.
    metadata = read_json(staging / "checkpoint-manifest.json")
    checked_status_checkpoint(
        staging, work,
        fileset_sha=metadata["sha256"],
        verified_locations=queue["verifiedLocations"],
        error_count=queue["errorCount"],
        partition_count=queue["partitionCount"],
    )
    print(json.dumps({"event": "segmented_checkpoint_validated",
                      "segment": state["lastSegment"],
                      "verifiedLocations": queue["verifiedLocations"],
                      "errorCount": queue["errorCount"],
                      "partitions": queue["partitionCount"],
                      "filesetSha256": metadata["sha256"],
                      "reason": reason}))


def collect_segment(args: argparse.Namespace) -> None:
    require_runner()
    out = args.out.resolve()
    state = read_progress(out)
    if state["halted"]:
        raise ValueError("A halted run must not start additional supplier requests")
    phase, index = args.phase, args.partition
    if not 0 <= index < PARTITION_COUNT:
        raise ValueError("Partition index outside 00–15")
    if state["phase"] != phase:
        raise ValueError("Segment phase/cursor mismatch")
    cursor_name = "sweepNext" if phase == "sweep" else "recoveryNext"
    if state[cursor_name] != index:
        raise ValueError("Nonsequential segment index")
    if phase == "recovery" and state["sweepNext"] != PARTITION_COUNT:
        raise ValueError("Cannot start deferred recovery before visiting all 16 partitions")
    if not os.environ.get("ELECTROVERSE_API_KEY"):
        raise ValueError("Missing status API credential")
    work = out / "work"
    try:
        require_fresh(work)
    except IncompleteStatus:
        state["halted"] = True
        state["stopReason"] = "checkpoint_stale_or_near_expiry"
        state["lastSegment"] = {"phase": phase, "partition": index, "supplierCalls": 0}
        write_json(progress_path(out), state)
        make_checkpoint(out, state)
        send_output(checkpoint_ready=True, continue_collecting=False)
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as handle:
            handle.write("STATUS_HALT=true\n")
        return
    previous = read_json(part_path(work, index)) if part_path(work, index).exists() else None
    before = dict(previous["entries"]) if previous else {}
    pending = previous is None or len(previous["entries"]) < previous["expectedLocations"]
    if phase == "recovery" and not pending:
        state["recoveryNext"] = index + 1
        if index == PARTITION_COUNT - 1:
            state["phase"] = "finished"
        write_json(progress_path(out), state)
        send_output(checkpoint_ready=False, continue_collecting=True)
        print(json.dumps({"event": "recovery_skipped_complete", "partition": index}))
        return
    os.environ.pop("ELECTROVERSE_STATUS_429_BUDGET_SECONDS", None)
    os.environ["ELECTROVERSE_STATUS_429_MAX_SECONDS_PER_STATION"] = "480"
    os.environ["ELECTROVERSE_STATUS_DEFER_FAILED"] = "1" if phase == "sweep" else "0"
    os.environ["ELECTROVERSE_STATUS_RECOVERY_ONLY"] = "1" if phase == "recovery" else "0"
    elapsed = time.monotonic()
    try:
        # Each historical collector subprocess is at most one partition (<=60 min).
        run(work, partition=index)
    except IncompleteStatus:
        pass
    report = read_json(work / STATUS_REPORT)
    validation = validate_part(work, index)
    if any(validation["entries"].get(pk) != values for pk, values in before.items()):
        raise ValueError("Previously verified status was lost or replayed")
    if (report.get("partition") != index
            or report.get("verifiedLocations") != len(validation["entries"])
            or report.get("sourceFingerprint") != state["sourceFingerprint"]):
        raise ValueError("Segment report does not match the selected partition")
    recovery = report.get("rateLimitRecovery")
    if (not isinstance(recovery, dict)
            or recovery.get("budgetScope") != "station_pk"
            or recovery.get("maxSecondsPerStation") != 480
            or not isinstance(recovery.get("totalWaitSeconds"), (int, float))
            or not 0 <= recovery.get("maxStationWaitSeconds", -1) <= 480):
        raise ValueError("Unexpected or missing per-station 429 recovery audit")
    state[cursor_name] = index + 1
    if index == PARTITION_COUNT - 1:
        state["phase"] = "recovery" if phase == "sweep" else "finished"
    state["halted"] = bool(report.get("rateLimit"))
    state["stopReason"] = "provider_rate_limited" if state["halted"] else None
    state["lastReport"] = report
    state["lastSegment"] = {
        "phase": phase, "partition": index,
        "verified": len(validation["entries"]),
        "remaining": validation["expectedLocations"] - len(validation["entries"]),
        "errors": len(validation["errors"]),
        "elapsedSeconds": round(time.monotonic() - elapsed, 2),
        "429WaitSeconds": recovery["totalWaitSeconds"],
        "maxStationWaitSeconds": recovery["maxStationWaitSeconds"],
    }
    write_json(progress_path(out), state)
    make_checkpoint(out, state)
    send_output(checkpoint_ready=True, continue_collecting=not state["halted"])
    if state["halted"] and os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as handle:
            handle.write("STATUS_HALT=true\n")
    print(json.dumps({"event": "segmented_result",
                      **state["lastSegment"], "halted": state["halted"],
                      "stopReason": state["stopReason"]}))


def finish(args: argparse.Namespace) -> None:
    require_runner()
    out = args.out.resolve()
    state = read_progress(out)
    if state["halted"] or state["phase"] != "finished":
        print(json.dumps({"result": "checkpointed",
                          "reason": state["stopReason"] or "segmented_cycle_incomplete",
                          "noNationalPublication": True}))
        send_output(collection_state="checkpointed")
        return
    work = out / "work"
    try:
        validate_complete(work)
    except (IncompleteStatus, FileNotFoundError, ValueError) as error:
        print(json.dumps({"result": "checkpointed",
                          "reason": "deferred_errors_or_missing_parts",
                          "detail": str(error), "noNationalPublication": True}))
        send_output(collection_state="checkpointed")
        return
    complete_path = out / "complete"
    if complete_path.exists():
        raise ValueError("Complete destination already exists")
    complete_path.mkdir()
    copy = out / "final_copy"
    shutil.copytree(work, copy)
    finish_complete(copy, complete_path, state["resumedFrom"])
    print(json.dumps({"result": "complete", "nationalPublication": False}))
    send_output(collection_state="complete")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "segment", "finish"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--checkpoint-fileset")
    parser.add_argument("--checkpoint-run", type=int)
    parser.add_argument("--checkpoint-artifact", type=int)
    parser.add_argument("--checkpoint-verified", type=int)
    parser.add_argument("--checkpoint-errors", type=int)
    parser.add_argument("--checkpoint-partitions", type=int)
    parser.add_argument("--phase", choices=("sweep", "recovery"))
    parser.add_argument("--partition", type=int)
    args = parser.parse_args()
    if args.command == "prepare":
        if any(x is None for x in (args.bundle, args.checkpoint, args.checkpoint_fileset,
                                   args.checkpoint_run, args.checkpoint_artifact,
                                   args.checkpoint_verified, args.checkpoint_errors,
                                   args.checkpoint_partitions)):
            raise ValueError("Missing immutable parent checkpoint pins")
        prepare(args)
    elif args.command == "segment":
        if args.phase is None or args.partition is None:
            raise ValueError("Segment phase and partition are required")
        collect_segment(args)
    else:
        finish(args)


if __name__ == "__main__":
    main()
