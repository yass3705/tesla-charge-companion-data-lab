#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs/uk-cpo-progress-2026-09.json"
OPEN_FEEDS_REPORT = ROOT / "reports/uk/validated-open-feeds-latest.json"
LIDL_INVENTORY_REPORT = ROOT / "reports/uk/lidl-public-ev-stores-latest.json"
LIDL_PRICING_REPORT = ROOT / "reports/uk/lidl-official-pricing-latest.json"
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

# Safe deterministic Lidl promotion requires BOTH an official public-store
# inventory and the separately persisted official pricing evidence.
lidl_inventory = load(LIDL_INVENTORY_REPORT, {})
lidl_pricing = load(LIDL_PRICING_REPORT, {})
lidl_row = by_name.get("Lidl")
lidl_safe = (
    lidl_row
    and lidl_inventory.get("status") == "location_inventory_complete_from_public_store_finder"
    and int(lidl_inventory.get("evChargingStores") or 0) > 0
    and int(lidl_inventory.get("storePagesParsed") or 0) >= int(lidl_inventory.get("evChargingStores") or 0)
    and bool(lidl_pricing.get("officialSource"))
    and bool(lidl_pricing.get("pricingComplete"))
)
if lidl_safe and not str(lidl_row.get("status") or "").startswith("complete"):
    before = lidl_row.get("status")
    lidl_row["status"] = "complete"
    lidl_row["access"] = "official_public_store_inventory_plus_official_network_pricing"
    lidl_row["evidence"] = (
        f"Official Lidl GB public store finder recovered {lidl_inventory.get('evChargingStores')} "
        f"EV-charging stores from {lidl_inventory.get('storePagesParsed')} parsed store pages; "
        "official Lidl GB tariff evidence is complete and persisted separately."
    )
    lidl_row["next"] = "validated; refresh public store inventory and official pricing on schedule."
    lidl_row["dataset"] = "data/national/uk_lidl_public_ev_stores.json.gz"
    lidl_row["report"] = "reports/uk/lidl-public-ev-stores-latest.json"
    changes.append({"name":"Lidl","from":before,"to":"complete","reason":"official_store_inventory_and_pricing_complete"})

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
