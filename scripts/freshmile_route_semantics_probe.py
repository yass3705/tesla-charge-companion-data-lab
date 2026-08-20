#!/usr/bin/env python3
"""Final public Freshmile probe for route semantics and price payload hints.

Safety constraints:
- public GET requests only;
- no authentication, cookies, tokens, mobile packages or user data;
- raw HTML/JavaScript is never persisted;
- output retains only sanitized URL/path/string candidates and bounded price hints.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
ROOT = "https://charge.freshmile.com/"
SEEDS = [
    ROOT,
    "https://charge.freshmile.com/location/A1D80CE6D8",
    "https://charge.freshmile.com/evse/CSBV1",
    "https://charge.freshmile.com/location/A1D80CE6D8/CSBV1",
]
KEYS = (
    "priceAfterTax", "priceBeforeTax", "tariffTitle", "has-free-tariff",
    "locationId", "location_id", "evseRef", "findStations", "station",
    "connector", "tariff", "pricing", "price",
)
ABS_RE = re.compile(r"https?://[^\s\"'<>`]+", re.I)
STR_RE = re.compile(r"[\"']([^\"'\n\r]{2,260})[\"']")
PRICE_RE = re.compile(
    r"(?i)(?:price(?:aftertax|beforetax)?|tariff(?:title)?|prix|tarif)[^\n\r<>]{0,120}?"
    r"(?:(?:EUR|€)\s*[0-9]+(?:[.,][0-9]+)?|[0-9]+(?:[.,][0-9]+)?\s*(?:EUR|€|€/kWh|eur/kwh))"
)
MODULE_RE = re.compile(r"(?:src|href)=[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']", re.I)
IMPORT_RE = re.compile(r"(?:from\s*|import\s*\()[\"'](\.?/?[^\"']+\.js)[\"']", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str, limit: int = 4_000_000) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/javascript,text/javascript,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=35, context=ssl.create_default_context()) as resp:
        raw = resp.read(limit)
        charset = resp.headers.get_content_charset() or "utf-8"
        return {
            "status": int(getattr(resp, "status", 200)),
            "final": resp.geturl(),
            "contentType": (resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()),
            "text": raw.decode(charset, errors="replace"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }


def clean_url(url: str) -> str:
    p = urllib.parse.urlsplit(html.unescape(url))
    path = re.sub(r"/{2,}", "/", p.path or "/")
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), path, "", ""))


def safe_literal(value: str) -> str | None:
    v = html.unescape(value).strip()
    if len(v) > 240 or any(x in v.lower() for x in ("authorization", "bearer ", "cookie=", "token=", "password=")):
        return None
    if "${" in v or "<" in v or ">" in v:
        return None
    low = v.lower()
    if not any(k.lower() in low for k in KEYS) and not low.startswith("/") and "freshmile.com" not in low:
        return None
    return v


def collect_semantics(base_url: str, text: str) -> dict:
    literals: set[str] = set()
    urls: set[str] = set()
    hints: set[str] = set()
    low = text.lower()

    for m in ABS_RE.findall(text):
        try:
            clean = clean_url(m.rstrip("),.;"))
        except Exception:
            continue
        if "freshmile.com" in urllib.parse.urlsplit(clean).netloc.lower():
            if any(k.lower() in clean.lower() for k in KEYS) or "/api/" in clean.lower():
                urls.add(clean)

    for key in KEYS:
        start = 0
        needle = key.lower()
        seen = 0
        while True:
            idx = low.find(needle, start)
            if idx < 0 or seen >= 30:
                break
            seen += 1
            window = text[max(0, idx - 700): min(len(text), idx + 900)]
            for raw in STR_RE.findall(window):
                safe = safe_literal(raw)
                if safe:
                    if safe.startswith("/"):
                        try:
                            urls.add(clean_url(urllib.parse.urljoin(base_url, safe)))
                        except Exception:
                            pass
                    literals.add(safe)
            start = idx + len(needle)

    for m in PRICE_RE.finditer(text):
        snippet = re.sub(r"\s+", " ", html.unescape(m.group(0))).strip()
        if len(snippet) <= 220:
            hints.add(snippet)

    return {
        "urls": sorted(urls)[:160],
        "literals": sorted(literals)[:240],
        "priceHints": sorted(hints)[:80],
    }


def main() -> None:
    out = Path("out/exact-price-stage4/freshmile")
    out.mkdir(parents=True, exist_ok=True)

    pages = []
    all_urls: set[str] = set()
    all_literals: set[str] = set()
    all_hints: set[str] = set()
    module_urls: set[str] = set()
    errors = []

    for url in SEEDS:
        try:
            r = fetch(url)
        except Exception as exc:
            errors.append({"url": clean_url(url), "errorType": type(exc).__name__, "message": str(exc)[:180]})
            continue
        sem = collect_semantics(r["final"], r["text"])
        all_urls.update(sem["urls"]); all_literals.update(sem["literals"]); all_hints.update(sem["priceHints"])
        for src in MODULE_RE.findall(r["text"]):
            u = clean_url(urllib.parse.urljoin(r["final"], src))
            if urllib.parse.urlsplit(u).netloc.endswith("freshmile.com"):
                module_urls.add(u)
        pages.append({
            "requestedUrl": clean_url(url),
            "finalUrl": clean_url(r["final"]),
            "httpStatus": r["status"],
            "contentType": r["contentType"],
            "bytesRead": r["bytes"],
            "contentSha256": r["sha256"],
            "priceHintCount": len(sem["priceHints"]),
        })

    # Reuse the prior stage-3 chunk inventory when available, then follow direct JS imports.
    prior = Path("reports/exact-price-stage3/freshmile_latest.json")
    if prior.exists():
        try:
            d = json.loads(prior.read_text())
            for item in d.get("chunks", []):
                u = item.get("url")
                if isinstance(u, str) and u.startswith("https://charge.freshmile.com/"):
                    module_urls.add(clean_url(u))
        except Exception:
            pass

    inspected = []
    queue = list(sorted(module_urls))[:80]
    seen: set[str] = set()
    while queue and len(seen) < 100:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            r = fetch(url, 3_500_000)
        except Exception as exc:
            errors.append({"url": url, "errorType": type(exc).__name__, "message": str(exc)[:180]})
            continue
        sem = collect_semantics(url, r["text"])
        all_urls.update(sem["urls"]); all_literals.update(sem["literals"]); all_hints.update(sem["priceHints"])
        for imp in IMPORT_RE.findall(r["text"]):
            try:
                nxt = clean_url(urllib.parse.urljoin(url, imp))
            except Exception:
                continue
            if urllib.parse.urlsplit(nxt).netloc.endswith("freshmile.com") and nxt not in seen and len(queue) < 120:
                queue.append(nxt)
        inspected.append({"url": url, "httpStatus": r["status"], "bytesRead": r["bytes"], "contentSha256": r["sha256"]})

    route_candidates = sorted({
        x for x in all_urls
        if any(k in x.lower() for k in ("api", "location", "evse", "station", "tariff", "price", "connector"))
        and not re.search(r"\.(?:js|css|png|jpe?g|svg|ico|woff2?|ttf)$", urllib.parse.urlsplit(x).path.lower())
    })
    literal_candidates = sorted({
        x for x in all_literals
        if any(k in x.lower() for k in ("price", "tariff", "station", "location", "evse", "connector", "api"))
    })

    # A numeric price is only treated as a candidate, never as validated exact pricing.
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "freshmile-public-exact-price-stage4",
        "generatedAt": now_iso(),
        "method": {
            "authenticated": False,
            "mobilePackageUsed": False,
            "persistRawBodies": False,
            "httpMethods": ["GET"],
        },
        "pages": pages,
        "chunksInspected": len(inspected),
        "routeCandidates": route_candidates[:160],
        "semanticLiterals": literal_candidates[:220],
        "numericPriceHints": sorted(all_hints)[:80],
        "conclusion": {
            "locationSpecificNumericPriceHintFound": bool(all_hints),
            "publicRouteCandidateFound": bool(route_candidates),
            "nextStep": (
                "manually validate one discovered public route against a real EVSE before TCC integration"
                if all_hints or route_candidates
                else "stop Freshmile public-web exact-price discovery and retain reference-only pricing"
            ),
        },
        "errors": errors[-30:],
    }
    p = out / "freshmile_public_exact_price_stage4.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "SUMMARY.md").write_text(
        "# Freshmile exact-price stage 4\n\n"
        f"- Public route pages checked: **{len(pages)}**\n"
        f"- Public Nuxt chunks inspected: **{len(inspected)}**\n"
        f"- Route candidates: **{len(route_candidates)}**\n"
        f"- Numeric price hints: **{len(all_hints)}**\n"
        f"- Next step: {payload['conclusion']['nextStep']}\n",
        encoding="utf-8",
    )
    print((out / "SUMMARY.md").read_text())


if __name__ == "__main__":
    main()
