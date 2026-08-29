#!/usr/bin/env python3
"""Extract only public station API configuration literals from known NextCharge CDN bundles.

No application API is called: this probe downloads static public JavaScript
bundles already observed in the public web map and extracts a strict allow-list
of station-related key/value literals.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

BUNDLES = [
    "https://nextchargeapp-542e.kxcdn.com/map/scripts.d0216cc7930fd57a.js",
    "https://nextchargeapp-542e.kxcdn.com/map/main.a22e183819ebbdfc.js",
    "https://nextchargeapp-542e.kxcdn.com/map/5121.b6a40f76497e5a07.js",
]
KEYS = (
    "stationsGrid",
    "station",
    "stationConnectors",
    "stationReviews",
    "stationPhotos",
    "getUserInfoFromGeoIP",
)
OUT = Path("data/reports/ges_nextcharge_api_literal_probe.json")
SENSITIVE = re.compile(r"(token|login|password|wallet|payment|creditcard|startcharge|stopcharge|auth)", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
    aggregate = defaultdict(list)
    reports = []
    for url in BUNDLES:
        row = {"url": url}
        try:
            r = s.get(url, timeout=30)
            row.update({"status": r.status_code, "bytes": len(r.content)})
            r.raise_for_status()
            text = r.text
            found = defaultdict(list)
            for key in KEYS:
                # Object literals in minified JS: key:"value" or "key":"value".
                pats = [
                    re.compile(rf'(?<![A-Za-z0-9_$]){re.escape(key)}\s*:\s*["\']([^"\']{{1,260}})["\']'),
                    re.compile(rf'["\']{re.escape(key)}["\']\s*:\s*["\']([^"\']{{1,260}})["\']'),
                ]
                for pat in pats:
                    for m in pat.finditer(text):
                        value = m.group(1).strip()
                        if not value or SENSITIVE.search(value):
                            continue
                        item = {"value": value[:260], "kind": "host" if value.startswith(("http://", "https://")) else "path"}
                        if item not in found[key]:
                            found[key].append(item)
                        if item not in aggregate[key]:
                            aggregate[key].append(item)
            row["targetConfigLiterals"] = dict(found)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        reports.append(row)

    payload = {
        "generatedAt": now_iso(),
        "security": {
            "staticPublicBundlesOnly": True,
            "applicationApiCalled": False,
            "accountCredentialsUsed": False,
            "headersOrCookiesPersisted": False,
        },
        "targetConfigLiterals": dict(aggregate),
        "bundles": reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
