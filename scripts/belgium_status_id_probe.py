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

candidates = [
    ("external-raw", "BE*TNM*EGL3203003301*1"),
    ("external-compact", "BETNMEGL32030033011"),
    ("internal-id", "ef30d8f7c643466db9a84173d3109401-1"),
]

results = []
for idx, (kind, evse_id) in enumerate(candidates):
    if idx:
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
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body[:2000]
            results.append({"kind": kind, "evseId": evse_id, "status": resp.status, "body": parsed})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body[:2000]
        results.append({"kind": kind, "evseId": evse_id, "status": e.code, "body": parsed})
    except Exception as e:
        results.append({"kind": kind, "evseId": evse_id, "status": None, "error": type(e).__name__ + ": " + str(e)})

out = {"probe": "Shell Recharge missing-price EVSE identifier formats", "results": results}
Path("reports").mkdir(exist_ok=True)
Path("reports/belgium-status-id-probe-2026-09-28.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(out, ensure_ascii=False, indent=2))
