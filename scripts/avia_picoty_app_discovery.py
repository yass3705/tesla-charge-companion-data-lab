#!/usr/bin/env python3
"""Static discovery helper for the public AVIA VOLT Recharge & Vous Android app.

This script does not authenticate, start sessions, or access customer data. It only
extracts public URL/host/config strings from a locally downloaded APK/XAPK so we can
identify the Picoty/Deftpower station/tariff API used by the public app.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

APK = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/avia-picoty.apk")
OUT = Path("data/reports/avia_picoty_app_api_discovery.json")

URL_RE = re.compile(rb"https?://[^\x00-\x20\"'<>\\]{5,500}", re.I)
HOST_HINT_RE = re.compile(rb"(?:[a-z0-9-]+\.)+(?:deftpower\.com|picoty\.fr|deftpower\.io)", re.I)
KEYWORDS = (b"deftpower", b"picoty", b"tariff", b"chargepoint", b"location", b"station", b"tenant", b"graphql", b"api")


def iter_blobs(path: Path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.file_size > 80_000_000:
                    continue
                try:
                    yield info.filename, z.read(info)
                except Exception:
                    pass
    else:
        yield path.name, path.read_bytes()


def clean_url(raw: bytes) -> str | None:
    s = raw.decode("utf-8", "ignore").rstrip("),.;]}")
    try:
        p = urlparse(s)
    except Exception:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return s


def main() -> None:
    if not APK.exists():
        raise SystemExit(f"missing {APK}")
    urls: set[str] = set()
    hosts: set[str] = set()
    hits: list[dict[str, str]] = []

    for name, blob in iter_blobs(APK):
        lower = blob.lower()
        if not any(k in lower for k in KEYWORDS):
            continue
        for m in URL_RE.finditer(blob):
            u = clean_url(m.group(0))
            if not u:
                continue
            urls.add(u)
            hosts.add(urlparse(u).netloc.lower())
        for m in HOST_HINT_RE.finditer(blob):
            hosts.add(m.group(0).decode("utf-8", "ignore").lower())
        # Preserve small contextual ASCII snippets around key infrastructure terms.
        for kw in (b"deftpower", b"picoty", b"tenant"):
            start = 0
            while len(hits) < 250:
                i = lower.find(kw, start)
                if i < 0:
                    break
                lo, hi = max(0, i - 180), min(len(blob), i + 300)
                snippet = re.sub(rb"[^\x20-\x7e]+", b" ", blob[lo:hi]).decode("ascii", "ignore")
                hits.append({"file": name, "keyword": kw.decode(), "snippet": snippet})
                start = i + len(kw)

    interesting_urls = sorted(
        u for u in urls
        if any(x in u.lower() for x in ("deftpower", "picoty", "api", "tenant", "charge", "location", "tariff"))
    )
    payload = {
        "apk": APK.name,
        "hosts": sorted(hosts),
        "interestingUrls": interesting_urls,
        "contextHits": hits,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hostCount": len(hosts), "interestingUrlCount": len(interesting_urls), "contextHitCount": len(hits)}, indent=2))
    print("hosts:")
    for h in sorted(hosts): print(" -", h)
    print("interesting URLs:")
    for u in interesting_urls[:100]: print(" -", u)


if __name__ == "__main__":
    main()
