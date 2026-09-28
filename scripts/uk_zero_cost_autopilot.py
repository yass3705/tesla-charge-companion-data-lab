#!/usr/bin/env python3
"""Zero-cost UK TCC autopilot.

Runs deterministic, already-validated UK collectors only. It never calls an AI API.
Each invocation performs at most one due collection task, persists state, rebuilds
an audit/report from the canonical UK ledger, and exits. Unknown/technical cases
are never guessed: they stay queued or set aside for human/ChatGPT investigation.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs/uk-cpo-progress-2026-09.json"
STATE = ROOT / "reports/uk/autopilot-state.json"
REPORT_JSON = ROOT / "reports/uk/autopilot-latest.json"
REPORT_MD = ROOT / "reports/uk/autopilot-latest.md"

TASKS = [
    {
        "id": "validated_open_feeds",
        "interval_hours": 6,
        "command": [sys.executable, "scripts/collect_uk_validated_open_feeds.py",
                    "--output", "artifacts/uk-validated-open-feeds.json"],
    },
    {
        "id": "fastned_direct",
        "interval_hours": 24,
        "command": [sys.executable, "scripts/fastned_station_inventory_uk.py"],
    },
    {
        "id": "ionity_direct",
        "interval_hours": 24,
        "command": [sys.executable, "scripts/ionity_station_tariffs_uk.py"],
    },
]

COMPLETE_PREFIXES = ("complete", "coverage_platform_scope_not_cpo")
SET_ASIDE_PREFIXES = ("set_aside", "blocked_external")
ACTIONABLE_PREFIXES = ("partial",)


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def due_task(state, now):
    runs = state.get("tasks", {})
    for task in TASKS:
        task_state = runs.get(task["id"]) or {}
        last_success = parse_time(task_state.get("lastSuccessAt"))
        last_attempt = parse_time(task_state.get("lastAttemptAt"))

        if last_success is None:
            # First attempt is due immediately. After a failure, wait at least
            # one hour before retrying so the 5-minute scheduler cannot build
            # a queue of long duplicate runs.
            if last_attempt is None or now - last_attempt >= timedelta(hours=1):
                return task
            continue

        if now - last_success >= timedelta(hours=task["interval_hours"]):
            # Also avoid rapid duplicate retries if a recent attempt failed.
            if last_attempt is None or now - last_attempt >= timedelta(hours=1):
                return task
    return None


def run_command(task):
    started = now_utc()
    proc = subprocess.run(
        task["command"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=50 * 60,
    )
    return {
        "taskId": task["id"],
        "startedAt": iso(started),
        "finishedAt": iso(now_utc()),
        "returnCode": proc.returncode,
        "outputTail": proc.stdout[-12000:],
    }


def publish_validated_open_feeds():
    src = ROOT / "artifacts/uk-validated-open-feeds.json"
    if not src.exists():
        raise RuntimeError("validated open feeds collector produced no artifact")
    raw = src.read_bytes()
    dst = ROOT / "data/national/uk_validated_open_feeds.json.gz"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dst, "wb", compresslevel=9) as g:
        g.write(raw)
    p = json.loads(raw)
    report = {
        "country": "GB",
        "retrievedAt": p.get("retrievedAt"),
        "summary": p.get("summary"),
        "failures": p.get("failures", []),
        "sources": [
            {"name": s.get("name"), "summary": s.get("summary"), "endpoints": s.get("endpoints")}
            for s in p.get("sources", [])
        ],
    }
    save_json(ROOT / "reports/uk/validated-open-feeds-latest.json", report)


def status_bucket(status):
    s = str(status or "").lower()
    if s.startswith(COMPLETE_PREFIXES):
        return "complete"
    if s.startswith(SET_ASIDE_PREFIXES):
        return "setAside"
    if s.startswith(ACTIONABLE_PREFIXES):
        return "actionable"
    return "other"


def build_report(canonical, state, run_result, task_due_after):
    rows = canonical.get("cpos") or []
    buckets = {"complete": [], "setAside": [], "actionable": [], "other": []}
    for row in rows:
        buckets[status_bucket(row.get("status"))].append(row.get("name"))
    global_blocked = bool(rows) and not buckets["actionable"] and not task_due_after
    return {
        "schemaVersion": 1,
        "country": "GB",
        "generatedAt": iso(now_utc()),
        "mode": "zero_cost_deterministic",
        "aiApiCalls": 0,
        "canonical": str(CANONICAL.relative_to(ROOT)),
        "canonicalUpdatedAt": canonical.get("updatedAt"),
        "firstPassComplete": (canonical.get("firstPass") or {}).get("countryFirstPassComplete"),
        "counts": {
            "totalCanonicalCpos": len(rows),
            "complete": len(buckets["complete"]),
            "actionablePartial": len(buckets["actionable"]),
            "setAsideOrExternalBlocked": len(buckets["setAside"]),
            "other": len(buckets["other"]),
        },
        "actionablePartialNames": buckets["actionable"],
        "setAsideNames": buckets["setAside"],
        "otherNames": buckets["other"],
        "lastRun": run_result,
        "nextDeterministicTask": task_due_after,
        "globalBlocked": global_blocked,
        "globalBlockedDefinition": "No deterministic task due and no canonical partial case remains. Set-aside cases alone do not block the country.",
        "limits": [
            "This pilot can execute only explicitly coded deterministic collectors.",
            "It does not invent endpoints, bypass authentication, or call OpenAI/other paid AI APIs.",
            "Technical residuals without a coded handler remain visible for later interactive investigation.",
        ],
    }


def write_markdown(report):
    c = report["counts"]
    lr = report.get("lastRun") or {}
    lines = [
        "# UK TCC zero-cost autopilot",
        "",
        f"- Generated: {report['generatedAt']}",
        f"- AI/API cost: **£0 / €0** (AI API calls: {report['aiApiCalls']})",
        f"- First pass complete: **{report['firstPassComplete']}**",
        f"- Canonical CPOs: **{c['totalCanonicalCpos']}**",
        f"- Complete: **{c['complete']}**",
        f"- Actionable partial: **{c['actionablePartial']}**",
        f"- Set aside / external blocked: **{c['setAsideOrExternalBlocked']}**",
        f"- Other: **{c['other']}**",
        "",
        "## Last deterministic run",
        "",
        f"- Task: **{lr.get('taskId', 'none')}**",
        f"- Return code: **{lr.get('returnCode', 'n/a')}**",
        "",
        "## Remaining actionable partials",
        "",
    ]
    names = report.get("actionablePartialNames") or []
    lines += [f"- {name}" for name in names] if names else ["- None"]
    lines += ["", "## Set aside", ""]
    names = report.get("setAsideNames") or []
    lines += [f"- {name}" for name in names] if names else ["- None"]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-only", action="store_true")
    args = ap.parse_args()

    canonical = load_json(CANONICAL, {})
    if not canonical or canonical.get("countryCode") != "GB":
        raise SystemExit("UK canonical ledger missing or invalid")

    state = load_json(STATE, {"schemaVersion": 1, "country": "GB", "tasks": {}, "history": []})
    now = now_utc()
    task = None if args.audit_only else due_task(state, now)
    last_report = parse_time(state.get("lastReportAt"))
    report_due = last_report is None or now - last_report >= timedelta(hours=1)
    if task is None and not report_due and not args.audit_only:
        print(json.dumps({"country": "GB", "status": "idle", "reason": "no deterministic task due and 3h report not due"}))
        return

    run_result = {"taskId": "report_only" if not args.audit_only else "audit_only", "returnCode": 0, "startedAt": iso(now), "finishedAt": iso(now)}

    if task:
        try:
            run_result = run_command(task)
            task_state = state.setdefault("tasks", {}).setdefault(task["id"], {})
            task_state["lastAttemptAt"] = run_result["finishedAt"]
            task_state["lastReturnCode"] = run_result["returnCode"]
            if run_result["returnCode"] == 0:
                task_state["lastSuccessAt"] = run_result["finishedAt"]
                if task["id"] == "validated_open_feeds":
                    publish_validated_open_feeds()
            else:
                task_state["consecutiveFailures"] = int(task_state.get("consecutiveFailures", 0)) + 1
        except Exception as exc:
            run_result = {
                "taskId": task["id"],
                "startedAt": iso(now),
                "finishedAt": iso(now_utc()),
                "returnCode": 99,
                "outputTail": f"{type(exc).__name__}: {exc}",
            }
            task_state = state.setdefault("tasks", {}).setdefault(task["id"], {})
            task_state["lastAttemptAt"] = run_result["finishedAt"]
            task_state["lastReturnCode"] = 99
            task_state["consecutiveFailures"] = int(task_state.get("consecutiveFailures", 0)) + 1

    history = state.setdefault("history", [])
    history.append({k: run_result.get(k) for k in ("taskId", "startedAt", "finishedAt", "returnCode")})
    state["history"] = history[-50:]
    state["updatedAt"] = iso(now_utc())

    next_task = due_task(state, now_utc())
    report = build_report(
        canonical,
        state,
        run_result,
        None if next_task is None else next_task["id"],
    )
    state["globalBlocked"] = report["globalBlocked"]
    state["lastReportAt"] = report["generatedAt"]

    save_json(STATE, state)
    save_json(REPORT_JSON, report)
    write_markdown(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if run_result.get("returnCode") not in (0, None):
        raise SystemExit(run_result["returnCode"])


if __name__ == "__main__":
    main()
