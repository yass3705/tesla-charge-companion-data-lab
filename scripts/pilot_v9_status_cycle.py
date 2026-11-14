#!/usr/bin/env python3
"""Bounded sequential national status cycle using a pinned tariff artifact.

The caller verifies the GitHub run and supplies its independently verified file
set SHA. Every partition retains its own checkpoint; no incomplete national
snapshot can be returned as complete. No provider retry follows a failed part.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v9_rebuild.electroverse_status import STATUS_REPORT, validate_partial, is_fresh_complete
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_batch, validated_dependency

SOURCE = "FR:electroverse_status"
BRANCH = "rebuild/v9-20261020"


def record_checkpoint(out, reports):
    state = out / "checkpoints/FR_electroverse_status"
    validate_partial(state)
    digest, files = artifact_digest(state)
    manifest = {"schemaVersion": 1, "state": "partial_checkpoint", "source": SOURCE,
                "branch": BRANCH, "headSha": os.environ["GITHUB_SHA"],
                "runId": int(os.environ["GITHUB_RUN_ID"]), "sha256": digest, "files": files,
                "completeSnapshotValidated": False, "reports": reports}
    (out / "checkpoint-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def advance(out, *, specs, max_partitions=16, budget_seconds=5*3600, execute=run_batch, clock=time.monotonic):
    if not 1 <= max_partitions <= 16 or budget_seconds < 2700:
        raise ValueError("Bounded partition count and upload time reserve required")
    started, reports = clock(), []
    for _ in range(max_partitions):
        # The orchestrator has a 40-minute process timeout. Leave time to save
        # and upload the checkpoint before any job-level timeout can terminate it.
        if clock() - started > budget_seconds - 2700:
            return {"state": "partial_checkpoint", "reason": "bounded_time_budget", "reports": reports}
        result = execute(specs, out, workers=1, attempts=1)
        if result.get("status") == "complete":
            return {"state": "complete", "reports": reports}
        state = out / "checkpoints/FR_electroverse_status"
        report_path = state / STATUS_REPORT
        report = json.loads(report_path.read_bytes()) if report_path.is_file() else {}
        reports.append(report)
        record_checkpoint(out, reports)
        partial = validate_partial(state)
        selected = next((part for part in partial["partitions"] if part["partition"] == report.get("partition")), None)
        if (result.get("sources", [{}])[0].get("reason") != "collector_exit_nonzero"
                or report.get("complete") is not True
                or selected is None or not is_fresh_complete(selected, datetime.now(timezone.utc))
                or report.get("partition") in [r.get("partition") for r in reports[:-1]]):
            return {"state": "partial_checkpoint", "reason": "partition_incomplete_no_provider_retry", "reports": reports}
    return {"state": "partial_checkpoint", "reason": "bounded_partition_budget", "reports": reports}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tariff-bundle", type=Path, required=True)
    p.add_argument("--expected-tariff-sha", required=True)
    p.add_argument("--max-partitions", type=int, default=16)
    p.add_argument("--budget-seconds", type=int, default=5*3600)
    p.add_argument("--github-output", type=Path, required=True)
    a = p.parse_args();out = a.out.resolve()
    if (out.exists() or out == ROOT or ROOT in out.parents
            or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or not re.fullmatch(r"[a-f0-9]{64}", a.expected_tariff_sha)):
        raise ValueError("New isolated output and pinned tariff dependency required")
    state = validated_dependency(a.tariff_bundle, "FR:electroverse_full", "electroverse")
    if artifact_digest(state)[0] != a.expected_tariff_sha:
        raise ValueError("Tariff dependency does not match the verified GitHub receipt")
    shutil.copytree(a.tariff_bundle, out / "input_dependencies/FR_electroverse_full")
    result = advance(out, specs=[s for s in read_sources() if s["id"] == SOURCE],
                     max_partitions=a.max_partitions, budget_seconds=a.budget_seconds)
    (out / "pilot-state.json").write_text(json.dumps(result, indent=2) + "\n")
    with a.github_output.open("a") as handle:
        handle.write(f"state={result['state']}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
