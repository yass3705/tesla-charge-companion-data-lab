#!/usr/bin/env python3
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.fastvolt.net/api/pages"
BASELINE = Path("reports/morocco/fastvolt/latest-public-map-inventory.json")
OUT = Path("reports/morocco/fastvolt/latest-state-freshness.json")

req = urllib.request.Request(URL, headers={"User-Agent": "tcc-public-readonly-probe/1.0"}, method="GET")
with urllib.request.urlopen(req, timeout=25) as r:
    current = json.load(r)

baseline = json.loads(BASELINE.read_text())
old_items = baseline.get("chargers", [])
new_items = current if isinstance(current, list) else current.get("chargers", current.get("data", []))

def norm(items):
    out = {}
    for x in items:
        if not isinstance(x, dict):
            continue
        cid = x.get("charger_id") or x.get("id")
        if cid is None:
            continue
        out[str(cid)] = {
            "name": x.get("charger_name") or x.get("name"),
            "state": x.get("state"),
        }
    return out

old = norm(old_items)
new = norm(new_items)
common = sorted(set(old) & set(new))
changes = []
for cid in common:
    if old[cid]["state"] != new[cid]["state"]:
        changes.append({
            "charger_id": cid,
            "charger_name": new[cid]["name"] or old[cid]["name"],
            "old_state": old[cid]["state"],
            "new_state": new[cid]["state"],
        })

report = {
    "schema_version": 1,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source": URL,
    "policy": {
        "read_only_get_only": True,
        "no_login": True,
        "no_credentials": True,
        "no_mutations": True,
        "raw_response_body_persisted": False,
    },
    "modeling": {
        "cpo_operator": "FastVolt / Afrimobility",
        "site_brand": None,
        "app_source_access_network": "FastVolt public web map",
        "tariff_channel": "FastVolt direct",
        "status_source": "candidate only; promote only if freshness is demonstrated and semantics are separately validated",
    },
    "summary": {
        "baseline_count": len(old),
        "current_count": len(new),
        "common_count": len(common),
        "changed_state_count": len(changes),
        "freshness_demonstrated": len(changes) > 0,
        "baseline_state_counts": dict(Counter(v["state"] for v in old.values())),
        "current_state_counts": dict(Counter(v["state"] for v in new.values())),
    },
    "changed_states": changes[:50],
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report["summary"], ensure_ascii=False))
