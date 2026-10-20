#!/usr/bin/env python3
"""Run the preserved 16-part Electroverse status census outside the checkout."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from v9_rebuild.electroverse import CACHE, ROOT, read_json, stage_state, validate_state


STATUS = Path("data/electroverse/live_statuses")
PARTS = STATUS / "parts"
STATUS_REPORT = Path("reports/electroverse/status-partition-latest.json")
FINAL_REPORT = Path("reports/electroverse/status-national-finalization.json")
PARTITION_COUNT = 16
FRESH_SECONDS = 16 * 3600


class IncompleteStatus(RuntimeError):
    """A valid partial checkpoint remains available for a later partition run."""


def cache_fingerprint(root: Path) -> str:
    manifest = read_json(root / CACHE / "manifest.json")
    compact = {"date": manifest.get("generatedAt"),
               "shards": [[row.get("file"), row.get("count"), row.get("sizeBytes")] for row in manifest.get("shards", [])]}
    encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def part_path(root: Path, index: int) -> Path:
    if not 0 <= index < PARTITION_COUNT:
        raise ValueError("Status partition must be 0..15")
    return root / PARTS / f"part-{index:02d}.json"


def validate_part(root: Path, index: int, *, fingerprint: str | None = None) -> dict:
    part = read_json(part_path(root, index))
    if (part.get("schemaVersion") != 1 or part.get("partition") != index
            or part.get("partitionCount") != PARTITION_COUNT
            or part.get("sourceFingerprint") != (fingerprint or cache_fingerprint(root))
            or not isinstance(part.get("expectedLocations"), int)
            or part["expectedLocations"] < 0
            or not isinstance(part.get("entries"), dict)
            or not isinstance(part.get("errors"), dict)
            or len(part["entries"]) > part["expectedLocations"]):
        raise ValueError(f"Invalid Electroverse status partition {index}")
    if set(part["entries"]) & set(part["errors"]):
        raise ValueError(f"Successful and failed location both present in partition {index}")
    for location, statuses in part["entries"].items():
        if not location or not isinstance(statuses, dict) or any(not pk or not isinstance(value, str) for pk, value in statuses.items()):
            raise ValueError(f"Invalid EVSE status row in partition {index}")
    return part


def validate_partial(root: Path) -> dict:
    validate_state(root, require_complete=False)
    fingerprint = cache_fingerprint(root)
    seen: set[str] = set()
    parts = []
    for index in range(PARTITION_COUNT):
        path = part_path(root, index)
        if not path.is_file():
            continue
        part = validate_part(root, index, fingerprint=fingerprint)
        for location in part["entries"]:
            if location in seen:
                raise ValueError(f"Location duplicated across status partitions: {location}")
            seen.add(location)
        parts.append(part)
    return {"fingerprint": fingerprint, "partitions": parts, "verified_locations": len(seen)}


def is_fresh_complete(part: dict, now: datetime) -> bool:
    try:
        started = datetime.fromisoformat(part["startedAt"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False
    age = (now - started).total_seconds()
    return 0 <= age < FRESH_SECONDS and len(part["entries"]) == part["expectedLocations"] and not part["errors"]


def choose_partition(root: Path, now: datetime | None = None) -> int | None:
    now = now or datetime.now(timezone.utc)
    fingerprint = cache_fingerprint(root)
    for index in range(PARTITION_COUNT):
        path = part_path(root, index)
        if not path.is_file():
            return index
        part = validate_part(root, index, fingerprint=fingerprint)
        if not is_fresh_complete(part, now):
            return index
    return None


def invoke(script: str, args: list[str], out: Path, env: dict[str, str], runner=subprocess.run) -> int:
    result = runner(["node", str(ROOT / "scripts" / script), *args], cwd=out, env=env,
                    capture_output=True, text=True, timeout=3600, check=False)
    return result.returncode


def merge_partitions(out: Path, incoming: Path, env: dict[str, str], runner=subprocess.run) -> None:
    for index in range(PARTITION_COUNT):
        candidate = part_path(incoming, index)
        if not candidate.is_file():
            continue
        destination = part_path(out, index)
        if invoke("electroverse_merge_status_partitions.mjs", [str(candidate), str(destination)], out, env, runner):
            raise ValueError(f"Cannot merge status partition {index}")


def stage(source: Path, out: Path, *, incoming: Path | None = None, runner=subprocess.run) -> None:
    stage_state(source, out)
    source_status = source / STATUS
    if source_status.is_dir():
        shutil.copytree(source_status, out / STATUS, dirs_exist_ok=True)
    (out / PARTS).mkdir(parents=True, exist_ok=True)
    current_fingerprint = cache_fingerprint(out)
    for index in range(PARTITION_COUNT):
        path = part_path(out, index)
        if not path.is_file():
            continue
        prior_fingerprint = read_json(path).get("sourceFingerprint")
        if prior_fingerprint != current_fingerprint:
            archive = out / STATUS / "stale_parts" / str(prior_fingerprint or "unknown") / path.name
            archive.parent.mkdir(parents=True, exist_ok=True)
            path.rename(archive)
    if incoming is not None:
        merge_partitions(out, incoming, os.environ.copy(), runner)
    # A prior national ledger never proves the new cycle complete.
    for name in ("manifest.json", "evses.json.gz"):
        (out / STATUS / name).unlink(missing_ok=True)
    validate_partial(out)


def validate_complete(out: Path, *, require_fresh_parts: bool = True) -> dict:
    partial = validate_partial(out)
    if len(partial["partitions"]) != PARTITION_COUNT:
        raise IncompleteStatus("Missing status partitions")
    now = datetime.now(timezone.utc)
    if require_fresh_parts and any(not is_fresh_complete(part, now) for part in partial["partitions"]):
        raise IncompleteStatus("Status partitions are incomplete or stale")
    manifest = read_json(out / STATUS / "manifest.json")
    if (manifest.get("sourceFingerprint") != partial["fingerprint"]
            or manifest.get("partitionCount") != PARTITION_COUNT
            or manifest.get("completeness", {}).get("locations") is not True
            or manifest.get("completeness", {}).get("allPartitionsFresh") is not True
            or manifest.get("issueCount") != 0
            or manifest.get("failedLocations") != 0
            or manifest.get("completedLocations") != manifest.get("expectedLocations")
            or manifest.get("ledger") != "evses.json.gz"):
        raise ValueError("National status manifest is incomplete")
    with gzip.open(out / STATUS / manifest["ledger"], "rt", encoding="utf-8") as handle:
        ledger = json.load(handle)
    locations = ledger.get("locations") if isinstance(ledger, dict) else None
    if not isinstance(locations, dict) or set(locations) != {key for part in partial["partitions"] for key in part["entries"]}:
        raise ValueError("Status ledger differs from partition entries")
    source_evse_pks: dict[str, str] = {}
    for location, statuses in locations.items():
        if not isinstance(statuses, dict):
            raise ValueError("Invalid status ledger row")
        for pk, status in statuses.items():
            if pk in source_evse_pks and source_evse_pks[pk] != location:
                raise ValueError(f"Duplicate source EVSE PK across locations: {pk}")
            source_evse_pks[pk] = location
            if status != next(part["entries"][location][pk] for part in partial["partitions"] if location in part["entries"]):
                raise ValueError("Status ledger value differs from partition")
    return manifest


def run(out: Path, *, source: Path = ROOT, incoming: Path | None = None, partition: int | None = None,
        runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Status output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    if not (out / CACHE / "manifest.json").is_file():
        stage(source, out, incoming=incoming, runner=runner)
    elif incoming is not None:
        merge_partitions(out, incoming, os.environ.copy(), runner)
    validate_partial(out)
    selected = partition if partition is not None else choose_partition(out)
    env = os.environ.copy()
    if not env.get("ELECTROVERSE_API_KEY"):
        raise ValueError("ELECTROVERSE_API_KEY is required")
    env.setdefault("ELECTROVERSE_STATUS_REQUEST_DELAY_MS", "800")
    env.setdefault("ELECTROVERSE_STATUS_FAILURE_BUDGET", "48")
    env.setdefault("ELECTROVERSE_STATUS_RUN_LIMIT", "1500")
    if selected is not None:
        if not 0 <= selected < PARTITION_COUNT:
            raise ValueError("Status partition must be 0..15")
        code = invoke("electroverse_status_incremental.mjs", ["collect", str(selected)], out, env, runner)
        validate_part(out, selected)
        report = read_json(out / STATUS_REPORT)
        if report.get("partition") != selected or report.get("sourceFingerprint") != cache_fingerprint(out):
            raise ValueError("Status partition report mismatch")
        if code or report.get("complete") is not True:
            raise IncompleteStatus(f"Status partition {selected} has a resumable checkpoint")
    validate_partial(out)
    if choose_partition(out) is not None:
        raise IncompleteStatus("Other status partitions remain")
    # Remove any old national file before the historical finalizer decides.
    for name in ("manifest.json", "evses.json.gz"):
        (out / STATUS / name).unlink(missing_ok=True)
    if invoke("electroverse_status_incremental.mjs", ["finalize"], out, env, runner):
        raise IncompleteStatus("Status finalization failed")
    if not (out / STATUS / "manifest.json").is_file():
        raise IncompleteStatus("National status ledger is not complete")
    if invoke("electroverse_status_incremental.mjs", ["validate"], out, env, runner):
        raise ValueError("Historical status validator failed")
    validate_complete(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--incoming", type=Path)
    parser.add_argument("--partition", type=int)
    args = parser.parse_args()
    run(args.out, source=args.source, incoming=args.incoming, partition=args.partition)


if __name__ == "__main__":
    main()
