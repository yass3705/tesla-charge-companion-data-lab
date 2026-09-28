#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://nap-be.eco-movement.com/datex2/v1/status/"
TOKEN = os.environ["BELGIUM_NAP_TOKEN"].strip()
SRC = "reports/belgium-national-first-pass-2026-09-28.json"
OUT = "reports/belgium-shell-missing-status-probe-2026-09-28.json"

report = json.loads(Path(SRC).read_text(encoding="utf-8"))
items = report.get("missingPriceEvses") or []

results = []
for i, item in enumerate(items):
    ext_ids = item.get("externalIdentifiers") or []
    evse_id = ext_ids[0] if ext_ids else None
    if not evse_id:
        results.append({**item, "httpStatus": None, "error": "missing external EVSE id"})
        continue
    if i:
        time.sleep(11)
    url = BASE + urllib.parse.quote(evse_id, safe="")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "User-Agent": "tesla-charge-companion-data-lab/1.0",
        },
    )
    row = {**item, "queriedEvseId": evse_id}
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            row["httpStatus"] = resp.status
            row["response"] = body
            text = json.dumps(body)
            row["hasEnergyRateUpdate"] = "energyRateUpdate" in text
            row["hasEnergyPrice"] = "energyPrice" in text
    except urllib.error.HTTPError as e:
        row["httpStatus"] = e.code
        row["errorBody"] = e.read().decode("utf-8", "replace")[:2000]
        row["hasEnergyRateUpdate"] = False
        row["hasEnergyPrice"] = False
    except Exception as e:
        row["httpStatus"] = None
        row["error"] = type(e).__name__ + ": " + str(e)
        row["hasEnergyRateUpdate"] = False
        row["hasEnergyPrice"] = False
    results.append(row)

summary = {
    "requested": len(items),
    "http200": sum(1 for r in results if r.get("httpStatus") == 200),
    "withEnergyRateUpdate": sum(1 for r in results if r.get("hasEnergyRateUpdate")),
    "withEnergyPrice": sum(1 for r in results if r.get("hasEnergyPrice")),
    "notFound": sum(1 for r in results if r.get("httpStatus") == 404),
    "otherErrors": sum(1 for r in results if r.get("httpStatus") not in (200, 404)),
}
out = {"summary": summary, "results": results}
Path(OUT).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
