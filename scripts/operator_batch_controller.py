#!/usr/bin/env python3
"""Stateful sequential controller for operator tariff batches.

The controller persists the operator currently in flight before dispatch.  A
workflow_run event is accepted only when it belongs to that operator and its run
ID is newer than the controller run that requested the dispatch.  Late/duplicate
workflow events are therefore ignored instead of advancing or halting the queue.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    return json.loads(path.read_text(encoding="utf-8"))


def parse_operator(title: str, valid_keys: set[str]) -> str | None:
    title = title or ""
    # Current run-name is "Operator batch item · <key>".  Keep a conservative
    # fallback for GitHub render variations, but never accept a key outside the queue.
    candidates: list[str] = []
    if "·" in title:
        candidates.append(title.rsplit("·", 1)[-1].strip())
    m = re.search(r"Operator batch item\s*[-:]\s*([A-Za-z0-9_-]+)\s*$", title)
    if m:
        candidates.append(m.group(1))
    for candidate in candidates:
        if candidate in valid_keys:
            return candidate
    return None


def marker_status(queue: list[dict]) -> tuple[list[str], list[str]]:
    completed: list[str] = []
    missing: list[str] = []
    for item in queue:
        if Path(item["marker"]).exists():
            completed.append(item["key"])
        else:
            missing.append(item["key"])
    return completed, missing


def write_outputs(path: str | None, values: dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for key, value in values.items():
            f.write(f"{key}={value}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/operator_batch.json")
    ap.add_argument("--state", default="reports/batch/runtime_state.json")
    ap.add_argument("--event", choices=["launch", "workflow_run"], required=True)
    ap.add_argument("--controller-run-id", type=int, required=True)
    ap.add_argument("--previous-run-id", type=int, default=0)
    ap.add_argument("--previous-conclusion", default="")
    ap.add_argument("--previous-title", default="")
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--github-output", default=None)
    args = ap.parse_args()

    cfg_path = Path(args.config)
    state_path = Path(args.state)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    queue = list(cfg.get("queue") or [])
    valid_keys = {item["key"] for item in queue}
    marker_by_key = {item["key"]: item["marker"] for item in queue}
    enabled = bool(cfg.get("enabled", False))
    batch_id = str(cfg.get("batchId") or "")
    generation = int(cfg.get("launchGeneration") or 0)

    default_state = {
        "schemaVersion": "1.0.0",
        "dataset": "operator-batch-runtime-state",
        "batchId": batch_id,
        "launchGeneration": generation,
        "inFlight": None,
        "dispatchAfterControllerRunId": None,
        "dispatchStatus": None,
        "dispatchHttpCode": None,
        "halted": False,
        "failedOperator": None,
        "failureReason": None,
        "lastCompletedOperator": None,
        "lastCompletedRunId": None,
        "lastControllerRunId": None,
        "lastEvent": None,
        "lastDecision": None,
        "lastIgnoredRunId": None,
        "lastIgnoredReason": None,
        "done": False,
    }
    state = load_json(state_path, default_state)

    generation_changed = (
        state.get("batchId") != batch_id
        or int(state.get("launchGeneration") or 0) != generation
    )
    if generation_changed:
        state = dict(default_state)
        state["lastDecision"] = "generation_reset"

    state["batchId"] = batch_id
    state["launchGeneration"] = generation
    state["lastControllerRunId"] = args.controller_run_id
    state["lastEvent"] = args.event
    state["done"] = False

    completed, missing = marker_status(queue)
    ignored = False
    should_dispatch = False
    next_key = ""

    if args.event == "launch":
        if args.restart:
            state["inFlight"] = None
            state["halted"] = False
            state["failedOperator"] = None
            state["failureReason"] = None
            state["dispatchStatus"] = None
            state["dispatchHttpCode"] = None
            state["lastDecision"] = "manual_restart"
        elif generation_changed:
            state["lastDecision"] = "generation_restart"
        elif not enabled:
            state["lastDecision"] = "batch_disabled"
        elif state.get("inFlight"):
            state["lastDecision"] = "launch_ignored_already_in_flight"
            ignored = True
        elif state.get("halted"):
            state["lastDecision"] = "launch_ignored_halted_same_generation"
            ignored = True
        else:
            state["lastDecision"] = "launch_continue"

    else:  # workflow_run
        previous_key = parse_operator(args.previous_title, valid_keys)
        dispatch_floor = int(state.get("dispatchAfterControllerRunId") or 0)
        if not previous_key:
            ignored = True
            state["lastIgnoredRunId"] = args.previous_run_id or None
            state["lastIgnoredReason"] = "unrecognized_or_non_queue_workflow_title"
            state["lastDecision"] = "ignored_workflow_run"
        elif args.previous_run_id <= dispatch_floor:
            ignored = True
            state["lastIgnoredRunId"] = args.previous_run_id
            state["lastIgnoredReason"] = "stale_run_predates_latest_dispatch_controller"
            state["lastDecision"] = "ignored_stale_workflow_run"
        elif state.get("inFlight") != previous_key:
            ignored = True
            state["lastIgnoredRunId"] = args.previous_run_id
            state["lastIgnoredReason"] = (
                f"operator_mismatch_expected_{state.get('inFlight') or 'none'}_got_{previous_key}"
            )
            state["lastDecision"] = "ignored_non_inflight_workflow_run"
        elif args.previous_conclusion != "success":
            state["inFlight"] = None
            state["halted"] = True
            state["failedOperator"] = previous_key
            state["failureReason"] = f"operator_run_{args.previous_conclusion or 'unknown'}"
            state["dispatchStatus"] = "operator_failed"
            state["lastDecision"] = "halt_after_operator_failure"
        elif not Path(marker_by_key[previous_key]).exists():
            # A green run without the validated marker is not sufficient to advance.
            state["inFlight"] = None
            state["halted"] = True
            state["failedOperator"] = previous_key
            state["failureReason"] = "successful_run_without_validated_marker"
            state["dispatchStatus"] = "operator_success_without_marker"
            state["lastDecision"] = "halt_after_missing_marker"
        else:
            state["inFlight"] = None
            state["halted"] = False
            state["failedOperator"] = None
            state["failureReason"] = None
            state["dispatchStatus"] = "operator_validated"
            state["lastCompletedOperator"] = previous_key
            state["lastCompletedRunId"] = args.previous_run_id
            state["lastDecision"] = "operator_validated_advance"
            completed, missing = marker_status(queue)

    # Only a clean, enabled state may request the next run.  Persist inFlight and
    # controller run ID now, before the REST workflow_dispatch call happens.
    if enabled and not ignored and not state.get("halted") and not state.get("inFlight"):
        completed, missing = marker_status(queue)
        if missing:
            next_key = missing[0]
            state["inFlight"] = next_key
            state["dispatchAfterControllerRunId"] = args.controller_run_id
            state["dispatchStatus"] = "pending_dispatch"
            state["dispatchHttpCode"] = None
            state["lastDecision"] = f"dispatch_{next_key}"
            should_dispatch = True
        else:
            state["done"] = True
            state["dispatchStatus"] = "batch_complete"
            state["lastDecision"] = "batch_complete"
    elif not enabled:
        state["lastDecision"] = "batch_disabled"

    completed, missing = marker_status(queue)
    if enabled and not missing and not state.get("inFlight") and not state.get("halted"):
        state["done"] = True

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = {
        "batchId": batch_id,
        "launchGeneration": generation,
        "enabled": enabled,
        "completed": completed,
        "missing": missing,
        "inFlight": state.get("inFlight"),
        "halted": bool(state.get("halted")),
        "failedOperator": state.get("failedOperator"),
        "ignored": ignored,
        "decision": state.get("lastDecision"),
        "next": next_key or None,
        "shouldDispatch": should_dispatch,
        "done": bool(state.get("done")),
    }
    print(json.dumps(result, ensure_ascii=False))

    write_outputs(args.github_output, {
        "enabled": "1" if enabled else "0",
        "next": next_key,
        "should_dispatch": "1" if should_dispatch else "0",
        "done": "1" if state.get("done") else "0",
        "halted": "1" if state.get("halted") else "0",
        "ignored": "1" if ignored else "0",
        "in_flight": str(state.get("inFlight") or ""),
        "decision": str(state.get("lastDecision") or ""),
        "completed_count": str(len(completed)),
        "queue_count": str(len(queue)),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
