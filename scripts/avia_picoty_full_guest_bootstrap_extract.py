#!/usr/bin/env python3
"""Extract Picoty public/guest bootstrap operations from the *full* decompiled app.

Inputs:
  argv[1] decoded APK resource directory
  argv[2] hermes-dec pseudo-code for the complete index.android.bundle

Only public identifiers, route structure, operation names and nearby config metadata are
retained. Credential/token-like values are redacted before persistence.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DECODED = Path(sys.argv[1])
DECOMPILED = Path(sys.argv[2])
OUT = Path("data/reports/avia_picoty_full_guest_bootstrap.json")

TARGETS = [
    "getRegistrationGroups",
    "registerWithoutToken",
    "getTenantFiles",
    "getCposAsGuest",
    "getNearbyLocationsAsGuest",
    "getMapLocationsAsGuest",
    "getLocationAsGuest",
    "simulateLocationPricingAsGuest",
    "getLocationTariffsAsGuest",
]
CONFIG_TERMS = [
    "registrationCode", "registrationGroup", "registerCode", "tenantId", "tenant_id",
    "appDistribution", "distributionId", "runtimeVersion", "expo-runtime-version",
    "EXPO_UPDATE_URL", "expo-channel-name", "u.expo.dev", "deftpower",
]

JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?\b")
GOOGLE_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")
BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]{16,}")
SECRET_ASSIGN_RE = re.compile(
    r"(?i)((?:api[-_ ]?key|subscription[-_ ]?key|authorization|access[-_ ]?token|refresh[-_ ]?token|client[-_ ]?secret)"
    r"\s*[=:]\s*['\"]?)[^\s,'\";}]{8,}"
)
LONG_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{100,}(?![A-Za-z0-9])")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")
QUOTED_RE = re.compile(r"(['\"])(.{1,260}?)\1", re.S)
METHOD_RE = re.compile(r"['\"]method['\"]\s*[:=]\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", re.I)


def sanitize(s: str) -> str:
    s = JWT_RE.sub("<redacted-jwt>", s)
    s = GOOGLE_KEY_RE.sub("<redacted-google-api-key>", s)
    s = BEARER_RE.sub(r"\1<redacted>", s)
    s = SECRET_ASSIGN_RE.sub(r"\1<redacted>", s)
    s = LONG_TOKEN_RE.sub("<redacted-long-token>", s)
    return s


def public_literals(ctx: str) -> list[str]:
    vals: list[str] = []
    for m in QUOTED_RE.finditer(ctx):
        v = m.group(2).strip()
        low = v.lower()
        if not v or len(v) > 260:
            continue
        if (
            v.startswith("/")
            or v.startswith("https://u.expo.dev/")
            or any(k in low for k in (
                "registration", "register", "tenant", "location", "tariff",
                "distribution", "cpo", "deftpower", "runtime", "expo-channel"
            ))
        ) and v not in vals:
            vals.append(v)
    return vals[:120]


def nearest_method(ctx: str, target_pos: int) -> str | None:
    candidates = [(m.start(), m.group(1).upper()) for m in METHOD_RE.finditer(ctx)]
    before = [x for x in candidates if x[0] <= target_pos]
    if before:
        return before[-1][1]
    return candidates[0][1] if candidates else None


def target_hits(text: str, target: str) -> list[dict]:
    low = text.lower()
    needle = target.lower()
    start = 0
    hits = []
    seen = set()
    while True:
        i = low.find(needle, start)
        if i < 0:
            break
        # Generated client function bodies can be several KB before the export assignment.
        lo, hi = max(0, i - 16000), min(len(text), i + len(target) + 18000)
        raw = text[lo:hi]
        ctx = sanitize(raw)
        rel = i - lo
        lits = public_literals(ctx)
        key = (nearest_method(ctx, rel), tuple(lits[:30]), ctx[max(0, rel-300):rel+500])
        if key not in seen:
            seen.add(key)
            hits.append({
                "offset": i,
                "methodCandidate": nearest_method(ctx, rel),
                "publicLiterals": lits,
                "context": ctx,
            })
        start = i + len(needle)
        if len(hits) >= 16:
            break
    # Route-rich candidates first.
    hits.sort(key=lambda h: (
        not any(v.startswith("/") for v in h["publicLiterals"]),
        -sum(v.startswith("/") for v in h["publicLiterals"]),
    ))
    return hits[:10]


def config_hits(text: str, term: str) -> list[dict]:
    low = text.lower(); needle = term.lower(); start = 0; out = []; seen = set()
    while True:
        i = low.find(needle, start)
        if i < 0:
            break
        lo, hi = max(0, i - 5000), min(len(text), i + len(term) + 7000)
        ctx = sanitize(text[lo:hi])
        lits = public_literals(ctx)
        key = (tuple(lits[:40]), ctx[:600])
        if key not in seen:
            seen.add(key)
            out.append({"offset": i, "publicLiterals": lits, "context": ctx})
        start = i + len(needle)
        if len(out) >= 12:
            break
    return out


def resource_metadata(root: Path) -> list[dict]:
    terms = tuple(t.lower() for t in CONFIG_TERMS)
    allowed = {".xml", ".json", ".txt", ".properties", ".yml", ".yaml"}
    hits = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in allowed:
            continue
        try:
            if p.stat().st_size > 8_000_000:
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = txt.splitlines()
        for idx, line in enumerate(lines):
            if not any(t in line.lower() for t in terms):
                continue
            lo, hi = max(0, idx - 3), min(len(lines), idx + 4)
            ctx = sanitize("\n".join(lines[lo:hi]))
            hits.append({
                "file": str(p.relative_to(root)),
                "line": idx + 1,
                "context": ctx,
                "uuidCandidates": sorted(set(UUID_RE.findall(ctx))),
            })
            if len(hits) >= 250:
                return hits
    return hits


def summarize_operation(target: str, hits: list[dict]) -> dict:
    paths = []
    methods = []
    for h in hits:
        if h.get("methodCandidate") and h["methodCandidate"] not in methods:
            methods.append(h["methodCandidate"])
        for v in h["publicLiterals"]:
            if v.startswith("/") and v not in paths:
                paths.append(v)
    return {"operation": target, "methodCandidates": methods[:5], "pathFragments": paths[:60]}


def main() -> None:
    if not DECOMPILED.exists():
        raise SystemExit(f"missing full decompiled bundle: {DECOMPILED}")
    text = DECOMPILED.read_text(encoding="utf-8", errors="ignore")
    operations = {target: target_hits(text, target) for target in TARGETS}
    configs = {term: config_hits(text, term) for term in CONFIG_TERMS}
    resources = resource_metadata(DECODED) if DECODED.exists() else []

    report = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "purpose": "Public/guest Picoty-Deftpower bootstrap reconstruction from the complete app bundle; credential-like values redacted.",
        "bundleChars": len(text),
        "operationSummary": [summarize_operation(k, v) for k, v in operations.items()],
        "operations": operations,
        "configHits": configs,
        "resourceMetadata": resources,
        "uuidCandidates": sorted(set(
            u for item in resources for u in item.get("uuidCandidates", [])
        )),
        "safety": {"credentialsPersisted": False, "tokensPersisted": False},
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    # Fail closed on common credential signatures.
    forbidden = [
        r"\bAIza[0-9A-Za-z_-]{20,}\b",
        r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}",
    ]
    for pat in forbidden:
        if re.search(pat, rendered):
            raise RuntimeError(f"sensitive value survived sanitization: {pat}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "bundleChars": len(text),
        "operationHitCounts": {k: len(v) for k, v in operations.items()},
        "configHitCounts": {k: len(v) for k, v in configs.items() if v},
        "resourceMetadata": len(resources),
        "uuidCandidates": report["uuidCandidates"],
        "summary": report["operationSummary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
