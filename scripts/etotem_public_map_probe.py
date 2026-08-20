#!/usr/bin/env python3
"""Discover public e-Totem map/station/tariff endpoints from first-party web assets.

Safety:
- public unauthenticated GET requests only;
- no account, cookies, tokens, QR payment, mobile package or charging action;
- raw HTML/JS is not persisted;
- persisted URLs are stripped of query strings and fragments.
"""
from __future__ import annotations

import argparse
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
SEEDS = [
    "https://www.e-totem.fr/",
    "https://www.e-totem.fr/#/home/ou_se_recharger",
    "https://www.e-totem.fr/prive/",
]
ALLOWED_ROOTS = ("e-totem.fr", "e-totem.eu")
KEYWORDS = (
    "api", "graphql", "borne", "bornes", "station", "stations", "evse", "chargepoint",
    "charge-point", "charger", "connector", "connecteur", "location", "map", "tarif",
    "tariff", "price", "pricing", "availability", "status", "recharge", "charging",
)
ABS_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
REL_URL_RE = re.compile(r"[\"'](/[^\"'<>\s]{2,240})[\"']")
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    path = re.sub(r"/{2,}", "/", p.path or "/")
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), path, "", ""))


def allowed_host(host: str) -> bool:
    host = (host or "").lower().split(":", 1)[0]
    return any(host == root or host.endswith("." + root) for root in ALLOWED_ROOTS)


def fetch(url: str, limit: int = 6_000_000) -> dict:
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
            "final_url": resp.geturl(),
            "content_type": resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower(),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "text": raw.decode(charset, errors="replace"),
        }


def page_meta(requested: str, r: dict) -> dict:
    return {
        "requestedUrl": sanitize_url(requested),
        "finalUrl": sanitize_url(r["final_url"]),
        "httpStatus": r["status"],
        "contentType": r["content_type"],
        "bytesRead": r["bytes"],
        "contentSha256": r["sha256"],
    }


def interesting(s: str) -> bool:
    low = s.lower()
    return any(k in low for k in KEYWORDS)


def candidates(base: str, text: str) -> set[str]:
    out: set[str] = set()
    for raw in ABS_URL_RE.findall(text):
        raw = html.unescape(raw).rstrip("),.;`]")
        try:
            p = urllib.parse.urlsplit(raw)
        except ValueError:
            continue
        if p.scheme in ("http", "https") and allowed_host(p.netloc) and interesting(raw):
            out.add(sanitize_url(raw))
    for raw in REL_URL_RE.findall(text):
        raw = html.unescape(raw)
        if not interesting(raw) or any(x in raw for x in ("{", "}", "${", "<", ">", "\\")):
            continue
        absu = urllib.parse.urljoin(base, raw)
        p = urllib.parse.urlsplit(absu)
        if p.scheme in ("http", "https") and allowed_host(p.netloc):
            out.add(sanitize_url(absu))
    return out


def classify(url: str) -> str:
    low = url.lower()
    if "graphql" in low:
        return "graphql_candidate"
    if any(x in low for x in ("tarif", "tariff", "price", "pricing")):
        return "pricing_candidate"
    if any(x in low for x in ("evse", "chargepoint", "connector", "connecteur")):
        return "evse_candidate"
    if any(x in low for x in ("station", "borne", "location", "map")):
        return "station_candidate"
    if any(x in low for x in ("availability", "status")):
        return "status_candidate"
    return "api_candidate"


def script_urls(base: str, text: str) -> list[str]:
    seen, out = set(), []
    for src in SCRIPT_RE.findall(text):
        absu = urllib.parse.urljoin(base, html.unescape(src))
        p = urllib.parse.urlsplit(absu)
        if p.scheme not in ("http", "https") or not allowed_host(p.netloc):
            continue
        clean = sanitize_url(absu)
        if clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out[:80]


def numeric_price_hints(text: str) -> list[str]:
    pats = re.findall(r"(?i)(?:price|pricing|tarif|tariff)[^\n]{0,90}?\b(\d{1,2}[\.,]\d{1,3})\b", text)
    vals = []
    for x in pats:
        v = x.replace(",", ".")
        if v not in vals:
            vals.append(v)
    return vals[:30]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/exact-price/etotem")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages, scripts, errs = [], [], []
    discovered: set[str] = set()
    semantic = set()
    price_hints = []
    scripts_seen = set()

    for seed in SEEDS:
        try:
            r = fetch(seed)
        except Exception as exc:
            errs.append({"url": sanitize_url(seed), "errorType": type(exc).__name__, "message": str(exc)[:220]})
            continue
        pages.append(page_meta(seed, r))
        discovered.update(candidates(r["final_url"], r["text"]))
        price_hints.extend(x for x in numeric_price_hints(r["text"]) if x not in price_hints)
        low = r["text"].lower()
        for marker in ("ou_se_recharger", "tarif", "price", "evse", "borne", "station", "connector", "map", "api"):
            if marker in low:
                semantic.add(marker)
        for jsu in script_urls(r["final_url"], r["text"]):
            if jsu in scripts_seen:
                continue
            scripts_seen.add(jsu)
            try:
                js = fetch(jsu, 8_000_000)
            except Exception as exc:
                errs.append({"url": jsu, "errorType": type(exc).__name__, "message": str(exc)[:220]})
                continue
            scripts.append({"url": jsu, "httpStatus": js["status"], "bytesRead": js["bytes"], "contentSha256": js["sha256"]})
            discovered.update(candidates(jsu, js["text"]))
            price_hints.extend(x for x in numeric_price_hints(js["text"]) if x not in price_hints)
            low = js["text"].lower()
            for marker in ("ou_se_recharger", "tarif", "tariff", "price", "evse", "borne", "station", "connector", "connecteur", "map", "api", "graphql"):
                if marker in low:
                    semantic.add(marker)

    seeds_clean = {sanitize_url(x) for x in SEEDS}
    endpoints = []
    for u in sorted(discovered):
        if u in seeds_clean:
            continue
        path = urllib.parse.urlsplit(u).path.lower()
        if re.search(r"\.(?:js|css|png|jpe?g|svg|ico|woff2?|ttf|map)$", path):
            continue
        endpoints.append({"url": u, "kind": classify(u)})

    # Read-only GET only against concrete, first-party candidates. Avoid account/payment/action routes.
    probes = []
    for item in endpoints[:40]:
        u = item["url"]
        low = u.lower()
        if any(x in low for x in ("login", "logout", "signin", "signup", "register", "payment", "payzen", "start", "stop", "session", "account", "user")):
            continue
        try:
            r = fetch(u, 1_000_000)
            probes.append({
                "url": u,
                "kind": item["kind"],
                "httpStatus": r["status"],
                "finalUrl": sanitize_url(r["final_url"]),
                "contentType": r["content_type"],
                "bytesRead": r["bytes"],
                "contentSha256": r["sha256"],
                "numericPriceHints": numeric_price_hints(r["text"]),
            })
        except Exception as exc:
            probes.append({"url": u, "kind": item["kind"], "errorType": type(exc).__name__, "message": str(exc)[:220]})

    pricing = [x for x in endpoints if x["kind"] in ("pricing_candidate", "graphql_candidate")]
    stations = [x for x in endpoints if x["kind"] in ("station_candidate", "evse_candidate", "api_candidate", "graphql_candidate")]
    public_json = [x for x in probes if x.get("contentType") == "application/json" and x.get("httpStatus") == 200]
    exact_hint = [x for x in probes if x.get("numericPriceHints")]

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "etotem-public-map-exact-price-discovery",
        "generatedAt": now_iso(),
        "method": {
            "authenticated": False,
            "mobilePackageUsed": False,
            "paymentSubmitted": False,
            "chargingSessionStarted": False,
            "persistRawBodies": False,
            "httpMethods": ["GET"],
        },
        "pages": pages,
        "sameVendorScriptsInspected": len(scripts),
        "scripts": scripts[:80],
        "candidateEndpoints": endpoints[:120],
        "candidateEndpointCount": len(endpoints),
        "pricingCandidateCount": len(pricing),
        "stationCandidateCount": len(stations),
        "semanticMarkers": sorted(semantic),
        "numericPriceHints": price_hints[:30],
        "probes": probes,
        "conclusion": {
            "publicMachineReadableStationCandidateFound": bool(stations),
            "publicMachineReadablePricingCandidateFound": bool(pricing or exact_hint),
            "publicJsonEndpointConfirmed": bool(public_json),
            "nextStep": (
                "inspect confirmed public JSON/station endpoint with real public EVSE identifiers"
                if public_json or exact_hint
                else "no usable public exact-price endpoint confirmed; keep e-Totem reference-only unless a real station URL/QR exposes tariff data"
            ),
        },
        "errors": errs[-30:],
    }

    (out / "etotem_public_map_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# e-Totem public map exact-price discovery\n\n"
        f"- Pages checked: **{len(pages)}**\n"
        f"- First-party JS bundles inspected: **{len(scripts)}**\n"
        f"- Candidate endpoints: **{len(endpoints)}**\n"
        f"- Pricing candidates: **{len(pricing)}**\n"
        f"- Station/API candidates: **{len(stations)}**\n"
        f"- Public JSON endpoints confirmed: **{len(public_json)}**\n"
        f"- Numeric price hints from public probes: **{sum(len(x.get('numericPriceHints', [])) for x in probes)}**\n"
        f"- Next step: {payload['conclusion']['nextStep']}\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
