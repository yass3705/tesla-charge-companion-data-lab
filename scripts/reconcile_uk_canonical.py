#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs/uk-cpo-progress-2026-09.json"
OPEN_FEEDS_REPORT = ROOT / "reports/uk/validated-open-feeds-latest.json"
OUT = ROOT / "reports/uk/canonical-reconcile-latest.json"

EXTERNAL_ONLY = {
    "Source EV": "set_aside_external_request",
    "Shell Recharge": "set_aside_external_request",
    "Believ": "set_aside_external_free_api_account",
    "ChargePoint": "set_aside_external_request",
    "Shell Recharge ubitricity": "set_aside_external_request",
    "Blink": "set_aside_external_request",
}

def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

canonical = load(CANONICAL, {})
rows = canonical.get("cpos") or []
by_name = {r.get("name"): r for r in rows}
changes = []

# Safe deterministic promotion: PoGo only when the persisted collector proves
# full inventory AND full pricing integrity in the same run.
feed = load(OPEN_FEEDS_REPORT, {})
pogo = next((s for s in feed.get("sources") or [] if s.get("name") == "PoGo Charge"), None)
if pogo:
    summary = pogo.get("summary") or {}
    audit = summary.get("sourceAudit") or pogo.get("sourceAudit") or {}
    safe_complete = (
        summary.get("status") == "complete"
        and bool(audit.get("coverageComplete"))
        and bool(audit.get("pricingComplete"))
        and not (summary.get("missingTariffIds") or [])
        and int(summary.get("locations") or 0) >= int(audit.get("smartChargingReportedTotal") or 0) > 0
    )
    row = by_name.get("PoGo Charge")
    if row and safe_complete and not str(row.get("status") or "").startswith("complete"):
        before = row.get("status")
        row["status"] = "complete"
        row["evidence"] = (
            f"Persisted UK collector evidence: {summary.get('locations')} / "
            f"{audit.get('smartChargingReportedTotal')} locations, "
            f"{summary.get('connectors')} connectors, pricing complete, "
            f"no missing tariff IDs."
        )
        row["next"] = "validated; include in scheduled UK aggregation. Fail closed if future coverage regresses."
        row["dataset"] = "data/national/uk_validated_open_feeds.json.gz"
        row["report"] = "reports/uk/validated-open-feeds-latest.json"
        changes.append({"name": "PoGo Charge", "from": before, "to": "complete", "reason": "full_location_and_pricing_evidence"})

# These are not autonomous technical residuals: the current ledger already
# documents an external/open-data account/request dependency. Keep them visible,
# but remove them from the active autonomous queue.
for name, target in EXTERNAL_ONLY.items():
    row = by_name.get(name)
    if not row:
        continue
    status = str(row.get("status") or "")
    if status.startswith("partial"):
        before = status
        row["status"] = target
        row["next"] = "Set aside pending the already-identified external/open-data access route; do not repeat anonymous discovery."
        changes.append({"name": name, "from": before, "to": target, "reason": "documented_external_access_dependency"})

if changes:
    canonical["updatedAt"] = datetime.now(timezone.utc).date().isoformat()
    policy = canonical.setdefault("autopilotPolicy", {})
    policy.update({
        "updatedAt": canonical["updatedAt"],
        "kpi": "Reduce actionable partial CPOs through evidence-backed promotions or evidence-backed set-aside classification.",
        "isolatedFailures": "An isolated source failure must not trigger immediate reruns of an otherwise useful batch.",
        "canonicalReconciliation": "Successful source results are persisted even when another source in the same batch fails, then reconciled into the canonical ledger.",
    })
    save(CANONICAL, canonical)

out = {
    "generatedAt": now_iso(),
    "changes": changes,
    "changeCount": len(changes),
    "canonicalUpdatedAt": canonical.get("updatedAt"),
}
save(OUT, out)
print(json.dumps(out, ensure_ascii=False, indent=2))
