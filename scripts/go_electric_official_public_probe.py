#!/usr/bin/env python3
"""Read-only discovery of public Go Electric Stations web tariff sources.

Purpose: determine whether the physical CPO exposes station/EVSE-specific or
network tariff information that can independently attribute prices to
`Go Electric Stations SRLS`. This probe never authenticates and never calls a
discovered API. It only performs GET requests against the public official web
origin and same-origin static/page resources.

The target EVSE sample is the exact Spoltore match already validated against PUN.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOTS = (
    "https://goelectricstations.com/",
    "https://www.goelectricstations.com/",
)
ALLOWED_HOSTS = {"goelectricstations.com", "www.goelectricstations.com"}
USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
MAX_BYTES = 6_000_000
MAX_PAGES = 12
MAX_ASSETS = 30
TERMS = (
    "tariff", "tariffe", "tariffa", "price", "prezzo", "prezzi", "ricarica",
    "charging", "station", "colonn", "evse", "connector", "api", "app",
    "roaming", "kwh", "€/kwh", "eur/kwh", "payment", "pagamento",
)
TARGET_EVSES = (
    "ITGESE812715456", "ITGESE812715457", "ITGESE812715458",
    "812715456", "812715457", "812715458",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() in ALLOWED_HOSTS


def normalize(base: str, value: str) -> str | None:
    url = urllib.parse.urljoin(base, value)
    return url if allowed(url) else None


def get_text(url: str) -> tuple[str, dict[str, str]]:
    if not allowed(url):
        raise RuntimeError(f"URL outside official allowlist: {url}")
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.5",
    })
    with urllib.request.urlopen(req, timeout=35) as resp:
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise RuntimeError(f"response too large: {url}")
        charset = resp.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace"), {
            "status": str(getattr(resp, "status", "")),
            "contentType": str(resp.headers.get("Content-Type") or ""),
            "finalUrl": str(resp.geturl()),
        }


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.assets: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = {k: v for k, v in attrs if v}
        if tag.lower() == "a" and d.get("href"):
            self.links.append(d["href"])
        if tag.lower() in {"script", "link"}:
            value = d.get("src") or d.get("href")
            if value:
                self.assets.append(value)


def score_url(url: str) -> int:
    low = url.lower()
    return sum(3 if t in {"tariffe", "tariffa", "prezzi", "ricarica"} else 1 for t in TERMS if t in low)


def extract_evidence(text: str) -> dict:
    low = text.lower()
    target_hits = [x for x in TARGET_EVSES if x.lower() in low]
    term_counts = {t: low.count(t) for t in TERMS if t in low}
    urls = sorted(set(re.findall(r"https://[^\s\"'<>]+", text)))
    candidates = [u[:800] for u in urls if any(t in u.lower() for t in TERMS)]
    snippets: list[dict[str, str]] = []
    for term in ("tariffe", "tariffa", "prezzo", "prezzi", "kwh", "api", "evse", "connector"):
        pos = low.find(term)
        if pos >= 0:
            snippets.append({"term": term, "text": text[max(0,pos-350):min(len(text),pos+900)]})
    return {
        "targetEvseHits": target_hits,
        "termCounts": term_counts,
        "candidateUrls": candidates[:200],
        "snippets": snippets[:30],
    }


def main() -> None:
    root_text = None
    root_url = None
    root_headers = None
    root_errors: list[str] = []
    for candidate in ROOTS:
        try:
            text, headers = get_text(candidate)
            final = headers.get("finalUrl") or candidate
            if allowed(final):
                root_text, root_url, root_headers = text, final, headers
                break
        except Exception as exc:
            root_errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
    if root_text is None or root_url is None:
        raise SystemExit("official Go Electric root unavailable: " + " | ".join(root_errors))

    queue: list[str] = [root_url]
    seen: set[str] = set()
    pages: list[dict] = []
    assets: list[dict] = []
    asset_urls: set[str] = set()

    while queue and len(pages) < MAX_PAGES:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            text, headers = (root_text, root_headers) if url == root_url else get_text(url)
            assert headers is not None
            ev = extract_evidence(text)
            pages.append({"url": url, "headers": headers, "bytesDecoded": len(text.encode("utf-8")), **ev})
            parser = Parser()
            parser.feed(text)
            ranked: list[tuple[int,str]] = []
            for href in parser.links:
                link = normalize(url, href)
                if link and link not in seen:
                    ranked.append((score_url(link), link))
            for _, link in sorted(ranked, key=lambda x: (-x[0], x[1])):
                if link not in queue and (score_url(link) > 0 or len(pages) < 3):
                    queue.append(link)
            for src in parser.assets:
                asset = normalize(url, src)
                if asset:
                    asset_urls.add(asset)
        except Exception as exc:
            pages.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

    for url in sorted(asset_urls)[:MAX_ASSETS]:
        try:
            text, headers = get_text(url)
            assets.append({"url": url, "headers": headers, "bytesDecoded": len(text.encode("utf-8")), **extract_evidence(text)})
        except Exception as exc:
            assets.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

    all_items = pages + assets
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "scope": "official Go Electric Stations public web source discovery",
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "getOnly": True,
            "discoveredApiCallsExecuted": False,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "allowedHosts": sorted(ALLOWED_HOSTS),
            "publicationAllowed": False,
        },
        "rootUrl": root_url,
        "rootErrors": root_errors,
        "pageCount": len(pages),
        "assetCount": len(assets),
        "targetEvseHits": sorted(set(x for item in all_items for x in item.get("targetEvseHits", []))),
        "pages": pages,
        "assets": assets,
    }
    out = Path("artifacts/go_electric_official_public_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rootUrl": root_url,
        "pages": len(pages),
        "assets": len(assets),
        "targetEvseHits": report["targetEvseHits"],
        "pagesWithTariffTerms": sum(1 for x in pages if any(k.startswith("tariff") or k in {"prezzi","prezzo","kwh"} for k in x.get("termCounts",{}))),
        "assetsWithApiTerms": sum(1 for x in assets if x.get("termCounts",{}).get("api",0) > 0),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
