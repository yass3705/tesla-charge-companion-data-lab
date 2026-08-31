#!/usr/bin/env python3
"""Read-only discovery probe for the public NextCharge web map.

Purpose: identify public map/API endpoint candidates needed to validate exact
connector tariffs for PUN CPO `Go Electric Stations SRLS` without guessing a
national tariff. The probe performs GET requests only against the public
NextCharge web frontend and its static CDN. It does not authenticate, start
sessions, call discovered charging APIs, or mutate any remote state.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
FRONTEND_HOSTS = {"nextcharge.app", "www.nextcharge.app"}
STATIC_HOSTS = {"nextchargeapp-542e.kxcdn.com"}
FETCH_HOSTS = FRONTEND_HOSTS | STATIC_HOSTS
MAX_ASSET_BYTES = 8_000_000
MAX_SCRIPTS = 30
CONTEXT_TERMS = (
    "hostEndpoints=",
    "pathAPI=",
    "hostAPIstationsGrid",
    "hostAPImultimedia",
    "getSessionTokenForStations",
    "function getStations",
    "getTariffs(){",
    "tariffEMP",
)


class ResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []
        self.resources: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: v for k, v in attrs if v is not None}
        if tag.lower() == "script" and values.get("src"):
            self.scripts.append(values["src"])
        for attr in ("src", "href", "data-src", "data-url"):
            value = values.get(attr)
            if value:
                self.resources.append({"tag": tag.lower(), "attribute": attr, "value": value})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetchable_url(base: str, candidate: str) -> str | None:
    url = urllib.parse.urljoin(base, candidate)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in FETCH_HOSTS:
        return None
    return url


def recordable_url(base: str, candidate: str) -> str | None:
    url = urllib.parse.urljoin(base, candidate)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return url


def get_text(url: str) -> tuple[str, dict[str, str]]:
    checked = fetchable_url(url, url)
    if not checked:
        raise RuntimeError(f"host is not allowed for GET: {url}")
    req = urllib.request.Request(
        checked,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = resp.read(MAX_ASSET_BYTES + 1)
        if len(data) > MAX_ASSET_BYTES:
            raise RuntimeError(f"asset too large: {checked}")
        charset = resp.headers.get_content_charset() or "utf-8"
        headers = {
            "contentType": str(resp.headers.get("Content-Type") or ""),
            "server": str(resp.headers.get("Server") or ""),
            "cacheControl": str(resp.headers.get("Cache-Control") or ""),
            "contentEncoding": str(resp.headers.get("Content-Encoding") or ""),
        }
        return data.decode(charset, errors="replace"), headers


def javascript_assets(text: str, base_url: str) -> set[str]:
    found: set[str] = set()
    patterns = [
        r"(?:src|href)\s*=\s*[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']",
        r"[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            url = fetchable_url(base_url, match.group(1))
            if url:
                found.add(url)
    return found


def endpoint_candidates(text: str, base_url: str) -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    strings: set[str] = set()

    for match in re.finditer(r"https://[A-Za-z0-9._:-]+/[A-Za-z0-9_./?=&%:+,{}$@~-]+", text, flags=re.IGNORECASE):
        raw = match.group(0).strip("\"'")
        if len(raw) <= 500:
            url = recordable_url(base_url, raw)
            if url and any(token in raw.lower() for token in ("api", "station", "connector", "tariff", "price", "charge", "evse")):
                urls.add(url)

    quoted_pattern = r"[\"']([^\"']{1,400})[\"']"
    for match in re.finditer(quoted_pattern, text):
        raw = match.group(1)
        low = raw.lower()
        if not any(token in low for token in ("api", "ajax", "station", "connector", "tariff", "price", "chargepoint", "charging", "evse")):
            continue
        if any(token in low for token in ("data:image", "node_modules", "sourcemappingurl", "<svg", "font-family")):
            continue
        strings.add(raw)
        if raw.startswith(("http://", "https://", "/")):
            url = recordable_url(base_url, raw)
            if url:
                urls.add(url)

    return urls, strings


def interesting_contexts(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for term in CONTEXT_TERMS:
        snippets: list[str] = []
        start_at = 0
        while len(snippets) < 8:
            pos = text.find(term, start_at)
            if pos < 0:
                break
            left = max(0, pos - 1200)
            right = min(len(text), pos + len(term) + 1800)
            snippet = text[left:right]
            if snippet not in snippets:
                snippets.append(snippet)
            start_at = pos + len(term)
        if snippets:
            result[term] = snippets
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://nextcharge.app/map?nextcharge=only")
    ap.add_argument("--out", default="data/reports/go_electric_nextcharge_public_probe.json")
    args = ap.parse_args()

    root_url = fetchable_url(args.url, args.url)
    if not root_url or urllib.parse.urlparse(root_url).hostname not in FRONTEND_HOSTS:
        raise SystemExit("root URL must be HTTPS on nextcharge.app")

    html, root_headers = get_text(root_url)
    parser = ResourceParser()
    parser.feed(html)

    discovered_resources: list[dict[str, object]] = []
    for item in parser.resources:
        url = recordable_url(root_url, item["value"])
        if not url:
            continue
        row: dict[str, object] = {**item, "url": url, "fetchAllowed": fetchable_url(root_url, item["value"]) is not None}
        if row not in discovered_resources:
            discovered_resources.append(row)

    script_urls: list[str] = []
    for src in list(parser.scripts) + sorted(javascript_assets(html, root_url)):
        url = fetchable_url(root_url, src)
        if url and url not in script_urls:
            script_urls.append(url)
        if len(script_urls) >= MAX_SCRIPTS:
            break

    candidate_urls, candidate_strings = endpoint_candidates(html, root_url)
    assets: list[dict[str, object]] = []
    nested_js: set[str] = set()
    for script_url in script_urls:
        item: dict[str, object] = {"url": script_url}
        try:
            text, headers = get_text(script_url)
            urls, strings = endpoint_candidates(text, script_url)
            nested = sorted(javascript_assets(text, script_url))
            item.update({
                "bytesDecoded": len(text.encode("utf-8")),
                "headers": headers,
                "candidateUrlCount": len(urls),
                "candidateUrls": sorted(urls),
                "candidateStringCount": len(strings),
                "candidateStrings": sorted(strings)[:500],
                "interestingContexts": interesting_contexts(text),
                "nestedJavascript": nested[:100],
            })
            candidate_urls.update(urls)
            candidate_strings.update(strings)
            nested_js.update(nested)
        except Exception as exc:  # diagnostic only; keep other assets inspectable
            item["error"] = f"{type(exc).__name__}: {exc}"
        assets.append(item)

    report = {
        "schemaVersion": 5,
        "generatedAt": now_iso(),
        "scope": "public NextCharge web frontend/static-bundle endpoint discovery",
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "discoveredApiCallsExecuted": False,
            "fetchHosts": sorted(FETCH_HOSTS),
        },
        "rootUrl": root_url,
        "rootHeaders": root_headers,
        "rootHtmlLength": len(html.encode("utf-8")),
        "resourceCount": len(discovered_resources),
        "resources": discovered_resources[:200],
        "scriptCount": len(script_urls),
        "scriptUrls": script_urls,
        "nestedJavascript": sorted(nested_js)[:200],
        "candidateUrlCount": len(candidate_urls),
        "candidateUrls": sorted(candidate_urls),
        "candidateStringCount": len(candidate_strings),
        "candidateStrings": sorted(candidate_strings)[:1000],
        "assets": assets,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rootHtmlLength": report["rootHtmlLength"],
        "resourceCount": report["resourceCount"],
        "scriptCount": report["scriptCount"],
        "candidateUrlCount": report["candidateUrlCount"],
        "candidateStringCount": report["candidateStringCount"],
    }, indent=2))
    for url in report["candidateUrls"][:100]:
        print(url)


if __name__ == "__main__":
    main()
