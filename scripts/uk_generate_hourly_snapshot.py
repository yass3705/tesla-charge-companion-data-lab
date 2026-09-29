#!/usr/bin/env python3
# canonical-refresh-trigger: 2026-09-29
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs/uk-cpo-progress-2026-09.json"
STATE = ROOT / "reports/uk/autopilot-state.json"
REPORT_JSON = ROOT / "reports/uk/autopilot-latest.json"
REPORT_MD = ROOT / "reports/uk/autopilot-latest.md"

COMPLETE_PREFIXES = ("complete", "coverage_platform_scope_not_cpo")
SET_ASIDE_PREFIXES = ("set_aside", "blocked_external")
ACTIONABLE_PREFIXES = ("partial",)

def iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def bucket(status):
    s = str(status or "").lower()
    if s.startswith(COMPLETE_PREFIXES):
        return "complete"
    if s.startswith(SET_ASIDE_PREFIXES):
        return "setAside"
    if s.startswith(ACTIONABLE_PREFIXES):
        return "actionable"
    return "other"

canonical = load(CANONICAL, {})
state = load(STATE, {})
rows = canonical.get("cpos") or []
buckets = {"complete": [], "setAside": [], "actionable": [], "other": []}
for row in rows:
    buckets[bucket(row.get("status"))].append(row.get("name"))

report = {
    "schemaVersion": 2,
    "country": "GB",
    "generatedAt": iso_now(),
    "snapshotType": "independent_hourly_audit",
    "mode": "zero_cost_deterministic",
    "aiApiCalls": 0,
    "canonical": str(CANONICAL.relative_to(ROOT)),
    "canonicalUpdatedAt": canonical.get("updatedAt"),
    "workerStateUpdatedAt": state.get("updatedAt"),
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
    "lastDeterministicRun": (state.get("history") or [None])[-1],
    "taskState": state.get("tasks") or {},
    "globalBlocked": bool(state.get("globalBlocked", False)),
    "note": "Independent audit snapshot. It never runs collectors and never mutates worker task state."
}

REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
REPORT_MD.write_text(
    "# UK TCC zero-cost autopilot snapshot\n\n"
    f"- Generated: {report['generatedAt']}\n"
    f"- Canonical CPOs: **{report['counts']['totalCanonicalCpos']}**\n"
    f"- Complete: **{report['counts']['complete']}**\n"
    f"- Actionable partial: **{report['counts']['actionablePartial']}**\n"
    f"- Set aside / external blocked: **{report['counts']['setAsideOrExternalBlocked']}**\n"
    f"- Worker state updated: **{report.get('workerStateUpdatedAt')}**\n"
    f"- Global blocked: **{report['globalBlocked']}**\n",
    encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False, indent=2))
