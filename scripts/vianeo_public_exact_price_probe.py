#!/usr/bin/env python3
"""Discover ENGIE Vianeo public station/exact-price web surfaces.

Safety:
- public unauthenticated GET requests only;
- no login, cookies, tokens, mobile packages, payment or charging actions;
- raw HTML/JS is never persisted;
- output stores only sanitized URLs, metadata and public semantic markers.
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
PAGES = [
    "https://www.engie-vianeo.com/tarifs-recharge-voiture-electrique/",
    "https://www.engie-vianeo.com/aide/",
    "https://www.engie-vianeo.com/selection/",
    "https://www.engie-vianeo.com/super-heures-creuses/",
]
ALLOWED_ROOTS = ("engie-vianeo.com", "vianeo.com")
REFERENCE_STATIONS = ["Igny Palaiseau", "Lieusaint Carré Sénart", "Noisy-le-Grand"]
KEYWORDS = (
    "api", "graphql", "station", "stations", "borne", "bornes", "evse", "connector",
    "connecteur", "map", "carte", "location", "tarif", "tariff", "price", "pricing",
    "charge", "charging", "recharge", "availability", "status", "app", "portal", "qr",
)
BLOCK = ("login", "logout", "signin", "signup", "register", "account", "user", "payment", "pay", "start", "stop", "session", "token", "callback")
ABS_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
REL_RE = re.compile(r"[\"'](/[^\"'<>\s]{2,240})[\"']")
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    path = re.sub(r"/{2,}", "/", p.path or "/")
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), path, "", ""))


def allowed(host: str) -> bool:
    host = (host or "").lower().split(":", 1)[0]
    return any(host == root or host.endswith("." + root) for root in ALLOWED_ROOTS)


def fetch(url: str, limit: int = 5_000_000) -> dict:
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


def meta(requested: str, r: dict) -> dict:
    return {
        "requestedUrl": clean(requested),
        "finalUrl": clean(r["final_url"]),
        "httpStatus": r["status"],
        "contentType": r["content_type"],
        "bytesRead": r["bytes"],
        "contentSha256": r["sha256"],
    }


def interesting(value: str) -> bool:
    low = value.lower()
    return any(k in low for k in KEYWORDS)


def candidate_urls(base: str, text: str) -> set[str]:
    out: set[str] = set()
    for raw in ABS_RE.findall(text):
        raw = html.unescape(raw).rstrip("),.;`]")
        try:
            p = urllib.parse.urlsplit(raw)
        except ValueError:
            continue
        if p.scheme in ("http", "https") and allowed(p.netloc) and interesting(raw):
            out.add(clean(raw))
    for raw in REL_RE.findall(text):
        raw = html.unescape(raw)
        if not interesting(raw) or any(x in raw for x in ("{", "}", "${", "<", ">", "\\")):
            continue
        u = urllib.parse.urljoin(base, raw)
        p = urllib.parse.urlsplit(u)
        if p.scheme in ("http", "https") and allowed(p.netloc):
            out.add(clean(u))
    return out


def script_urls(base: str, text: str) -> list[str]:
    out, seen = [], set()
    for src in SCRIPT_RE.findall(text):
        u = clean(urllib.parse.urljoin(base, html.unescape(src)))
        p = urllib.parse.urlsplit(u)
        if not allowed(p.netloc) or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out[:80]


def kind(url: str) -> str:
    low = url.lower()
    if "graphql" in low:
        return "graphql_candidate"
    if any(x in low for x in ("tarif", "tariff", "price", "pricing")):
        return "pricing_candidate"
    if any(x in low for x in ("station", "borne", "evse", "connector", "connecteur", "map", "carte", "location")):
        return "station_candidate"
    if "api" in low:
        return "api_candidate"
    if any(x in low for x in ("portal", "charge", "charging", "recharge", "qr", "app")):
        return "portal_candidate"
    return "other_candidate"


def public_markers(text: str) -> list[str]:
    low = text.lower()
    markers = []
    for marker in ("tarif", "price", "station", "borne", "evse", "connector", "map", "carte", "api", "graphql", "qr code", "apple pay", "google pay", "vianeo max"):
        if marker in low:
            markers.append(marker)
    return markers


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/exact-price/vianeo")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages, scripts_meta, errors = [], [], []
    discovered: set[str] = set()
    markers: set[str] = set()
    scripts_seen: set[str] = set()

    for page in PAGES:
        try:
            r = fetch(page)
        except Exception as exc:
            errors.append({"url": clean(page), "errorType": type(exc).__name__, "message": str(exc)[:220]})
            continue
        pages.append(meta(page, r))
        markers.update(public_markers(r["text"]))
        discovered.update(candidate_urls(r["final_url"], r["text"]))
        for jsu in script_urls(r["final_url"], r["text"]):
            if jsu in scripts_seen:
                continue
            scripts_seen.add(jsu)
            try:
                js = fetch(jsu, 7_000_000)
            except Exception as exc:
                errors.append({"url": jsu, "errorType": type(exc).__name__, "message": str(exc)[:220]})
                continue
            scripts_meta.append({"url": jsu, "httpStatus": js["status"], "bytesRead": js["bytes"], "contentSha256": js["sha256"]})
            markers.update(public_markers(js["text"]))
            discovered.update(candidate_urls(jsu, js["text"]))

    seeds = {clean(x) for x in PAGES}
    endpoints = []
    for u in sorted(discovered):
        if u in seeds:
            continue
        path = urllib.parse.urlsplit(u).path.lower()
        if re.search(r"\.(?:js|css|png|jpe?g|svg|ico|woff2?|ttf|map)$", path):
            continue
        endpoints.append({"url": u, "kind": kind(u)})

    probes = []
    for item in endpoints[:60]:
        u = item["url"]
        low = u.lower()
        if any(x in low for x in BLOCK):
            continue
        try:
            r = fetch(u, 900_000)
            probes.append({
                "url": u,
                "kind": item["kind"],
                "httpStatus": r["status"],
                "finalUrl": clean(r["final_url"]),
                "contentType": r["content_type"],
                "bytesRead": r["bytes"],
                "contentSha256": r["sha256"],
                "semanticMarkers": public_markers(r["text"]),
            })
        except Exception as exc:
            probes.append({"url": u, "kind": item["kind"], "errorType": type(exc).__name__, "message": str(exc)[:220]})

    viable_station = [x for x in probes if x.get("httpStatus") == 200 and x.get("kind") in ("station_candidate", "api_candidate", "graphql_candidate")]
    viable_pricing = [x for x in probes if x.get("httpStatus") == 200 and x.get("kind") in ("pricing_candidate", "graphql_candidate")]

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "vianeo-public-exact-price-discovery",
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
        "sameVendorScriptsInspected": len(scripts_meta),
        "scripts": scripts_meta[:80],
        "referenceStationsUsedOnlyAsNames": REFERENCE_STATIONS,
        "candidateEndpoints": endpoints[:140],
        "candidateEndpointCount": len(endpoints),
        "semanticMarkers": sorted(markers),
        "probes": probes,
        "conclusion": {
            "publicStationOrApiCandidateConfirmed": bool(viable_station),
            "publicPricingCandidateConfirmed": bool(viable_pricing),
            "nextStep": (
                "inspect confirmed public station/pricing candidate with a real public station identifier"
                if viable_station or viable_pricing
                else "no public exact-price web endpoint discovered; keep Vianeo exact standard tariff station-specific"
            ),
        },
        "errors": errors[-30:],
    }

    (out / "vianeo_public_exact_price_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# ENGIE Vianeo public exact-price discovery\n\n"
        f"- Pages checked: **{len(pages)}**\n"
        f"- First-party JS bundles inspected: **{len(scripts_meta)}**\n"
        f"- Candidate endpoints: **{len(endpoints)}**\n"
        f"- Public station/API candidates confirmed: **{len(viable_station)}**\n"
        f"- Public pricing candidates confirmed: **{len(viable_pricing)}**\n"
        f"- Next step: {payload['conclusion']['nextStep']}\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
