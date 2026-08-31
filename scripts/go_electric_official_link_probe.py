#!/usr/bin/env python3
"""Extract official Go Electric public B2C/NextCharge link evidence without following it.

Reads only the validated canonical Go Electric `.it` site and same-origin static
Javascript assets. External links are recorded as evidence but never requested.
This is intended to decide whether NextCharge is the operator-authorized consumer
channel for Go Electric station tariffs.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = "https://www.goelectricstations.it/"
ALLOWED_HOSTS = {"goelectricstations.it", "www.goelectricstations.it"}
USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
MAX_BYTES = 7_000_000
MAX_ASSETS = 40
KEY_TERMS = ("b2c", "nextcharge", "href", "url", "terms", "privacy", "status")
TARGET_TERMS = ("b2c", "nextcharge")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def same_origin(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() in ALLOWED_HOSTS


def get_text(url: str) -> tuple[str, dict[str, str]]:
    if not same_origin(url):
        raise RuntimeError(f"outside official same-origin allowlist: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/javascript,*/*;q=0.5"})
    with urllib.request.urlopen(req, timeout=35) as resp:
        final = str(resp.geturl())
        if not same_origin(final):
            raise RuntimeError(f"redirect outside official same-origin allowlist: {url} -> {final}")
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise RuntimeError(f"response too large: {url}")
        charset = resp.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace"), {
            "status": int(getattr(resp, "status", 200)),
            "contentType": str(resp.headers.get("Content-Type") or ""),
            "finalUrl": final,
        }


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = {k: v for k, v in attrs if v}
        if tag.lower() == "script" and d.get("src"):
            self.assets.append(d["src"])
        if tag.lower() == "link" and d.get("href"):
            self.assets.append(d["href"])
        if tag.lower() == "a" and d.get("href"):
            self.links.append(d["href"])


def normalize_same_origin(base: str, value: str) -> str | None:
    url = urllib.parse.urljoin(base, value)
    return url if same_origin(url) else None


def external_candidate(base: str, value: str) -> str | None:
    value = value.strip()
    if value.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None
    url = urllib.parse.urljoin(base, value)
    p = urllib.parse.urlparse(url)
    if p.scheme not in {"http", "https"} or not p.hostname:
        return None
    return url


def contexts(text: str, terms=TARGET_TERMS) -> list[dict[str, str]]:
    low = text.lower()
    out: list[dict[str, str]] = []
    for term in terms:
        start = 0
        while len(out) < 120:
            pos = low.find(term, start)
            if pos < 0:
                break
            out.append({"term": term, "text": text[max(0, pos - 900):min(len(text), pos + 1800)]})
            start = pos + len(term)
    return out


def quoted_strings(text: str) -> list[str]:
    values: list[str] = []
    pattern = re.compile(r'''["']([^"'\\]{1,1000})["']''')
    for m in pattern.finditer(text):
        raw = m.group(1).strip()
        low = raw.lower()
        if any(t in low for t in KEY_TERMS) or raw.startswith(("http://", "https://", "/")):
            if raw not in values:
                values.append(raw)
        if len(values) >= 1500:
            break
    return values


def url_candidates(text: str, base: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    seen: set[str] = set()
    candidates = quoted_strings(text)
    candidates += re.findall(r"https?://[^\s\"'<>`]+", text)
    for raw in candidates:
        url = external_candidate(base, raw)
        if not url or url in seen:
            continue
        low = (raw + " " + url).lower()
        if not any(t in low for t in ("nextcharge", "b2c", "goelectric", "privacy", "terms", "status")):
            continue
        seen.add(url)
        p = urllib.parse.urlparse(url)
        out.append({
            "raw": raw[:1200],
            "resolvedUrl": url[:1600],
            "host": p.hostname,
            "sameOrigin": same_origin(url),
            "requested": False,
        })
    return out[:500]


def main() -> None:
    html, headers = get_text(ROOT)
    parser = AssetParser()
    parser.feed(html)

    sources: list[dict[str, object]] = []
    sources.append({
        "url": ROOT,
        "headers": headers,
        "kind": "html",
        "contexts": contexts(html),
        "quotedStrings": quoted_strings(html),
        "urlCandidates": url_candidates(html, ROOT),
    })

    assets: list[str] = []
    for raw in parser.assets:
        url = normalize_same_origin(ROOT, raw)
        if url and url not in assets and url.lower().split("?", 1)[0].endswith((".js", ".json")):
            assets.append(url)
        if len(assets) >= MAX_ASSETS:
            break

    for url in assets:
        try:
            text, h = get_text(url)
            low = text.lower()
            if not any(t in low for t in TARGET_TERMS):
                continue
            sources.append({
                "url": url,
                "headers": h,
                "kind": "asset",
                "bytesDecoded": len(text.encode("utf-8")),
                "contexts": contexts(text),
                "quotedStrings": quoted_strings(text),
                "urlCandidates": url_candidates(text, url),
            })
        except Exception as exc:
            sources.append({"url": url, "kind": "asset", "error": f"{type(exc).__name__}: {exc}"})

    all_candidates = []
    seen = set()
    for src in sources:
        for item in src.get("urlCandidates", []):
            key = item.get("resolvedUrl")
            if key and key not in seen:
                seen.add(key)
                all_candidates.append(item)

    nextcharge = [x for x in all_candidates if "nextcharge" in str(x.get("resolvedUrl", "")).lower() or "nextcharge" in str(x.get("raw", "")).lower()]
    b2c_context_count = sum(1 for src in sources for c in src.get("contexts", []) if c.get("term") == "b2c")
    nextcharge_context_count = sum(1 for src in sources for c in src.get("contexts", []) if c.get("term") == "nextcharge")

    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "scope": "official Go Electric B2C/NextCharge static link evidence",
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "getOnly": True,
            "sameOriginRequestsOnly": True,
            "externalLinksFollowed": False,
            "discoveredApiCallsExecuted": False,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "publicationAllowed": False,
            "allowedHosts": sorted(ALLOWED_HOSTS),
        },
        "root": ROOT,
        "assetCountFetched": len(assets),
        "sourceCountWithTargetTerms": len(sources),
        "b2cContextCount": b2c_context_count,
        "nextchargeContextCount": nextcharge_context_count,
        "nextchargeUrlCandidates": nextcharge,
        "allRelevantUrlCandidates": all_candidates,
        "sources": sources,
    }
    out = Path("artifacts/go_electric_official_link_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "assetsFetched": len(assets),
        "sourcesWithTargetTerms": len(sources),
        "b2cContexts": b2c_context_count,
        "nextchargeContexts": nextcharge_context_count,
        "nextchargeUrls": nextcharge,
    }, ensure_ascii=False, indent=2))
    if nextcharge_context_count == 0:
        raise SystemExit("no NextCharge context found in official canonical source")


if __name__ == "__main__":
    main()
