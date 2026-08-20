#!/usr/bin/env python3
"""Discover Powerdot public QR/payment endpoint candidates from first-party public pages.

Safety constraints:
- public GET only;
- no QR image decoding, credentials, cookies, tokens, payment submission or session start;
- no raw page/JS persistence;
- output contains sanitized URLs, hosts, paths and bounded metadata only.
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
PAGES = [
    "https://www.powerdot.eu/fr/vos-questions",
    "https://www.powerdot.eu/fr",
    "https://www.powerdot.eu/fr/blog/marker/match-arras",
]
KNOWN_PUBLIC_EVSES = [
    "FRPD1EASCGUYBBC0011",
    "FRPD1EDUVVRSKP0013",
    "FRPD1ECACSDSIES50013",
]
KEYWORDS = (
    "qr", "payment", "pay", "checkout", "charge", "charging", "session",
    "connector", "evse", "tariff", "price", "start", "transaction",
)
ABS_RE = re.compile(r"https?://[^\s\"'<>`]+", re.I)
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
LINK_RE = re.compile(r"<(?:a|form)\b[^>]*(?:href|action)=[\"']([^\"']+)[\"']", re.I)
STR_RE = re.compile(r"[\"']([^\"'\n\r]{3,260})[\"']")


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


def interesting(value: str) -> bool:
    low = value.lower()
    return any(k in low for k in KEYWORDS)


def same_vendor(url: str) -> bool:
    host = urllib.parse.urlsplit(url).netloc.lower().split(":", 1)[0]
    return host == "powerdot.eu" or host.endswith(".powerdot.eu") or host == "powerdot.fr" or host.endswith(".powerdot.fr")


def collect(base: str, text: str) -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    literals: set[str] = set()
    for raw in ABS_RE.findall(text):
        raw = raw.rstrip("),.;")
        if not interesting(raw):
            continue
        try:
            urls.add(clean_url(raw))
        except Exception:
            pass
    for raw in LINK_RE.findall(text):
        absolute = urllib.parse.urljoin(base, html.unescape(raw))
        if interesting(absolute):
            try:
                urls.add(clean_url(absolute))
            except Exception:
                pass
    low = text.lower()
    for key in KEYWORDS:
        start = 0
        count = 0
        while True:
            idx = low.find(key, start)
            if idx < 0 or count >= 25:
                break
            count += 1
            window = text[max(0, idx - 500): min(len(text), idx + 700)]
            for s in STR_RE.findall(window):
                v = html.unescape(s).strip()
                if len(v) <= 220 and interesting(v) and not any(x in v.lower() for x in ("authorization", "bearer ", "cookie=", "password=", "token=")):
                    literals.add(v)
                    if v.startswith("/"):
                        try:
                            urls.add(clean_url(urllib.parse.urljoin(base, v)))
                        except Exception:
                            pass
            start = idx + len(key)
    return urls, literals


def main() -> None:
    out = Path("out/exact-price/powerdot")
    out.mkdir(parents=True, exist_ok=True)
    pages = []
    scripts: set[str] = set()
    urls: set[str] = set()
    literals: set[str] = set()
    errors = []

    for page in PAGES:
        try:
            r = fetch(page)
        except Exception as exc:
            errors.append({"url": clean_url(page), "errorType": type(exc).__name__, "message": str(exc)[:180]})
            continue
        u, l = collect(r["final"], r["text"]); urls.update(u); literals.update(l)
        for src in SCRIPT_RE.findall(r["text"]):
            absolute = clean_url(urllib.parse.urljoin(r["final"], src))
            if same_vendor(absolute):
                scripts.add(absolute)
        pages.append({
            "requestedUrl": clean_url(page), "finalUrl": clean_url(r["final"]),
            "httpStatus": r["status"], "contentType": r["contentType"],
            "bytesRead": r["bytes"], "contentSha256": r["sha256"],
        })

    inspected = []
    for script in sorted(scripts)[:40]:
        try:
            r = fetch(script, 3_000_000)
        except Exception as exc:
            errors.append({"url": script, "errorType": type(exc).__name__, "message": str(exc)[:180]})
            continue
        u, l = collect(script, r["text"]); urls.update(u); literals.update(l)
        inspected.append({"url": script, "httpStatus": r["status"], "bytesRead": r["bytes"], "contentSha256": r["sha256"]})

    candidates = []
    for url in sorted(urls):
        p = urllib.parse.urlsplit(url)
        if re.search(r"\.(?:js|css|png|jpe?g|svg|ico|woff2?|ttf)$", p.path.lower()):
            continue
        candidates.append({
            "url": url,
            "host": p.netloc.lower(),
            "sameVendor": same_vendor(url),
            "kind": (
                "payment" if any(k in url.lower() for k in ("payment", "checkout", "pay"))
                else "session" if any(k in url.lower() for k in ("session", "start", "transaction"))
                else "connector" if any(k in url.lower() for k in ("connector", "evse"))
                else "charge_or_qr"
            ),
        })

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "powerdot-public-qr-endpoint-discovery",
        "generatedAt": now_iso(),
        "method": {
            "authenticated": False,
            "paymentSubmitted": False,
            "chargingSessionStarted": False,
            "qrImageDecoded": False,
            "persistRawBodies": False,
            "httpMethods": ["GET"],
        },
        "pages": pages,
        "sameVendorScriptsInspected": len(inspected),
        "knownPublicEvseIdsUsedOnlyAsReference": KNOWN_PUBLIC_EVSES,
        "candidateEndpoints": candidates[:160],
        "semanticLiterals": sorted(literals)[:220],
        "conclusion": {
            "publicQrOrPaymentEndpointCandidateFound": bool(candidates),
            "externalReferencedPaymentHostFound": any(not x["sameVendor"] and x["kind"] in ("payment", "session", "connector", "charge_or_qr") for x in candidates),
            "nextStep": (
                "validate discovered public QR/payment route with one known public EVSE using GET only"
                if candidates
                else "no public QR endpoint discovered from first-party web assets; retain station-specific reference-only tariff"
            ),
        },
        "errors": errors[-30:],
    }
    (out / "powerdot_public_qr_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "SUMMARY.md").write_text(
        "# Powerdot public QR discovery\n\n"
        f"- First-party pages checked: **{len(pages)}**\n"
        f"- Same-vendor scripts inspected: **{len(inspected)}**\n"
        f"- Candidate QR/payment endpoints: **{len(candidates)}**\n"
        f"- Next step: {payload['conclusion']['nextStep']}\n",
        encoding="utf-8",
    )
    print((out / "SUMMARY.md").read_text())


if __name__ == "__main__":
    main()
