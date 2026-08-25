#!/usr/bin/env python3
"""Probe the public e-Totem charging portal for discoverable station/tariff APIs.

This does not authenticate or bypass access controls. It only fetches the public SPA
HTML/JavaScript and records URL/endpoint strings that the public client itself ships.
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


def get(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read(), r.geturl()


def text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", "replace")


def uniq(seq):
    seen = set(); out=[]
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def main() -> int:
    raw, final_url = get(ROOT)
    html = text(raw)
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, flags=re.I)
    link_hrefs = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html, flags=re.I)
    scripts = []
    for src in script_srcs:
        url = urllib.parse.urljoin(final_url, src)
        try:
            body, fetched = get(url)
            js = text(body)
        except Exception as exc:
            scripts.append({"url": url, "error": str(exc)})
            continue

        absolute_urls = uniq(re.findall(r'https?://[^"\'`\\\s)]+', js))
        path_candidates = uniq(re.findall(r'["\']([^"\']*(?:api|station|charge|evse|tarif|price|connector|location)[^"\']*)["\']', js, flags=re.I))
        graphql = uniq(re.findall(r'[^"\']{0,80}graphql[^"\']{0,120}', js, flags=re.I))
        keyword_contexts = []
        for kw in ("tarif", "price", "station", "evse", "chargepoint", "connector", "ocpi", "api"):
            for m in re.finditer(kw, js, flags=re.I):
                s=max(0,m.start()-100); e=min(len(js),m.end()+180)
                snippet=re.sub(r'\s+',' ',js[s:e])
                if snippet not in keyword_contexts:
                    keyword_contexts.append(snippet)
                if len(keyword_contexts) >= 120:
                    break
            if len(keyword_contexts) >= 120:
                break
        scripts.append({
            "url": fetched,
            "size": len(body),
            "absoluteUrls": absolute_urls[:200],
            "pathCandidates": path_candidates[:400],
            "graphqlContexts": graphql[:50],
            "keywordContexts": keyword_contexts[:120],
        })

    payload = {
        "root": ROOT,
        "finalUrl": final_url,
        "htmlSize": len(raw),
        "scriptSrcs": script_srcs,
        "linkHrefs": link_hrefs,
        "scripts": scripts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "htmlSize": len(raw),
        "scriptCount": len(script_srcs),
        "scripts": [{"url": s.get("url"), "size": s.get("size"), "urls": len(s.get("absoluteUrls", [])), "paths": len(s.get("pathCandidates", []))} for s in scripts]
    }, ensure_ascii=False, indent=2))
    for s in scripts:
        for u in s.get("absoluteUrls", []):
            lu=u.lower()
            if any(k in lu for k in ("api", "station", "charge", "evse", "ocpi", "totem")):
                print("URL", u)
        for p in s.get("pathCandidates", [])[:80]:
            print("PATH", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
