#!/usr/bin/env python3
"""Read-only discovery probe for the public NextCharge web map.

Purpose: identify public map/API endpoint candidates needed to validate exact
connector tariffs for PUN CPO `Go Electric Stations SRLS` without guessing a
national tariff. The probe performs GET requests only against nextcharge.app,
does not authenticate, start sessions, or mutate any remote state.
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
ALLOWED_HOSTS = {"nextcharge.app", "www.nextcharge.app"}
MAX_ASSET_BYTES = 3_000_000
MAX_SCRIPTS = 30


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


def safe_url(base: str, candidate: str) -> str | None:
    url = urllib.parse.urljoin(base, candidate)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        return None
    return url


def get_text(url: str) -> tuple[str, dict[str, str]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = resp.read(MAX_ASSET_BYTES + 1)
        if len(data) > MAX_ASSET_BYTES:
            raise RuntimeError(f"asset too large: {url}")
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
            url = safe_url(base_url, match.group(1))
            if url:
                found.add(url)
    return found


def endpoint_candidates(text: str, base_url: str) -> set[str]:
    candidates: set[str] = set()
    patterns = [
        r"https://(?:www\.)?nextcharge\.app/[A-Za-z0-9_./?=&%:+,-]+",
        r"[\"']([^\"']*(?:/apis?/|/api/)[^\"']*)[\"']",
        r"[\"']([^\"']*(?:station|connector|tariff|price|chargepoint|evse)[^\"']{0,160})[\"']",
    ]
    for idx, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw = match.group(0 if idx == 0 else 1).strip("\"'")
            if len(raw) > 300 or any(x in raw.lower() for x in ("data:image", "node_modules", "sourcemappingurl")):
                continue
            if idx == 2 and not any(token in raw.lower() for token in ("api", "ajax", "json", "station", "connector", "tariff", "price", "evse")):
                continue
            url = safe_url(base_url, raw)
            if url:
                candidates.add(url)
    return candidates


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://nextcharge.app/map?nextcharge=only")
    ap.add_argument("--out", default="data/reports/go_electric_nextcharge_public_probe.json")
    args = ap.parse_args()

    root_url = safe_url(args.url, args.url)
    if not root_url:
        raise SystemExit("root URL must be HTTPS on nextcharge.app")

    html, root_headers = get_text(root_url)
    parser = ResourceParser()
    parser.feed(html)

    discovered_resources: list[dict[str, str]] = []
    for item in parser.resources:
        url = safe_url(root_url, item["value"])
        if not url:
            continue
        row = {**item, "url": url}
        if row not in discovered_resources:
            discovered_resources.append(row)

    script_urls: list[str] = []
    for src in list(parser.scripts) + sorted(javascript_assets(html, root_url)):
        url = safe_url(root_url, src)
        if url and url not in script_urls:
            script_urls.append(url)
        if len(script_urls) >= MAX_SCRIPTS:
            break

    candidates = endpoint_candidates(html, root_url)
    candidates.update(item["url"] for item in discovered_resources if any(k in item["url"].lower() for k in ("api", "station", "connector", "tariff", "price", "evse")))

    assets: list[dict[str, object]] = []
    nested_js: set[str] = set()
    for script_url in script_urls:
        item: dict[str, object] = {"url": script_url}
        try:
            text, headers = get_text(script_url)
            found = sorted(endpoint_candidates(text, script_url))
            nested = sorted(javascript_assets(text, script_url))
            item.update({
                "bytesDecoded": len(text.encode("utf-8")),
                "headers": headers,
                "candidateCount": len(found),
                "candidates": found,
                "nestedJavascript": nested[:100],
            })
            candidates.update(found)
            nested_js.update(nested)
        except Exception as exc:  # diagnostic only; keep other assets inspectable
            item["error"] = f"{type(exc).__name__}: {exc}"
        assets.append(item)

    compact_prefix = re.sub(r"\s+", " ", html[:5000]).strip()
    compact_suffix = re.sub(r"\s+", " ", html[-5000:]).strip()
    report = {
        "schemaVersion": 3,
        "generatedAt": now_iso(),
        "scope": "public NextCharge web map endpoint discovery",
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "allowedHosts": sorted(ALLOWED_HOSTS),
        },
        "rootUrl": root_url,
        "rootHeaders": root_headers,
        "rootHtmlLength": len(html.encode("utf-8")),
        "rootHtmlPrefix": compact_prefix,
        "rootHtmlSuffix": compact_suffix,
        "resourceCount": len(discovered_resources),
        "resources": discovered_resources[:200],
        "scriptCount": len(script_urls),
        "scriptUrls": script_urls,
        "nestedJavascript": sorted(nested_js)[:200],
        "candidateCount": len(candidates),
        "candidates": sorted(candidates),
        "assets": assets,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rootHtmlLength": report["rootHtmlLength"],
        "resourceCount": report["resourceCount"],
        "scriptCount": report["scriptCount"],
        "candidateCount": report["candidateCount"],
    }, indent=2))
    for url in report["candidates"][:80]:
        print(url)


if __name__ == "__main__":
    main()
