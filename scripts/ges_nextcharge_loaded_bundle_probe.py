#!/usr/bin/env python3
"""Inspect JavaScript bundles actually loaded by the public NextCharge web map.

The browser is used only as a public asset loader. We persist no headers,
cookies, storage or auth material and never invoke discovered API endpoints.
Only sanitized endpoint/host/path hints and a strict allow-list of station API
configuration literals from already-loaded public JS are kept.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
OUT = Path("data/reports/ges_nextcharge_loaded_bundle_probe.json")
ALLOWED_HOSTS = {"nextcharge.app", "nextchargeapp-542e.kxcdn.com"}
MAX_BODY_CHARS = 15_000_000

URL_RE = re.compile(r"https?://[^\s\"'`<>\\]{4,400}", re.I)
PATH_RE = re.compile(r"[\"'`]((?:/{1,2}|\.\.?/)[A-Za-z0-9_./?=&%:+${}-]{3,320})[\"'`]", re.I)
HOST_RE = re.compile(r"(?:(?:https?:)?//)?([a-z0-9][a-z0-9.-]{2,}\.[a-z]{2,})(?=[:/'\"`]|$)", re.I)
STRONG_RE = re.compile(r"(station|chargepoint|connector|evse|tariff|price|marker|cluster|bounding|viewport|latitude|longitude|poi|map)", re.I)
BLOCKED_RE = re.compile(r"(userauth|login|signup|register|password|payment|wallet|transaction|startcharge|stopcharge|recharge|creditcard|token)", re.I)
TARGET_CONFIG_KEYS = (
    "stationsGrid",
    "station",
    "stationConnectors",
    "stationReviews",
    "stationPhotos",
    "getUserInfoFromGeoIP",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed_host(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in ALLOWED_HOSTS


def strip_query_values(value: str) -> str:
    value = value.strip()[:400]
    if "?" not in value:
        return value
    path, query = value.split("?", 1)
    keys = []
    for part in query.split("&")[:40]:
        key = part.split("=", 1)[0].strip()
        if key:
            keys.append(key[:80])
    return path + ("?" + "&".join(keys) if keys else "")


def extract_target_literals(text: str) -> dict[str, list[dict[str, str]]]:
    """Extract only literal values for a strict non-sensitive station API key set."""
    found: dict[str, list[dict[str, str]]] = defaultdict(list)
    for key in TARGET_CONFIG_KEYS:
        pattern = re.compile(rf'(?<![A-Za-z0-9_$]){re.escape(key)}\s*:\s*["\']([^"\']{{1,260}})["\']')
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            if not value or BLOCKED_RE.search(value):
                continue
            kind = "host" if value.startswith(("http://", "https://")) else "path"
            row = {"value": value[:260], "kind": kind}
            if row not in found[key]:
                found[key].append(row)
    return dict(found)


def hints(text: str) -> dict:
    hosts = Counter()
    urls, paths, contexts = set(), set(), set()
    for m in HOST_RE.finditer(text):
        h = m.group(1).lower()
        if len(h) <= 180:
            hosts[h] += 1
    for m in URL_RE.finditer(text):
        raw = m.group(0)
        if STRONG_RE.search(raw) and not BLOCKED_RE.search(raw):
            urls.add(strip_query_values(raw))
    for m in PATH_RE.finditer(text):
        raw = m.group(1)
        if STRONG_RE.search(raw) and not BLOCKED_RE.search(raw):
            paths.add(strip_query_values(raw))
    for m in STRONG_RE.finditer(text):
        s, e = max(0, m.start() - 180), min(len(text), m.end() + 280)
        frag = text[s:e].replace("\n", " ").replace("\r", " ")
        if BLOCKED_RE.search(frag):
            continue
        if "/" in frag or "http" in frag or ".com" in frag or ".app" in frag:
            contexts.add(frag[:480])
        if len(contexts) >= 700:
            break
    return {
        "hosts": dict(hosts.most_common(200)),
        "apiLikeUrls": sorted(urls)[:800],
        "apiLikePaths": sorted(paths)[:800],
        "contexts": sorted(contexts)[:700],
    }


def main() -> None:
    opts = Options()
    opts.page_load_strategy = "none"
    for arg in (
        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
        "--window-size=1440,1600", "--lang=it-IT", "--disable-geolocation",
    ):
        opts.add_argument(arg)
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=opts)
    responses: dict[str, dict] = {}
    browser_errors = []
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.set_page_load_timeout(20)
        try:
            driver.get(MAP_URL)
        except TimeoutException:
            browser_errors.append("page_load_timeout")
        for _ in range(8):
            time.sleep(3)
            for entry in driver.get_log("performance"):
                try:
                    msg = json.loads(entry["message"])["message"]
                    if msg.get("method") != "Network.responseReceived":
                        continue
                    p = msg.get("params") or {}
                    res = p.get("response") or {}
                    url = str(res.get("url") or "")
                    if not allowed_host(url):
                        continue
                    responses[str(p.get("requestId"))] = {
                        "url": url,
                        "host": (urlparse(url).hostname or "").lower(),
                        "path": urlparse(url).path,
                        "status": res.get("status"),
                        "mimeType": res.get("mimeType"),
                        "resourceType": p.get("type"),
                    }
                except Exception:
                    continue

        bundles = []
        combined_hosts = Counter()
        combined_urls, combined_paths = set(), set()
        aggregate_literals: dict[str, list[dict[str, str]]] = defaultdict(list)
        for rid, meta in responses.items():
            mime = str(meta.get("mimeType") or "").lower()
            rtype = str(meta.get("resourceType") or "")
            path = str(meta.get("path") or "")
            is_js = rtype == "Script" or "javascript" in mime or path.lower().endswith(".js")
            if not is_js:
                continue
            row = dict(meta)
            try:
                body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid})
                text = str(body.get("body") or "")
                row["bodyChars"] = len(text)
                row["base64Encoded"] = bool(body.get("base64Encoded"))
                if not row["base64Encoded"] and len(text) <= MAX_BODY_CHARS:
                    h = hints(text)
                    row["hints"] = h
                    literals = extract_target_literals(text)
                    row["targetConfigLiterals"] = literals
                    for key, values in literals.items():
                        for value in values:
                            if value not in aggregate_literals[key]:
                                aggregate_literals[key].append(value)
                    combined_hosts.update(h["hosts"])
                    combined_urls.update(h["apiLikeUrls"])
                    combined_paths.update(h["apiLikePaths"])
                else:
                    row["bodySkipped"] = "encoded_or_too_large"
            except Exception as exc:
                row["bodyReadError"] = type(exc).__name__
            bundles.append(row)

        payload = {
            "generatedAt": now_iso(),
            "mapUrl": MAP_URL,
            "security": {
                "accountCredentialsUsed": False,
                "loginOrRegistrationPerformed": False,
                "discoveredEndpointsCalled": False,
                "paymentWalletChargeEndpointsCalled": False,
                "requestHeadersPersisted": False,
                "responseHeadersPersisted": False,
                "cookiesPersisted": False,
                "browserStoragePersisted": False,
                "fullBundleBodiesPersisted": False,
            },
            "diagnostics": {"browserErrors": browser_errors},
            "counts": {
                "allowedResponses": len(responses),
                "loadedJavascriptBundles": len(bundles),
                "bundlesWithReadableBody": sum(1 for x in bundles if x.get("hints")),
            },
            "responsePaths": sorted({f"{x['host']}{x['path']}" for x in responses.values()}),
            "targetConfigLiterals": dict(aggregate_literals),
            "bundles": bundles,
            "combined": {
                "hosts": dict(combined_hosts.most_common(250)),
                "apiLikeUrls": sorted(combined_urls)[:1200],
                "apiLikePaths": sorted(combined_paths)[:1200],
            },
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "diagnostics": payload["diagnostics"],
            "counts": payload["counts"],
            "targetConfigLiterals": payload["targetConfigLiterals"],
            "combinedApiLikePaths": payload["combined"]["apiLikePaths"],
        }, ensure_ascii=False, indent=2)[:100000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
