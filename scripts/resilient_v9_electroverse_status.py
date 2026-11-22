#!/usr/bin/env python3
"""Durable, bounded Electroverse status steps for GitHub Actions.

A separate upload-artifact step follows EVERY successful unit. Losing the
runner mid-unit can lose only that unit; previous immutable units remain
available from the same GitHub run.

Never publish an incomplete status ledger or alter the pinned tariff parent.
"""
from __future__ import annotations

import argparse
import hashlib
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
from v9_rebuild.orchestrator import artifact_digest, sha256
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


def delta_paths(staging: Path) -> list[Path]:
    """Only mutable live status data and the last report; never tariff shards."""
    full = read_json(staging / "checkpoint-manifest.json")
    paths = []
    for record in full["files"]:
        relative = Path(record["path"])
        if (relative.parts[:3] == ("data", "electroverse", "live_statuses")
                or relative.as_posix() == STATUS_REPORT.as_posix()):
            paths.append(relative)
    if STATUS_REPORT not in paths or not any(p.name.startswith("part-") for p in paths):
        raise ValueError("Status delta needs at least one partition and its last report")
    return paths


def delta_digest(records: list[dict]) -> str:
    h = hashlib.sha256()
    for row in sorted(records, key=lambda x: x["path"]):
        h.update(row["path"].encode("utf-8") + b"\0" +
                 row["sha256"].encode("ascii") + b"\n")
    return h.hexdigest()


def export_delta(staging: Path, destination: Path) -> None:
    """Small, independently validated artifact; full status state can be rehydrated."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    source_files = [Path("manifest.json"), Path("checkpoint-manifest.json"),
                    *delta_paths(staging)]
    records = []
    for relative in sorted(source_files):
        src = staging / relative
        if src.is_symlink() or not src.is_file():
            raise ValueError("Unsafe status checkpoint delta member")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        records.append({"path": relative.as_posix(),
                        "sha256": sha256(target), "bytes": target.stat().st_size})
    full = read_json(staging / "checkpoint-manifest.json")
    manifest = {
        "schemaVersion": 1,
        "kind": "tcc-v9-electroverse-status-delta",
        "source": "FR:electroverse_status",
        "branch": BRANCH,
        "sourceFingerprint": full["sourceFingerprint"],
        "completeSnapshotValidated": False,
        "fullFilesetSha256": full["sha256"],
        "sha256": delta_digest(records),
        "files": records,
    }
    write_json(destination / "delta-manifest.json", manifest)
    print(json.dumps({"event": "segmented_delta_ready",
                      "files": len(records), "sha256": manifest["sha256"],
                      "fullFilesetSha256": full["sha256"]}))


def restore_delta(tariff_parent: Path, delta: Path, dest: Path) -> dict:
    """Reconstitute canonical, SHA-checked full checkpoint from small artifact.

    This is deliberately usable by a later GitHub run after runner disappearance.
    """
    if dest.exists() or not delta.is_dir() or not tariff_parent.is_dir():
        raise ValueError("Fresh destination and trusted input directories required")
    meta = read_json(delta / "delta-manifest.json")
    if (meta.get("schemaVersion") != 1
            or meta.get("kind") != "tcc-v9-electroverse-status-delta"
            or meta.get("source") != "FR:electroverse_status"
            or meta.get("branch") != BRANCH
            or meta.get("completeSnapshotValidated") is not False):
        raise ValueError("Untrusted Electroverse segment delta")
    files = meta.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Missing segment file inventory")
    seen = set()
    for record in files:
        relative = Path(record.get("path", ""))
        valid = (relative in (Path("manifest.json"), Path("checkpoint-manifest.json"),
                              STATUS_REPORT)
                 or relative.parts[:3] == ("data", "electroverse", "live_statuses"))
        if (not valid or not relative.parts or relative.is_absolute()
                or ".." in relative.parts or relative.as_posix() in seen):
            raise ValueError("Invalid or duplicate status delta path")
        seen.add(relative.as_posix())
        path = delta / relative
        if (not path.resolve().is_relative_to(delta.resolve())
                or any((delta / Path(*relative.parts[:i])).is_symlink()
                       for i in range(1, len(relative.parts) + 1))
                or not path.is_file()
                or path.stat().st_size != record.get("bytes")
                or sha256(path) != record.get("sha256")):
            raise ValueError("Status delta member SHA-256 mismatch")
    if any(p.is_symlink() for p in delta.rglob("*")):
        raise ValueError("Status delta cannot include symlinks")
    found = {p.relative_to(delta).as_posix() for p in delta.rglob("*") if p.is_file()}
    if found != seen | {"delta-manifest.json"} or delta_digest(files) != meta.get("sha256"):
        raise ValueError("Status delta inventory or digest mismatch")
    source = read_json(delta / "checkpoint-manifest.json")
    if (source.get("sha256") != meta.get("fullFilesetSha256")
            or source.get("sourceFingerprint") != meta.get("sourceFingerprint")):
        raise ValueError("Delta full-checkpoint provenance does not match")
    dest.mkdir(parents=True)
    work = dest / "checkpoints/FR_electroverse_status"
    shutil.copytree(tariff_parent, work)
    for row in files:
        rel = Path(row["path"])
        if rel in (Path("manifest.json"), Path("checkpoint-manifest.json")):
            continue
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(delta / rel, target)
    digest, inventory = artifact_digest(work)
    if digest != source["sha256"] or inventory != source["files"]:
        raise ValueError("Status delta could not reconstruct canonical full fileset")
    for name in ("manifest.json", "checkpoint-manifest.json"):
        shutil.copy2(delta / name, dest / name)
    _root, partial, report = checked_status_checkpoint(
        dest, tariff_parent,
        fileset_sha=source["sha256"],
        verified_locations=source["verifiedLocations"],
        error_count=sum(len(p["errors"]) for p in validate_partial(work)["partitions"]),
        partition_count=source["partitionCount"],
    )
    if meta["sourceFingerprint"] != partial["fingerprint"]:
        raise ValueError("Restored status fingerprint mismatch")
    print(json.dumps({"event": "restored_verified_status_delta",
                      "verifiedLocations": partial["verified_locations"],
                      "partitions": len(partial["partitions"]),
                      "fullFilesetSha256": digest,
                      "rateLimited": bool(report.get("rateLimit"))}))
    return source


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
    export_delta(staging, out / "stage-delta")
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
    parser.add_argument("command", choices=("prepare", "segment", "finish", "rehydrate"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--delta", type=Path)
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
    elif args.command == "rehydrate":
        if args.bundle is None or args.delta is None:
            raise ValueError("Rehydration requires canonical tariff parent and pinned delta")
        parent = checked_source(args.bundle.resolve())
        restore_delta(parent, args.delta.resolve(), args.out.resolve())
    else:
        finish(args)


if __name__ == "__main__":
    main()
