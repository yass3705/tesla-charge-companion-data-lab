#!/usr/bin/env python3
"""Discover public, unauthenticated pricing/station endpoints for selected CPO apps.

Safety rules:
- GET-only public pages and same-vendor JavaScript bundles.
- No login, cookies, credentials, tokens, mobile app packages or authenticated exports.
- Raw HTML/JS is never persisted; output contains only sanitized metadata and URL paths.
- Query strings/fragments are stripped from discovered URLs before writing output.
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

TARGETS = {
    "freshmile": {
        "pages": [
            "https://charge.freshmile.com/",
            "https://charge.freshmile.com/map",
            "https://charge.freshmile.com/location/A1D80CE6D8",
            "https://charge.freshmile.com/evse/CSBV1",
        ],
        "allowed_suffix": ".freshmile.com",
        "retired_markers": ["freshmile charge evolue", "passez a la solution qui vous correspond"],
    },
    "qovoltis": {
        "pages": [
            "https://chargenow.qovoltis.com/",
        ],
        "allowed_suffix": ".qovoltis.com",
        "retired_markers": [],
    },
}

KEYWORDS = (
    "api", "graphql", "evse", "location", "locations", "station", "stations",
    "chargepoint", "charge-point", "charger", "connector", "tariff", "tariffs",
    "price", "prices", "pricing", "availability", "status",
)

ABS_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
REL_URL_RE = re.compile(r"[\"'](/[^\"'<>\s]{2,220})[\"']")
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm_text(value: str) -> str:
    value = html.unescape(value or "")
    value = value.lower().replace("’", "'")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def allowed_host(host: str, suffix: str) -> bool:
    host = (host or "").lower().split(":", 1)[0]
    root = suffix.lstrip(".")
    return host == root or host.endswith(suffix)


def sanitize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.lower(), path, "", ""))


def fetch(url: str) -> dict:
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
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=35, context=ctx) as resp:
        raw = resp.read(6_000_000)
        ctype = resp.headers.get("Content-Type", "")
        charset = resp.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
        return {
            "status": int(getattr(resp, "status", 200)),
            "final_url": resp.geturl(),
            "content_type": ctype.split(";", 1)[0].strip().lower(),
            "text": text,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


def page_metadata(requested: str, result: dict, retired_markers: list[str]) -> dict:
    raw = result["text"]
    title_m = TITLE_RE.search(raw)
    title = re.sub(r"\s+", " ", html.unescape(title_m.group(1))).strip() if title_m else None
    n = norm_text(raw[:150_000])
    retired = any(norm_text(marker) in n for marker in retired_markers)
    return {
        "requestedUrl": sanitize_url(requested),
        "finalUrl": sanitize_url(result["final_url"]),
        "httpStatus": result["status"],
        "contentType": result["content_type"],
        "bytesRead": result["bytes"],
        "contentSha256": result["sha256"],
        "redirected": sanitize_url(requested) != sanitize_url(result["final_url"]),
        "title": title,
        "retiredLandingDetected": retired,
    }


def script_urls(page_url: str, raw_html: str, suffix: str) -> list[str]:
    out = []
    seen = set()
    for src in SCRIPT_RE.findall(raw_html):
        absolute = urllib.parse.urljoin(page_url, html.unescape(src))
        parsed = urllib.parse.urlsplit(absolute)
        if parsed.scheme not in ("http", "https") or not allowed_host(parsed.netloc, suffix):
            continue
        clean = sanitize_url(absolute)
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out[:24]


def looks_interesting(value: str) -> bool:
    low = value.lower()
    return any(k in low for k in KEYWORDS)


def candidate_urls(base_url: str, text: str, suffix: str) -> set[str]:
    candidates: set[str] = set()
    for raw in ABS_URL_RE.findall(text):
        raw = html.unescape(raw).rstrip("),.;")
        try:
            p = urllib.parse.urlsplit(raw)
        except ValueError:
            continue
        if p.scheme in ("http", "https") and allowed_host(p.netloc, suffix) and looks_interesting(raw):
            candidates.add(sanitize_url(raw))
    for raw in REL_URL_RE.findall(text):
        if not looks_interesting(raw):
            continue
        if any(x in raw for x in ("{", "}", "<", ">", "${", "\\")):
            continue
        absolute = urllib.parse.urljoin(base_url, html.unescape(raw))
        p = urllib.parse.urlsplit(absolute)
        if allowed_host(p.netloc, suffix):
            candidates.add(sanitize_url(absolute))
    return candidates


def classify_candidate(url: str) -> str:
    low = url.lower()
    if "graphql" in low:
        return "graphql_candidate"
    if "tariff" in low or "price" in low or "pricing" in low:
        return "pricing_candidate"
    if "evse" in low or "chargepoint" in low or "connector" in low:
        return "evse_candidate"
    if "location" in low or "station" in low:
        return "location_candidate"
    if "availability" in low or "status" in low:
        return "status_candidate"
    return "api_candidate"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=sorted(TARGETS), required=True)
    ap.add_argument("--out", default="out/exact-price")
    args = ap.parse_args()

    cfg = TARGETS[args.target]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages = []
    scripts_seen: set[str] = set()
    candidates: set[str] = set()
    errors = []

    for requested in cfg["pages"]:
        try:
            result = fetch(requested)
        except Exception as exc:
            errors.append({"url": sanitize_url(requested), "errorType": type(exc).__name__, "message": str(exc)[:240]})
            continue
        pages.append(page_metadata(requested, result, cfg["retired_markers"]))
        candidates.update(candidate_urls(result["final_url"], result["text"], cfg["allowed_suffix"]))
        for script in script_urls(result["final_url"], result["text"], cfg["allowed_suffix"]):
            if script in scripts_seen:
                continue
            scripts_seen.add(script)
            try:
                js = fetch(script)
            except Exception as exc:
                errors.append({"url": script, "errorType": type(exc).__name__, "message": str(exc)[:240]})
                continue
            candidates.update(candidate_urls(script, js["text"], cfg["allowed_suffix"]))

    # Remove static assets and the seed pages themselves from endpoint candidates.
    seed = {sanitize_url(x) for x in cfg["pages"]}
    cleaned = []
    for url in sorted(candidates):
        if url in seed:
            continue
        path = urllib.parse.urlsplit(url).path.lower()
        if re.search(r"\.(?:js|css|png|jpe?g|svg|ico|woff2?|ttf|map)$", path):
            continue
        cleaned.append({"url": url, "kind": classify_candidate(url)})

    pricing_candidates = [x for x in cleaned if x["kind"] in ("pricing_candidate", "graphql_candidate")]
    station_candidates = [x for x in cleaned if x["kind"] in ("evse_candidate", "location_candidate", "graphql_candidate", "api_candidate")]
    retired = bool(pages) and all(p.get("retiredLandingDetected") for p in pages if "freshmile.com" in p["finalUrl"]) if args.target == "freshmile" else False

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": f"{args.target}-public-exact-price-discovery",
        "generatedAt": now_iso(),
        "target": args.target,
        "method": {
            "authenticated": False,
            "mobilePackageUsed": False,
            "persistRawHtmlOrJs": False,
            "httpMethods": ["GET"],
        },
        "pages": pages,
        "sameVendorScriptsInspected": len(scripts_seen),
        "candidateEndpoints": cleaned[:120],
        "candidateEndpointCount": len(cleaned),
        "pricingCandidateCount": len(pricing_candidates),
        "stationCandidateCount": len(station_candidates),
        "freshmileLegacyWebMapRetired": retired if args.target == "freshmile" else None,
        "conclusion": {
            "publicMachineReadablePricingCandidateFound": bool(pricing_candidates),
            "publicMachineReadableStationCandidateFound": bool(station_candidates),
            "nextStep": (
                "inspect discovered public candidate endpoints with read-only GET requests"
                if pricing_candidates or station_candidates
                else "no public web endpoint discovered; move to the next operator or app-only analysis without credentials"
            ),
        },
        "errors": errors[-30:],
    }

    (out / f"{args.target}_public_exact_price_probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = [
        f"# {args.target} public exact-price discovery",
        "",
        f"- Pages checked: **{len(pages)}**",
        f"- Same-vendor JS bundles inspected: **{len(scripts_seen)}**",
        f"- Candidate endpoints: **{len(cleaned)}**",
        f"- Pricing candidates: **{len(pricing_candidates)}**",
        f"- Station/API candidates: **{len(station_candidates)}**",
    ]
    if args.target == "freshmile":
        summary.append(f"- Legacy public web map retired/redirected to app landing: **{'yes' if retired else 'no'}**")
    summary.extend([
        f"- Public machine-readable pricing candidate found: **{'yes' if pricing_candidates else 'no'}**",
        f"- Next step: {payload['conclusion']['nextStep']}",
        "",
    ])
    (out / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
