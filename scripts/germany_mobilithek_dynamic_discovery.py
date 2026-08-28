#!/usr/bin/env python3
"""Discover current German AFIR dynamic offers in Mobilithek.

The public Mobilithek UI uses the metadata offer search endpoint. This script is
QA-only and records only offer metadata; it does not publish anything to TCC.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search"
UA = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"
TARGETS = ("chargecloud", "eround", "qwello")


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read(8_000_000)
            return {"ok": True, "status": getattr(r, "status", 200), "data": json.loads(raw.decode("utf-8-sig"))}
    except urllib.error.HTTPError as e:
        raw = e.read(65536).decode("utf-8", errors="replace")
        return {"ok": False, "status": e.code, "error": raw[:8000]}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def flatten_offer_nodes(obj):
    """Find dicts that look like Mobilithek offers independent of response envelope."""
    found = []
    seen = set()
    def walk(x):
        if isinstance(x, dict):
            keys = {str(k).lower() for k in x}
            blob = json.dumps(x, ensure_ascii=False).lower()
            if ("offerid" in keys or "id" in keys or "publicationid" in keys) and (
                "title" in keys or "name" in keys or "afir-recharging" in blob
            ):
                ident = str(x.get("offerId") or x.get("publicationId") or x.get("id") or "")
                sig = (ident, str(x.get("title") or x.get("name") or ""))
                if sig not in seen:
                    seen.add(sig)
                    found.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return found


def compact_offer(x):
    blob = json.dumps(x, ensure_ascii=False)
    low = blob.lower()
    if "afir" not in low or "recharg" not in low:
        return None
    if not any(t in low for t in TARGETS):
        return None
    return {
        "id": str(x.get("offerId") or x.get("publicationId") or x.get("id") or ""),
        "title": x.get("title") or x.get("name") or x.get("dataName") or x.get("publicationName"),
        "provider": next((t for t in TARGETS if t in low), None),
        "dynamicHint": "dyn" in low or "dynamic" in low or "dynamisch" in low,
        "staticHint": "stat" in low or "static" in low or "statisch" in low,
        "raw": x,
    }


def main():
    # Start with the broadest request. If the API schema changed, retain its
    # response/error so the CI log tells us exactly what to adapt.
    attempts = []
    candidates = []
    payloads = [
        {},
        {"searchTerm": "AFIR-recharging"},
        {"search": "AFIR-recharging"},
        {"query": "AFIR-recharging"},
    ]
    urls = [
        BASE + "?page=0&size=500",
        BASE + "?page=0&size=100",
        BASE + "?page=0&size=50",
    ]
    for url in urls:
        for payload in payloads:
            res = request(url, payload)
            attempts.append({"url": url, "payload": payload, "ok": res.get("ok"), "status": res.get("status"), "error": res.get("error")})
            if not res.get("ok"):
                continue
            for node in flatten_offer_nodes(res["data"]):
                c = compact_offer(node)
                if c:
                    candidates.append(c)
            # A valid broad response is enough; avoid redundant calls.
            if candidates:
                break
        if candidates:
            break

    dedup = {}
    for c in candidates:
        key = c["id"] or json.dumps(c.get("title"), ensure_ascii=False, sort_keys=True)
        dedup[key] = c
    candidates = list(dedup.values())
    dynamic = [c for c in candidates if c["dynamicHint"] and not c["staticHint"]]

    out = {
        "schemaVersion": 1,
        "dataset": "germany-mobilithek-dynamic-discovery",
        "generatedAt": now(),
        "stagedOnly": True,
        "attempts": attempts,
        "candidates": candidates,
        "dynamicCandidates": dynamic,
    }
    path = Path("data/germany/mobilithek_dynamic_discovery.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_MOBILITHEK_DISCOVERY=" + json.dumps({
        "candidates": len(candidates), "dynamicCandidates": len(dynamic),
        "providers": sorted({c.get("provider") for c in dynamic if c.get("provider")}),
    }, sort_keys=True))
    for c in dynamic:
        print("TCC_MOBILITHEK_DYNAMIC=" + json.dumps({
            "id": c.get("id"), "title": c.get("title"), "provider": c.get("provider")
        }, ensure_ascii=False, sort_keys=True))
    if not any(a.get("ok") for a in attempts):
        raise SystemExit("Mobilithek offers/search API did not accept any discovery request")


if __name__ == "__main__":
    main()
