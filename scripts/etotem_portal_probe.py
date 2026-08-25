#!/usr/bin/env python3
"""Probe the public e-Totem charging portal for discoverable station/tariff APIs.

No authentication or access-control bypass: this only reads assets publicly shipped
to browsers by the e-Totem Flutter Web portal and records likely endpoint strings.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = "https://www.e-totem.fr/"
OUT = Path("data/national/etotem_portal_probe.json")
UA = "Mozilla/5.0 TeslaChargeCompanionDataLab/1.0"
KEYWORDS = ("api", "station", "charge", "evse", "tarif", "price", "connector", "location", "ocpi", "borne", "pointdecharge")


def get(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.geturl(), r.headers.get("Content-Type", "")


def text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", "replace")


def uniq(seq):
    seen=set(); out=[]
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def inspect_asset(url: str) -> dict:
    try:
        body, fetched, ctype = get(url)
        js = text(body)
    except Exception as exc:
        return {"url": url, "error": str(exc)}

    absolute_urls = uniq(re.findall(r'https?://[^"\'`\\\s)]+', js))
    quoted = uniq(re.findall(r'["\']([^"\']{1,500})["\']', js))
    path_candidates = [q for q in quoted if any(k in q.lower() for k in KEYWORDS)]
    endpointish = []
    for q in quoted:
        lq=q.lower()
        if q.startswith("/") and any(k in lq for k in KEYWORDS):
            endpointish.append(q)
        elif ("/api/" in lq or "graphql" in lq or "ocpi" in lq) and len(q) < 300:
            endpointish.append(q)
    contexts=[]
    for kw in ("tarif", "price", "evse", "station", "chargepoint", "connector", "ocpi", "baseurl", "api"):
        for m in re.finditer(kw, js, flags=re.I):
            s=max(0,m.start()-140); e=min(len(js),m.end()+260)
            snippet=re.sub(r'\s+',' ',js[s:e])
            if snippet not in contexts:
                contexts.append(snippet)
            if len(contexts) >= 240:
                break
        if len(contexts) >= 240:
            break
    asset_refs = uniq(re.findall(r'["\']([^"\']+\.(?:js|json))(?:\?[^"\']*)?["\']', js, flags=re.I))
    return {
        "url": fetched,
        "contentType": ctype,
        "size": len(body),
        "absoluteUrls": absolute_urls[:500],
        "endpointCandidates": uniq(endpointish)[:600],
        "pathCandidates": path_candidates[:800],
        "assetRefs": asset_refs[:200],
        "keywordContexts": contexts[:240],
    }


def main() -> int:
    raw, final_url, _ = get(ROOT)
    html = text(raw)
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, flags=re.I)
    link_hrefs = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html, flags=re.I)
    inline_asset_refs = re.findall(r'["\']([^"\']+\.(?:js|json))(?:\?[^"\']*)?["\']', html, flags=re.I)

    # Flutter Web commonly loads these dynamically, so they are not always script tags.
    candidate_refs = uniq(script_srcs + inline_asset_refs + [
        "flutter_bootstrap.js", "main.dart.js", "version.json", "manifest.json"
    ])
    assets=[]
    visited=set()
    queue=[urllib.parse.urljoin(final_url, ref) for ref in candidate_refs]
    while queue and len(visited) < 25:
        url=queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        item=inspect_asset(url)
        assets.append(item)
        if item.get("error"):
            continue
        # Only follow small set of same-origin JS/JSON refs discovered in bootstrap files.
        for ref in item.get("assetRefs", []):
            nxt=urllib.parse.urljoin(item["url"], ref)
            if urllib.parse.urlparse(nxt).netloc == urllib.parse.urlparse(ROOT).netloc and nxt not in visited:
                queue.append(nxt)

    payload={
        "root": ROOT,
        "finalUrl": final_url,
        "htmlSize": len(raw),
        "scriptSrcs": script_srcs,
        "inlineAssetRefs": inline_asset_refs,
        "linkHrefs": link_hrefs,
        "assets": assets,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary={
        "htmlSize": len(raw),
        "assetCount": len(assets),
        "assets": [{"url":a.get("url"),"size":a.get("size"),"urls":len(a.get("absoluteUrls",[])),"endpoints":len(a.get("endpointCandidates",[])),"paths":len(a.get("pathCandidates",[])),"error":a.get("error")} for a in assets]
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for a in assets:
        print("ASSET", a.get("url"), "SIZE", a.get("size"), "ERROR", a.get("error"))
        for u in a.get("absoluteUrls", []):
            lu=u.lower()
            if any(k in lu for k in KEYWORDS):
                print("URL", u)
        for p in a.get("endpointCandidates", [])[:150]:
            print("ENDPOINT", p)
        for p in a.get("pathCandidates", [])[:150]:
            print("PATH", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
