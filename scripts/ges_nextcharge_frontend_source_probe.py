#!/usr/bin/env python3
"""Inspect public NextCharge frontend assets for station-data endpoint hints.

Research-only and fail-closed: no account/login/payment/charging endpoints are
called. Public HTML/JS assets are fetched directly first; Selenium is only a
best-effort fallback and can never prevent report creation.
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
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
OUT = Path("data/reports/ges_nextcharge_frontend_source_probe.json")
ALLOWED_HOSTS = {"nextcharge.app", "nextchargeapp-542e.kxcdn.com"}
MAX_JS_BYTES = 12_000_000

HOST_RE = re.compile(r"(?:(?:https?:)?//)?([a-z0-9][a-z0-9.-]{2,}\.[a-z]{2,})(?=[:/'\"`]|$)", re.I)
URL_RE = re.compile(r"https?://[^\s\"'`<>\\]{4,300}", re.I)
PATH_RE = re.compile(r"[\"'`](/{1,2}[A-Za-z0-9_./?=&%:+-]{3,250})[\"'`]", re.I)
SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.I)
LINK_HREF_RE = re.compile(r"<link[^>]+href=[\"']([^\"']+)[\"']", re.I)
INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]+src=)[^>]*>(.*?)</script>", re.I | re.S)
API_WORD_RE = re.compile(r"(api|station|chargepoint|connector|marker|cluster|location|poi|evse|tariff|price|mapbounds|bounding|viewport|latitude|longitude)", re.I)
BLOCKED_WORD_RE = re.compile(r"(userauth|login|signup|register|payment|wallet|transaction|startcharge|stopcharge|recharge)", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed(url: str) -> bool:
    try:
        return (urlparse(url).hostname or "").lower() in ALLOWED_HOSTS
    except Exception:
        return False


def normalize_fragment(value: str) -> str:
    value = value.strip()
    if "?" in value:
        path, query = value.split("?", 1)
        keys = []
        for part in query.split("&")[:30]:
            key = part.split("=", 1)[0].strip()
            if key:
                keys.append(key[:80])
        return path + ("?" + "&".join(keys) if keys else "")
    return value[:300]


def extract_hints(text: str) -> dict:
    hosts = Counter()
    urls, paths, snippets = set(), set(), set()
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
    for m in API_WORD_RE.finditer(text):
        start, end = max(0, m.start() - 140), min(len(text), m.end() + 220)
        frag = text[start:end].replace("\n", " ").replace("\r", " ")
        if BLOCKED_WORD_RE.search(frag):
            continue
        if any(x in frag for x in ("/", "http", ".com", ".app")):
            snippets.add(frag[:380])
        if len(snippets) >= 500:
            break
    return {
        "hosts": dict(hosts.most_common(150)),
        "apiLikeUrls": sorted(urls)[:500],
        "apiLikePaths": sorted(paths)[:500],
        "apiContextSnippets": sorted(snippets)[:500],
    }


def add_unique(target: list[str], values, base: str) -> None:
    for value in values:
        full = urljoin(base, str(value))
        if allowed(full) and full not in target:
            target.append(full)


def main() -> None:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
    })

    fetch_errors: list[str] = []
    browser_errors: list[str] = []
    html = ""
    final_url = MAP_URL
    title = ""
    ready_state = None
    body_text = ""
    script_urls: list[str] = []
    link_urls: list[str] = []
    inline_scripts: list[str] = []

    # Primary path: direct public HTML. This avoids waiting for map renderers.
    try:
        r = session.get(MAP_URL, timeout=30, allow_redirects=True)
        r.raise_for_status()
        html = r.text
        final_url = r.url
        add_unique(script_urls, SCRIPT_SRC_RE.findall(html), final_url)
        add_unique(link_urls, LINK_HREF_RE.findall(html), final_url)
        inline_scripts.extend(INLINE_SCRIPT_RE.findall(html))
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()[:300]
    except Exception as exc:
        fetch_errors.append(f"html:{type(exc).__name__}:{exc}")

    # Best-effort browser fallback/enrichment. A renderer timeout is non-fatal.
    if not script_urls or not html:
        opts = Options()
        opts.page_load_strategy = "eager"
        for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1600", "--lang=it-IT"):
            opts.add_argument(arg)
        driver = None
        try:
            driver = webdriver.Chrome(options=opts)
            driver.set_page_load_timeout(30)
            try:
                driver.get(MAP_URL)
            except TimeoutException as exc:
                browser_errors.append(f"page_load_timeout:{type(exc).__name__}")
                try:
                    driver.execute_script("window.stop()")
                except Exception:
                    pass
            time.sleep(3)
            final_url = driver.current_url or final_url
            title = driver.title or title
            ready_state = driver.execute_script("return document.readyState")
            body_text = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
            add_unique(script_urls, driver.execute_script("return Array.from(document.scripts).map(s=>s.src).filter(Boolean)") or [], final_url)
            add_unique(link_urls, driver.execute_script("return Array.from(document.querySelectorAll('link[href]')).map(x=>x.href)") or [], final_url)
            inline_scripts.extend(driver.execute_script("return Array.from(document.scripts).filter(s=>!s.src).map(s=>s.textContent||'')") or [])
            if not html:
                html = driver.page_source or ""
        except Exception as exc:
            browser_errors.append(f"browser:{type(exc).__name__}:{exc}")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    html_hints = extract_hints(html)
    inline_hints = extract_hints("\n".join(x for x in inline_scripts if x))
    combined_hosts = Counter(html_hints["hosts"])
    combined_hosts.update(inline_hints["hosts"])
    combined_urls = set(html_hints["apiLikeUrls"]) | set(inline_hints["apiLikeUrls"])
    combined_paths = set(html_hints["apiLikePaths"]) | set(inline_hints["apiLikePaths"])

    asset_reports = []
    for url in script_urls:
        try:
            res = session.get(url, timeout=30)
            size = len(res.content)
            row = {"url": url, "status": res.status_code, "bytes": size}
            if size <= MAX_JS_BYTES and res.status_code == 200:
                text = res.content.decode("utf-8", errors="replace")
                hints = extract_hints(text)
                row["hints"] = hints
                combined_hosts.update(hints["hosts"])
                combined_urls.update(hints["apiLikeUrls"])
                combined_paths.update(hints["apiLikePaths"])
            elif size > MAX_JS_BYTES:
                row["skipped"] = "too_large"
            asset_reports.append(row)
        except Exception as exc:
            asset_reports.append({"url": url, "error": f"{type(exc).__name__}:{exc}"})

    payload = {
        "generatedAt": now_iso(),
        "mapUrl": MAP_URL,
        "finalPageUrl": final_url,
        "pageTitle": title,
        "readyState": ready_state,
        "bodyTextPrefix": body_text[:4000],
        "directHtmlBytes": len(html.encode("utf-8", errors="ignore")),
        "scriptCount": len(script_urls),
        "scriptUrls": script_urls,
        "linkHosts": dict(Counter((urlparse(x).hostname or "unknown").lower() for x in link_urls).most_common()),
        "htmlHints": html_hints,
        "inlineHints": inline_hints,
        "combined": {
            "hosts": dict(combined_hosts.most_common(200)),
            "apiLikeUrls": sorted(combined_urls)[:800],
            "apiLikePaths": sorted(combined_paths)[:800],
        },
        "assets": asset_reports,
        "diagnostics": {"fetchErrors": fetch_errors, "browserErrors": browser_errors},
        "security": {
            "accountCredentialsUsed": False,
            "discoveredEndpointsCalled": False,
            "authPaymentChargeEndpointsCalled": False,
            "cookiesPersisted": False,
            "requestHeadersPersisted": False,
            "responseHeadersPersisted": False,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pageTitle": title,
        "directHtmlBytes": payload["directHtmlBytes"],
        "scriptCount": len(script_urls),
        "scriptUrls": script_urls,
        "combined": payload["combined"],
        "diagnostics": payload["diagnostics"],
        "assetSummaries": [{
            "url": a.get("url"), "status": a.get("status"), "bytes": a.get("bytes"),
            "apiLikeUrls": (a.get("hints") or {}).get("apiLikeUrls"),
            "apiLikePaths": (a.get("hints") or {}).get("apiLikePaths"),
        } for a in asset_reports],
    }, ensure_ascii=False, indent=2)[:120000])


if __name__ == "__main__":
    main()
