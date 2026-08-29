#!/usr/bin/env python3
"""Inspect the public NextCharge map frontend for station-data endpoint hints.

No account or privileged API is used. The probe loads the public map, enumerates
its script sources, downloads only public JS assets from nextcharge.app or its
known CDN, and records API/host/path-like strings. It never calls discovered
endpoints.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
OUT = Path("data/reports/ges_nextcharge_frontend_source_probe.json")
ALLOWED_HOSTS = {"nextcharge.app", "nextchargeapp-542e.kxcdn.com"}
MAX_JS_BYTES = 8_000_000

HOST_RE = re.compile(r"(?:(?:https?:)?//)?([a-z0-9][a-z0-9.-]{2,}\.[a-z]{2,})(?=[:/'\"`]|$)", re.I)
URL_RE = re.compile(r"https?://[^\s\"'`<>\\]{4,300}", re.I)
PATH_RE = re.compile(r"[\"'`](/{1,2}[A-Za-z0-9_./?=&%:+-]{3,250})[\"'`]", re.I)
API_WORD_RE = re.compile(r"(api|station|chargepoint|connector|marker|cluster|location|poi|evse|tariff|price|mapbounds|bounding|viewport|latitude|longitude)", re.I)
BLOCKED_WORD_RE = re.compile(r"(userauth|login|signup|register|payment|wallet|transaction|startcharge|stopcharge|recharge)", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed(url: str) -> bool:
    try:
        return (urlparse(url).hostname or "").lower() in ALLOWED_HOSTS
    except Exception:
        return False


def normalize_fragment(value: str) -> str:
    value = value.strip()
    # Strip long query values; endpoint discovery only needs key names/path.
    if "?" in value:
        path, query = value.split("?", 1)
        keys = []
        for part in query.split("&")[:30]:
            key = part.split("=", 1)[0].strip()
            if key:
                keys.append(key[:80])
        return path + ("?" + "&".join(keys) if keys else "")
    return value[:300]


def extract_hints(text: str):
    hosts = Counter()
    urls = set()
    paths = set()
    api_snippets = set()

    for match in HOST_RE.finditer(text):
        host = match.group(1).lower()
        if len(host) <= 180:
            hosts[host] += 1

    for match in URL_RE.finditer(text):
        raw = match.group(0)
        if API_WORD_RE.search(raw) and not BLOCKED_WORD_RE.search(raw):
            urls.add(normalize_fragment(raw))

    for match in PATH_RE.finditer(text):
        raw = match.group(1)
        if API_WORD_RE.search(raw) and not BLOCKED_WORD_RE.search(raw):
            paths.add(normalize_fragment(raw))

    # Context snippets around strong endpoint words; keep short and sanitized.
    for m in API_WORD_RE.finditer(text):
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 180)
        frag = text[start:end].replace("\n", " ").replace("\r", " ")
        if BLOCKED_WORD_RE.search(frag):
            continue
        if any(ch in frag for ch in ("/", "http", ".com", ".app")):
            api_snippets.add(frag[:320])
        if len(api_snippets) >= 300:
            break

    return {
        "hosts": dict(hosts.most_common(100)),
        "apiLikeUrls": sorted(urls)[:300],
        "apiLikePaths": sorted(paths)[:300],
        "apiContextSnippets": sorted(api_snippets)[:300],
    }


def main():
    opts = Options()
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1600", "--lang=it-IT"):
        opts.add_argument(arg)
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(MAP_URL)
        time.sleep(8)
        page_url = driver.current_url
        title = driver.title
        body_text = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
        scripts = driver.execute_script("return Array.from(document.scripts).map(s => s.src).filter(Boolean)") or []
        links = driver.execute_script("return Array.from(document.querySelectorAll('link[href]')).map(x=>x.href)") or []
        inline_scripts = driver.execute_script("return Array.from(document.scripts).filter(s=>!s.src).map(s=>s.textContent || '')") or []
        ready_state = driver.execute_script("return document.readyState")
    finally:
        driver.quit()

    script_urls = []
    for src in scripts:
        full = urljoin(page_url, str(src))
        if allowed(full) and full not in script_urls:
            script_urls.append(full)

    session = requests.Session()
    session.headers["User-Agent"] = "tesla-charge-companion-data-lab/ges-nextcharge-public-source-probe"
    asset_reports = []
    combined_hosts = Counter()
    combined_urls = set()
    combined_paths = set()

    inline_text = "\n".join(str(x) for x in inline_scripts if x)
    inline_hints = extract_hints(inline_text)
    combined_hosts.update(inline_hints["hosts"])
    combined_urls.update(inline_hints["apiLikeUrls"])
    combined_paths.update(inline_hints["apiLikePaths"])

    for url in script_urls:
        try:
            r = session.get(url, timeout=30)
            content = r.content
            if len(content) > MAX_JS_BYTES:
                asset_reports.append({"url": url, "status": r.status_code, "bytes": len(content), "skipped": "too_large"})
                continue
            text = content.decode("utf-8", errors="replace")
            hints = extract_hints(text)
            combined_hosts.update(hints["hosts"])
            combined_urls.update(hints["apiLikeUrls"])
            combined_paths.update(hints["apiLikePaths"])
            asset_reports.append({
                "url": url,
                "status": r.status_code,
                "bytes": len(content),
                "hints": hints,
            })
        except Exception as exc:
            asset_reports.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

    payload = {
        "generatedAt": now_iso(),
        "mapUrl": MAP_URL,
        "finalPageUrl": page_url,
        "pageTitle": title,
        "readyState": ready_state,
        "bodyTextPrefix": body_text[:4000],
        "scriptCount": len(scripts),
        "allowedScriptCount": len(script_urls),
        "scriptUrls": script_urls,
        "linkHosts": dict(Counter((urlparse(str(x)).hostname or "unknown").lower() for x in links).most_common()),
        "inlineHints": inline_hints,
        "combined": {
            "hosts": dict(combined_hosts.most_common(150)),
            "apiLikeUrls": sorted(combined_urls)[:500],
            "apiLikePaths": sorted(combined_paths)[:500],
        },
        "assets": asset_reports,
        "security": {
            "accountCredentialsUsed": False,
            "discoveredEndpointsCalled": False,
            "authPaymentChargeEndpointsCalled": False,
            "cookiesPersisted": False,
            "requestHeadersPersisted": False,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pageTitle": payload["pageTitle"],
        "readyState": payload["readyState"],
        "bodyTextPrefix": payload["bodyTextPrefix"],
        "scriptCount": payload["scriptCount"],
        "allowedScriptCount": payload["allowedScriptCount"],
        "scriptUrls": payload["scriptUrls"],
        "combined": payload["combined"],
        "assetSummaries": [{"url": a.get("url"), "status": a.get("status"), "bytes": a.get("bytes"), "apiLikeUrls": (a.get("hints") or {}).get("apiLikeUrls"), "apiLikePaths": (a.get("hints") or {}).get("apiLikePaths")} for a in asset_reports],
    }, ensure_ascii=False, indent=2)[:100000])


if __name__ == "__main__":
    main()
