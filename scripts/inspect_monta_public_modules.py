#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://cdn.monta.app/control/hub/assets"
FILES = [
    "use-public-tariffs-kFlP_gIp.js",
    "deeplinks-api-DfouvZRW.js",
    "charge-points-api-C25y_gLF.js",
    "price-groups-api-s7tBvtb3.js",
    "charge-point-detail-api-BDg_2hI1.js",
    "sites-search-api-Df3kz9OJ.js",
    "monta-urls-J6q9Peb-.js",
    "src-C_4q6C_O.js",
    "use-operator-team-id-C1mlEbjy.js",
]
KEYS = [
    "listTariffsCreator", "public tariff", "publicTariff", "tariff", "price",
    "deeplink", "deepLink", "chargePoint", "charge-point", "priceGroup",
    "price-group", "qr", "guest", "adHoc", "ad-hoc", "publicNetwork",
    "public-network", "portalApiUrl", "apiGatewayUrl",
]


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "TeslaChargeCompanion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.status), r.read().decode("utf-8", "ignore")
    except Exception as e:
        return 0, f"ERROR {type(e).__name__}: {e}"


def interesting_strings(s: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    pats = [
        r'https?://[^"\'`\\\s]+',
        r'/[A-Za-z0-9_.~?=&%{}:$@+\-]+(?:/[A-Za-z0-9_.~?=&%{}:$@+\-]+)+',
    ]
    for pat in pats:
        for m in re.finditer(pat, s):
            x = m.group(0)
            if any(k in x.lower() for k in ["api", "price", "tariff", "charge", "deep", "public", "site", "qr", "guest"]):
                if x not in seen:
                    seen.add(x)
                    out.append(x)
    return out[:800]


def contexts(s: str) -> list[dict[str, str]]:
    out = []
    low = s.lower()
    for key in KEYS:
        start = 0
        n = 0
        while n < 25:
            i = low.find(key.lower(), start)
            if i < 0:
                break
            a, b = max(0, i - 360), min(len(s), i + 900)
            out.append({"key": key, "context": s[a:b].replace("\n", " ")})
            start = i + len(key)
            n += 1
    return out


def main() -> None:
    report = {"generatedAt": datetime.now(timezone.utc).isoformat(), "modules": []}
    for f in FILES:
        url = f"{BASE}/{f}"
        status, body = fetch(url)
        item = {"file": f, "url": url, "status": status, "bytes": len(body.encode('utf-8'))}
        if status == 200:
            item["strings"] = interesting_strings(body)
            item["contexts"] = contexts(body)
        else:
            item["error"] = body[:500]
        report["modules"].append(item)
    p = Path("data/reports/waat_monta_module_endpoints.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for m in report["modules"]:
        print("=====", m["file"], "status", m["status"], "bytes", m["bytes"], "=====")
        for x in m.get("strings", [])[:120]:
            print(x)
        for c in m.get("contexts", [])[:60]:
            print(f"[{c['key']}] {c['context'][:1200]}")


if __name__ == "__main__":
    main()
