#!/usr/bin/env python3
"""Zero-cost UK TCC autopilot.

Primary KPI: reduce actionable partial CPOs. Maintenance collectors are secondary.
The worker never calls an AI API and never invents endpoint/tariff data.

Important scheduling rules:
- a degraded multi-source maintenance run is persisted and is NOT retried every hour;
- successful source results survive even when another source in the same batch fails;
- canonical reconciliation runs before and after each deterministic task;
- maintenance tasks rotate instead of one failing task starving the queue.
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
RECONCILE_REPORT = ROOT / "reports/uk/canonical-reconcile-latest.json"

# Maintenance only. Order intentionally rotates direct collectors before the
# broad multi-source batch so a degraded batch cannot starve the queue.
TASKS = [
    {
        "id": "ionity_direct",
        "interval_hours": 24,
        "command": [sys.executable, "scripts/ionity_station_tariffs_uk.py"],
    },
    {
        "id": "fastned_direct",
        "interval_hours": 24,
        "command": [sys.executable, "scripts/fastned_station_inventory_uk.py"],
    },
    {
        "id": "validated_open_feeds",
        "interval_hours": 24,
        "command": [sys.executable, "scripts/collect_uk_validated_open_feeds.py",
                    "--output", "artifacts/uk-validated-open-feeds.json"],
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
    """Return one due task using last attempt, not last success.

    A completed degraded attempt consumes the maintenance interval. This prevents
    char.gy/Go Zero from causing hourly reruns of a 20-minute 12-source batch.
    """
    runs = state.get("tasks", {})
    for task in TASKS:
        task_state = runs.get(task["id"]) or {}
        last_attempt = parse_time(task_state.get("lastAttemptAt"))
        if last_attempt is None or now - last_attempt >= timedelta(hours=task["interval_hours"]):
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


def run_reconciler():
    proc = subprocess.run(
        [sys.executable, "scripts/reconcile_uk_canonical.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError("canonical reconciler failed: " + proc.stdout[-2000:])
    return load_json(RECONCILE_REPORT, {"changes": [], "changeCount": 0})


def publish_validated_open_feeds():
    """Persist all successful source results even when the collector exits 2."""
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
            {"name": s.get("name"), "summary": s.get("summary"),
             "sourceAudit": s.get("sourceAudit"), "endpoints": s.get("endpoints")}
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


def build_report(canonical, state, run_result, task_due_after, reconcile):
    rows = canonical.get("cpos") or []
    buckets = {"complete": [], "setAside": [], "actionable": [], "other": []}
    for row in rows:
        buckets[status_bucket(row.get("status"))].append(row.get("name"))

    # "globalBlocked" is reserved for a country-level dependency requiring user
    # action. Isolated set-asides or technical residuals do not trigger it.
    global_blocked = False

    return {
        "schemaVersion": 2,
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
        "canonicalReconciliation": reconcile,
        "nextDeterministicTask": task_due_after,
        "globalBlocked": global_blocked,
        "globalBlockedDefinition": "True only for a country-level dependency requiring user intervention; isolated CPO blockers remain set aside.",
        "limits": [
            "Deterministic worker executes only explicitly coded collectors/reconcilers.",
            "No OpenAI or other paid AI API is used.",
            "Unresolved CPO-specific technical cases remain visible without blocking the country.",
        ],
    }


def write_markdown(report):
    c = report["counts"]
    lr = report.get("lastRun") or {}
    rec = report.get("canonicalReconciliation") or {}
    lines = [
        "# UK TCC zero-cost autopilot",
        "",
        f"- Generated: {report['generatedAt']}",
        f"- AI/API cost: **£0 / €0**",
        f"- Complete: **{c['complete']} / {c['totalCanonicalCpos']}**",
        f"- Actionable partial: **{c['actionablePartial']}**",
        f"- Set aside / external blocked: **{c['setAsideOrExternalBlocked']}**",
        f"- Canonical changes this cycle: **{rec.get('changeCount', 0)}**",
        "",
        "## Last deterministic run",
        f"- Task: **{lr.get('taskId', 'none')}**",
        f"- Return code: **{lr.get('returnCode', 'n/a')}**",
        "",
        "## Remaining actionable partials",
    ]
    names = report.get("actionablePartialNames") or []
    lines += [f"- {name}" for name in names] if names else ["- None"]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-only", action="store_true")
    args = ap.parse_args()

    canonical = load_json(CANONICAL, {})
    if not canonical or canonical.get("countryCode") != "GB":
        raise SystemExit("UK canonical ledger missing or invalid")

    state = load_json(STATE, {"schemaVersion": 2, "country": "GB", "tasks": {}, "history": []})

    # Reconcile persisted evidence before deciding what remains actionable.
    reconcile_before = run_reconciler()
    canonical = load_json(CANONICAL, canonical)

    now = now_utc()
    task = None if args.audit_only else due_task(state, now)
    last_report = parse_time(state.get("lastReportAt"))
    report_due = last_report is None or now - last_report >= timedelta(hours=1)

    if task is None and not report_due and not args.audit_only and not reconcile_before.get("changeCount"):
        print(json.dumps({"country": "GB", "status": "idle", "reason": "no maintenance task due and hourly report not due"}))
        return

    run_result = {
        "taskId": "report_only" if not args.audit_only else "audit_only",
        "returnCode": 0,
        "startedAt": iso(now),
        "finishedAt": iso(now),
    }

    if task:
        try:
            run_result = run_command(task)

            # Persist useful successes from a degraded multi-source run before
            # interpreting the aggregate return code.
            if task["id"] == "validated_open_feeds" and (ROOT / "artifacts/uk-validated-open-feeds.json").exists():
                publish_validated_open_feeds()

            task_state = state.setdefault("tasks", {}).setdefault(task["id"], {})
            task_state["lastAttemptAt"] = run_result["finishedAt"]
            task_state["lastReturnCode"] = run_result["returnCode"]
            task_state["lastCompletedAt"] = run_result["finishedAt"]

            if run_result["returnCode"] == 0:
                task_state["lastSuccessAt"] = run_result["finishedAt"]
                task_state["consecutiveFailures"] = 0
                task_state.pop("degradedAt", None)
            else:
                task_state["degradedAt"] = run_result["finishedAt"]
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
            task_state["lastCompletedAt"] = run_result["finishedAt"]
            task_state["lastReturnCode"] = 99
            task_state["consecutiveFailures"] = int(task_state.get("consecutiveFailures", 0)) + 1

    # Reconcile again because this run may have produced new successful evidence.
    reconcile_after = run_reconciler()
    reconcile = reconcile_after if reconcile_after.get("changeCount") else reconcile_before
    canonical = load_json(CANONICAL, canonical)

    history = state.setdefault("history", [])
    history.append({k: run_result.get(k) for k in ("taskId", "startedAt", "finishedAt", "returnCode")})
    state["history"] = history[-50:]
    state["updatedAt"] = iso(now_utc())

    next_task = due_task(state, now_utc())
    report = build_report(canonical, state, run_result, None if next_task is None else next_task["id"], reconcile)
    state["globalBlocked"] = report["globalBlocked"]
    state["lastReportAt"] = report["generatedAt"]

    save_json(STATE, state)
    save_json(REPORT_JSON, report)
    write_markdown(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Return code 2 from a multi-source maintenance batch is a degraded checkpoint,
    # not a workflow-level failure. Hard failures still surface.
    if run_result.get("returnCode") not in (0, 2, None):
        raise SystemExit(run_result["returnCode"])


if __name__ == "__main__":
    main()
