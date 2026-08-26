#!/usr/bin/env python3
"""Extract bounded, sanitized Hermes strings relevant to AVIA/Picoty public API discovery.

Requires hermes-dec source on PYTHONPATH. This intentionally does not persist API keys,
access tokens, auth headers, or other credential-like values even when embedded in the
public APK. We only retain public host/path/tenant/config identifiers needed to find the
anonymous station/tariff surface used by the app.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from hermes_dec.parsers.hbc_file_parser import HBCReader

BUNDLE = Path(sys.argv[1])
OUT = Path("data/reports/avia_picoty_hermes_api_strings.json")
KEYWORDS = (
    "deftpower", "picoty", "tenant", "nearby-locations", "map-locations",
    "tariff", "pricing", "price", "locationid", "locations/", "azure-api",
    "apiurl", "baseurl", "registration-group", "charger", "chargepoint",
)
SECRET_NAME_RE = re.compile(r"(?i)(api[-_ ]?key|authorization|bearer|access[-_ ]?token|refresh[-_ ]?token|client[-_ ]?secret)")
QUERY_SECRET_RE = re.compile(r"(?i)([?&](?:key|api_key|apikey|token|access_token|client_secret)=)[^&#\s]+")
JWT_RE = re.compile(r"\beyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}(?:\.[a-zA-Z0-9_-]{10,})?\b")
LONG_TOKEN_RE = re.compile(r"\b[a-fA-F0-9]{40,}\b|\b[A-Za-z0-9_-]{80,}\b")


def sanitize(s: str) -> str:
    s = s.replace("\x00", "")
    s = QUERY_SECRET_RE.sub(r"\1<redacted>", s)
    s = JWT_RE.sub("<redacted-jwt>", s)
    s = LONG_TOKEN_RE.sub("<redacted-token>", s)
    if SECRET_NAME_RE.search(s) and len(s) > 200:
        # Keep the fact that a sensitive config key exists, not its surrounding value.
        return "<sensitive-config-reference-redacted>"
    return s[:700]


def main() -> None:
    if not BUNDLE.exists():
        raise SystemExit(f"missing Hermes bundle: {BUNDLE}")
    reader = HBCReader()
    with BUNDLE.open("rb") as fh:
        reader.read_whole_file(fh)
    strings = reader.strings
    matches = []
    seen = set()
    indexes = []
    for i, s in enumerate(strings):
        low = s.lower()
        if any(k in low for k in KEYWORDS):
            indexes.append(i)
    for i in indexes:
        # Nearby string-table entries often contain the literal route/base URL/tenant
        # separately. Keep a narrow neighborhood while sanitizing aggressively.
        for j in range(max(0, i - 3), min(len(strings), i + 4)):
            raw = strings[j]
            if not raw or len(raw) > 2000:
                continue
            val = sanitize(raw)
            if not val or val in seen:
                continue
            seen.add(val)
            matches.append({"index": j, "value": val, "triggerIndex": i})

    exact_hosts = sorted({
        m.group(0).lower()
        for s in strings
        for m in re.finditer(r"(?i)(?:https?://)?(?:[a-z0-9-]+\.)+(?:deftpower\.com|azure-api\.net|azurewebsites\.net)", s)
    })
    exact_routes = sorted({
        sanitize(s) for s in strings
        if any(x in s.lower() for x in ("nearby-locations", "map-locations", "locations/:locationid", "tariff"))
        and len(s) <= 700
        and not SECRET_NAME_RE.search(s)
    })
    payload = {
        "bytecodeVersion": int(reader.header.version),
        "stringCount": len(strings),
        "exactHosts": exact_hosts,
        "exactRoutesAndTariffStrings": exact_routes,
        "boundedRelevantStrings": matches,
        "safety": {
            "credentialsPersisted": False,
            "tokensPersisted": False,
            "purpose": "public anonymous station/tariff API discovery only",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "bytecodeVersion": payload["bytecodeVersion"],
        "stringCount": payload["stringCount"],
        "exactHosts": exact_hosts,
        "exactRoutesAndTariffStrings": exact_routes[:80],
        "boundedRelevantStringCount": len(matches),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
