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
            if ("offerid" in keys or "id" in keys or "publicationid" in keys) and (
                "title" in keys or "name" in keys
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
    raw_blob = json.dumps(x, ensure_ascii=False).lower()
    title_value = x.get("title") or x.get("name") or x.get("dataName") or x.get("publicationName") or ""
    title = json.dumps(title_value, ensure_ascii=False).lower() if not isinstance(title_value, str) else title_value.lower()
    if "afir" not in raw_blob or "recharg" not in raw_blob:
        return None
    provider = next((t for t in TARGETS if t in raw_blob), None)
    if not provider:
        return None
    dynamic = "-dyn-" in title or " dynamic" in title or "dynamisch" in title
    static = "-stat-" in title or " static" in title or "statisch" in title
    return {
        "id": str(x.get("offerId") or x.get("publicationId") or x.get("id") or ""),
        "title": title_value,
        "provider": provider,
        "dynamicHint": dynamic,
        "staticHint": static,
        "raw": x,
    }


def page_shape(obj):
    if not isinstance(obj, dict):
        return {"type": type(obj).__name__}
    out = {"keys": sorted(obj.keys())[:30]}
    for key in ("totalElements", "totalPages", "number", "size", "numberOfElements", "page", "total"):
        if key in obj:
            out[key] = obj[key]
    for key in ("content", "items", "results", "offers"):
        if isinstance(obj.get(key), list):
            out[key + "Count"] = len(obj[key])
    return out


def main():
    attempts = []
    candidates = []
    # Empty JSON is accepted by the current public API. Walk the current newest
    # pages so duplicate GovData records do not hide the actual offer IDs.
    successful_pages = 0
    empty_streak = 0
    for page in range(0, 80):
        url = BASE + f"?page={page}&size=100"
        res = request(url, {})
        attempts.append({
            "url": url, "payload": {}, "ok": res.get("ok"), "status": res.get("status"),
            "error": res.get("error"), "shape": page_shape(res.get("data")) if res.get("ok") else None,
        })
        if not res.get("ok"):
            if page == 0:
                break
            continue
        successful_pages += 1
        nodes = flatten_offer_nodes(res["data"])
        if not nodes:
            empty_streak += 1
        else:
            empty_streak = 0
        for node in nodes:
            c = compact_offer(node)
            if c:
                candidates.append(c)
        # Stop once both known dynamic providers are found and Qwello has either
        # appeared anywhere or we have scanned a meaningful window around them.
        dyn_providers = {c["provider"] for c in candidates if c["dynamicHint"] and not c["staticHint"]}
        qwello_seen = any(c["provider"] == "qwello" for c in candidates)
        if {"chargecloud", "eround"}.issubset(dyn_providers) and (qwello_seen or page >= 15):
            break
        if empty_streak >= 3:
            break

    dedup = {}
    for c in candidates:
        key = c["id"] or json.dumps(c.get("title"), ensure_ascii=False, sort_keys=True)
        dedup[key] = c
    candidates = list(dedup.values())
    dynamic = [c for c in candidates if c["dynamicHint"] and not c["staticHint"]]

    out = {
        "schemaVersion": 2,
        "dataset": "germany-mobilithek-dynamic-discovery",
        "generatedAt": now(),
        "stagedOnly": True,
        "successfulPages": successful_pages,
        "attempts": attempts,
        "candidates": candidates,
        "dynamicCandidates": dynamic,
    }
    path = Path("data/germany/mobilithek_dynamic_discovery.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_MOBILITHEK_DISCOVERY=" + json.dumps({
        "successfulPages": successful_pages,
        "candidates": len(candidates), "dynamicCandidates": len(dynamic),
        "providers": sorted({c.get("provider") for c in dynamic if c.get("provider")}),
    }, sort_keys=True))
    for c in dynamic:
        print("TCC_MOBILITHEK_DYNAMIC=" + json.dumps({
            "id": c.get("id"), "title": c.get("title"), "provider": c.get("provider")
        }, ensure_ascii=False, sort_keys=True))
    if successful_pages == 0:
        raise SystemExit("Mobilithek offers/search API did not accept discovery request")
    if not {"chargecloud", "eround"}.issubset({c.get("provider") for c in dynamic}):
        raise SystemExit("current chargecloud/eRound dynamic offers not both discovered")


if __name__ == "__main__":
    main()
