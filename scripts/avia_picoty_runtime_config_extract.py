#!/usr/bin/env python3
"""Sanitize app resource/decompiler context for AVIA Picoty public guest API discovery.

Inputs are decoded public APK resources and optional hermes-dec pseudo-code. The output
retains only brand/tenant/base-URL/guest-route context and strips credential-like values.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DECODED = Path(sys.argv[1])
DECOMPILED = Path(sys.argv[2]) if len(sys.argv) > 2 else None
OUT = Path("data/reports/avia_picoty_runtime_config.json")

TERMS = (
    "picoty", "avia volt", "aviavolt", "deftpower", "tenant", "pdefweu",
    "azure-api", "getlocationtariffsasguest", "get-location-tariffs-as-guest",
    "getmaplocationsasguest", "get-map-locations-as-guest", "nearby-locations-as-guest",
    "/map-locations", "/locations/:locationid/tariffs", "baseurl", "apiurl",
)

# Match JS/JSON assignments such as:
#   'API_SUBSCRIPTION_KEY': '...'
#   "ANDROID_GOOGLE_MAPS_API_KEY": "..."
# and unquoted forms such as API_KEY=...
SECRET_OBJECT_RE = re.compile(
    r"(?ix)(?P<prefix>['\"]?(?:"
    r"(?:[A-Z0-9_]*API(?:_SUBSCRIPTION)?_KEY)|"
    r"(?:[A-Z0-9_]*GOOGLE_MAPS_API_KEY)|"
    r"AUTHORIZATION|BEARER|ACCESS_TOKEN|REFRESH_TOKEN|CLIENT_SECRET|SUBSCRIPTION_KEY"
    r")['\"]?\s*:\s*)(?P<quote>['\"])(?P<value>[^'\"]+)(?P=quote)"
)
SECRET_ASSIGN_RE = re.compile(
    r"(?i)((?:api[-_ ]?key|authorization|bearer|access[-_ ]?token|refresh[-_ ]?token|client[-_ ]?secret|subscription[-_ ]?key)\s*=\s*)[^\s,;\"']+"
)
QUERY_SECRET_RE = re.compile(r"(?i)([?&](?:key|api_key|apikey|token|access_token|client_secret)=)[^&#\s]+")
GOOGLE_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}(?:\.[A-Za-z0-9_-]{10,})?\b")
LONG_TOKEN_RE = re.compile(r"\b[a-fA-F0-9]{40,}\b|\b[A-Za-z0-9_-]{100,}\b")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")


def sanitize(s: str) -> str:
    s = SECRET_OBJECT_RE.sub(lambda m: f"{m.group('prefix')}{m.group('quote')}<redacted>{m.group('quote')}", s)
    s = SECRET_ASSIGN_RE.sub(r"\1<redacted>", s)
    s = QUERY_SECRET_RE.sub(r"\1<redacted>", s)
    s = GOOGLE_KEY_RE.sub("<redacted-google-api-key>", s)
    s = JWT_RE.sub("<redacted-jwt>", s)
    s = LONG_TOKEN_RE.sub("<redacted-token>", s)
    return s[:1800]


def relevant(s: str) -> bool:
    low = s.lower()
    return any(t in low for t in TERMS)


def collect_resources(root: Path) -> list[dict[str, str]]:
    hits = []
    allowed_suffixes = {".xml", ".json", ".txt", ".properties", ".js", ".html", ".yml", ".yaml"}
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in allowed_suffixes:
            continue
        try:
            if p.stat().st_size > 5_000_000:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if relevant(line):
                lo, hi = max(0, i - 2), min(len(lines), i + 3)
                context = sanitize("\n".join(lines[lo:hi]))
                hits.append({"file": str(p.relative_to(root)), "line": i + 1, "context": context})
                if len(hits) >= 400:
                    return hits
    return hits


def collect_decompiled(path: Path | None) -> list[dict[str, object]]:
    if not path or not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    hits = []
    low = text.lower()
    needles = [t for t in TERMS if len(t) >= 8]
    seen = set()
    for needle in needles:
        start = 0
        while len(hits) < 250:
            i = low.find(needle, start)
            if i < 0:
                break
            lo, hi = max(0, i - 1400), min(len(text), i + 2200)
            ctx = sanitize(text[lo:hi])
            key = ctx[:500]
            if key not in seen:
                seen.add(key)
                hits.append({"needle": needle, "offset": i, "context": ctx})
            start = i + len(needle)
    return hits


def extract_candidates(resource_hits, decompiled_hits):
    joined = "\n".join(x["context"] for x in resource_hits) + "\n" + "\n".join(str(x["context"]) for x in decompiled_hits)
    hosts = sorted(set(re.findall(r"https?://[A-Za-z0-9._-]+", joined)))
    uuids = sorted(set(UUID_RE.findall(joined)))
    # UUIDs are identifiers, but not automatically assumed to be a tenant. Keep as candidates.
    return {
        "hosts": [h for h in hosts if "deftpower" in h.lower() or "azure" in h.lower()],
        "uuidCandidates": uuids[:100],
    }


def main() -> None:
    resource_hits = collect_resources(DECODED) if DECODED.exists() else []
    decompiled_hits = collect_decompiled(DECOMPILED)
    payload = {
        "resourceHits": resource_hits,
        "decompiledHits": decompiled_hits,
        "candidates": extract_candidates(resource_hits, decompiled_hits),
        "safety": {
            "credentialsPersisted": False,
            "tokensPersisted": False,
            "identifiersAreCandidatesOnly": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    # Fail closed if a common credential marker survived sanitization.
    forbidden = [
        r"AIza[0-9A-Za-z_-]{20,}",
        r"(?i)['\"]API_SUBSCRIPTION_KEY['\"]\s*:\s*['\"](?!<redacted>)",
        r"(?i)['\"]ANDROID_GOOGLE_MAPS_API_KEY['\"]\s*:\s*['\"](?!<redacted>)",
    ]
    for pattern in forbidden:
        if re.search(pattern, rendered):
            raise RuntimeError(f"sensitive value survived sanitization: {pattern}")
    OUT.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "resourceHitCount": len(resource_hits),
        "decompiledHitCount": len(decompiled_hits),
        "candidates": payload["candidates"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
