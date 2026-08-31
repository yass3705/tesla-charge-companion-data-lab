#!/usr/bin/env python3
"""Extract official Go Electric B2C/NextCharge link evidence without following external links.

Reads only the validated canonical Go Electric `.it` site, including directly
addressed `/it` and `/en` pages plus same-origin Javascript assets. External
anchor destinations are recorded but never requested. This determines whether
NextCharge is the operator-authorized consumer channel for Go Electric tariffs.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

PAGES = (
    "https://www.goelectricstations.it/",
    "https://www.goelectricstations.it/it",
    "https://www.goelectricstations.it/en",
)
ALLOWED_HOSTS = {"goelectricstations.it", "www.goelectricstations.it"}
USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
MAX_BYTES = 7_000_000
MAX_ASSETS = 40
TARGET_TERMS = ("b2c", "nextcharge")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def same_origin(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() in ALLOWED_HOSTS


def get_text(url: str) -> tuple[str, dict[str, object]]:
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


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []
        self.anchors: list[dict[str, object]] = []
        self._anchor: dict[str, object] | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = {k: v for k, v in attrs if v}
        if tag.lower() == "script" and d.get("src"):
            self.assets.append(d["src"])
        if tag.lower() == "link" and d.get("href"):
            self.assets.append(d["href"])
        if tag.lower() == "a" and d.get("href"):
            self._anchor = {"href": d["href"], "target": d.get("target"), "rel": d.get("rel")}
            self._anchor_text = []

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._anchor is not None:
            text = " ".join(" ".join(self._anchor_text).split())
            self.anchors.append({**self._anchor, "text": text})
            self._anchor = None
            self._anchor_text = []


def contexts(text: str) -> list[dict[str, str]]:
    low = text.lower()
    out: list[dict[str, str]] = []
    for term in TARGET_TERMS:
        start = 0
        while len(out) < 160:
            pos = low.find(term, start)
            if pos < 0:
                break
            out.append({"term": term, "text": text[max(0, pos - 1100):min(len(text), pos + 2200)]})
            start = pos + len(term)
    return out


def relevant_anchor(base: str, anchor: dict[str, object]) -> dict[str, object]:
    raw = str(anchor.get("href") or "")
    resolved = urllib.parse.urljoin(base, raw)
    p = urllib.parse.urlparse(resolved)
    return {
        **anchor,
        "resolvedUrl": resolved,
        "host": p.hostname,
        "sameOrigin": same_origin(resolved),
        "requested": False,
    }


def main() -> None:
    pages: list[dict[str, object]] = []
    asset_urls: list[str] = []
    all_anchors: list[dict[str, object]] = []

    for url in PAGES:
        try:
            html, headers = get_text(url)
            parser = PageParser()
            parser.feed(html)
            anchors = [relevant_anchor(url, a) for a in parser.anchors]
            all_anchors.extend(anchors)
            pages.append({
                "url": url,
                "headers": headers,
                "anchorCount": len(anchors),
                "anchors": anchors,
                "contexts": contexts(html),
            })
            for raw in parser.assets:
                asset = urllib.parse.urljoin(url, raw)
                if same_origin(asset) and asset.lower().split("?", 1)[0].endswith((".js", ".json")) and asset not in asset_urls:
                    asset_urls.append(asset)
                    if len(asset_urls) >= MAX_ASSETS:
                        break
        except Exception as exc:
            pages.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

    sources: list[dict[str, object]] = []
    structured_pairs: list[dict[str, str]] = []
    pair_patterns = [
        re.compile(r'''(?:href|url|link|b2c|nextcharge)\s*:\s*["']([^"']+)["']''', re.I),
        re.compile(r'''["'](?:href|url|link|b2c|nextcharge)["']\s*:\s*["']([^"']+)["']''', re.I),
        re.compile(r'''(?:window\.open|location\.href\s*=)\s*\(?\s*["']([^"']+)["']''', re.I),
    ]
    for url in asset_urls:
        try:
            text, headers = get_text(url)
            low = text.lower()
            if not any(t in low for t in TARGET_TERMS):
                continue
            for pat in pair_patterns:
                for m in pat.finditer(text):
                    raw = m.group(1)
                    if "nextcharge" in raw.lower() or "b2c" in raw.lower() or raw.startswith(("http://", "https://", "/")):
                        structured_pairs.append({"source": url, "raw": raw[:1600]})
            sources.append({
                "url": url,
                "headers": headers,
                "bytesDecoded": len(text.encode("utf-8")),
                "contexts": contexts(text),
            })
        except Exception as exc:
            sources.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

    relevant_anchors = []
    for a in all_anchors:
        blob = (str(a.get("text") or "") + " " + str(a.get("href") or "") + " " + str(a.get("resolvedUrl") or "")).lower()
        if any(t in blob for t in ("b2c", "nextcharge", "terms", "status", "cpo", "fleet")):
            relevant_anchors.append(a)

    report = {
        "schemaVersion": 2,
        "generatedAt": now_iso(),
        "scope": "official Go Electric rendered B2C/NextCharge anchor evidence",
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
        "pages": pages,
        "assetCountFetched": len(asset_urls),
        "sourceCountWithTargetTerms": len(sources),
        "relevantAnchors": relevant_anchors,
        "structuredLinkCandidates": structured_pairs[:500],
        "b2cContextCount": sum(1 for p in pages for c in p.get("contexts", []) if c.get("term") == "b2c") + sum(1 for s in sources for c in s.get("contexts", []) if c.get("term") == "b2c"),
        "nextchargeContextCount": sum(1 for p in pages for c in p.get("contexts", []) if c.get("term") == "nextcharge") + sum(1 for s in sources for c in s.get("contexts", []) if c.get("term") == "nextcharge"),
        "sources": sources,
    }
    out = Path("artifacts/go_electric_official_link_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pages": [{"url": p.get("url"), "anchors": p.get("anchorCount"), "error": p.get("error")} for p in pages],
        "relevantAnchors": relevant_anchors,
        "structuredLinkCandidates": structured_pairs[:100],
        "b2cContexts": report["b2cContextCount"],
        "nextchargeContexts": report["nextchargeContextCount"],
    }, ensure_ascii=False, indent=2))
    if report["nextchargeContextCount"] == 0:
        raise SystemExit("no NextCharge context found in official canonical source")


if __name__ == "__main__":
    main()
