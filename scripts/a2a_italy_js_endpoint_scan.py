#!/usr/bin/env python3
"""Scan public A2A Emoving JavaScript for station-detail AJAX endpoints.

Only public static JS is downloaded. The report stores endpoint-like strings and
short sanitized code contexts; no credentials/cookies or full third-party files.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://e-movinghub.a2a.it/acEicp/resources4/js/"
FILES = [
    "acEicp.map.cu.js",
    "acEicp.map.js",
    "acEicp.common.rechargeUtils.js",
]
OUT = Path("data/reports/a2a_italy_js_endpoint_scan.json")
PATTERNS = [
    re.compile(r"[\"']([^\"']*(?:json|action|ajax|detail|cu|connector|presa|price|tariff|station)[^\"']*)[\"']", re.I),
    re.compile(r"(?:url|type|method)\s*:\s*[\"']([^\"']+)[\"']", re.I),
]
KEYWORDS = ("json", "price", "tariff", "connector", "presa", "detail", "station", "cu", "recharge", "plug")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 TCC research"})
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def context(text: str, start: int, end: int, radius: int = 220) -> str:
    s = max(0, start - radius)
    e = min(len(text), end + radius)
    return re.sub(r"\s+", " ", text[s:e])[:700]


def main():
    rows = []
    for name in FILES:
        url = BASE + name
        text = fetch(url)
        matches = []
        seen = set()
        for pat in PATTERNS:
            for m in pat.finditer(text):
                value = m.group(1).strip()
                if len(value) > 500:
                    continue
                if not any(k in value.lower() or k in context(text, m.start(), m.end()).lower() for k in KEYWORDS):
                    continue
                key = (value, m.start())
                if key in seen:
                    continue
                seen.add(key)
                matches.append({
                    "value": value,
                    "context": context(text, m.start(), m.end()),
                })
        # Also collect literal relative backend-looking paths.
        paths = sorted(set(re.findall(r"[\"']((?:/)?(?:json|[A-Za-z0-9_]+\.action)[A-Za-z0-9_./?=&-]*)[\"']", text, re.I)))
        rows.append({
            "file": name,
            "url": url,
            "length": len(text),
            "backendLikePaths": paths[:200],
            "matches": matches[:300],
        })
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "security": {"accountCredentialsUsed": False, "cookiesPersisted": False, "fullJsPersisted": False},
        "files": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:50000])


if __name__ == "__main__":
    main()
