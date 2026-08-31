#!/usr/bin/env python3
"""Identify the canonical public Go Electric Stations web host without following unknown redirects.

This is a read-only bootstrap probe. It sends GET requests only to the two known
Go Electric Stations hostnames. Redirects are deliberately NOT followed. Any
Location header is recorded as a candidate and remains blocked until explicitly
validated in a later step.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOTS = (
    "https://goelectricstations.com/",
    "https://www.goelectricstations.com/",
)
ALLOWED_HOSTS = {"goelectricstations.com", "www.goelectricstations.com"}
USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() in ALLOWED_HOSTS


def probe(url: str) -> dict:
    if not allowed(url):
        raise RuntimeError(f"outside bootstrap allowlist: {url}")
    opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,*/*;q=0.5",
    })
    try:
        with opener.open(req, timeout=30) as resp:
            body = resp.read(2048)
            return {
                "url": url,
                "status": int(getattr(resp, "status", 200)),
                "location": resp.headers.get("Location"),
                "contentType": resp.headers.get("Content-Type"),
                "sampleBytes": len(body),
            }
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") if exc.headers else None
        return {
            "url": url,
            "status": int(exc.code),
            "location": location,
            "contentType": exc.headers.get("Content-Type") if exc.headers else None,
            "sampleBytes": 0,
        }
    except Exception as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    results = [probe(url) for url in ROOTS]
    redirects = []
    for item in results:
        loc = item.get("location")
        if not loc:
            continue
        absolute = urllib.parse.urljoin(item["url"], loc)
        parsed = urllib.parse.urlparse(absolute)
        redirects.append({
            "from": item["url"],
            "to": absolute,
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "sameBootstrapHostAllowlist": allowed(absolute),
            "followed": False,
        })

    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "scope": "Go Electric Stations canonical-host redirect discovery",
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "getOnly": True,
            "redirectsFollowed": False,
            "unknownRedirectHostsBlocked": True,
            "allowedHosts": sorted(ALLOWED_HOSTS),
            "publicationAllowed": False,
        },
        "results": results,
        "redirects": redirects,
        "candidateHosts": sorted({r.get("host") for r in redirects if r.get("host")}),
    }
    out = Path("artifacts/go_electric_official_redirect_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "results": results,
        "candidateHosts": report["candidateHosts"],
        "redirectsFollowed": False,
    }, ensure_ascii=False, indent=2))
    if not any("status" in x for x in results):
        raise SystemExit("no HTTP response from known Go Electric hosts")


if __name__ == "__main__":
    main()
