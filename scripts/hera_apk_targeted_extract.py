#!/usr/bin/env python3
"""Extract only sanitized HERA API/config evidence from the public app bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

OFFICIAL_MARKERS = (
    "heraricarica-mobileapp.gruppohera.it",
    "heraricarica-identity.gruppohera.it",
    "heraricarica.gruppohera.it",
    "ev-driver-app-hera.gridedge-dev.sidg-clo.siemens.cloud",
    "ev-driver-customer-hera.gridedge-dev.sidg-clo.siemens.cloud",
)
KEYWORDS = (
    "tariff", "tariffe", "price", "pricing", "offer", "offerta", "rate", "flat",
    "station", "chargingstation", "evse", "connector", "location", "poi", "charger",
    "roaming", "contract", "customer", "driver", "penalty", "parking", "idle",
    "consumption", "consumo", "kwh", "mobility", "ricarica",
)
SENSITIVE_KEYS = (
    "secret", "password", "passwd", "access_token", "refresh_token", "private_key",
    "payment_token", "credit_card", "authorization", "bearer",
)
URL_RE = re.compile(r"https?://[^\s\"'<>\\]{4,500}", re.I)
QUOTED_RE = re.compile(r"(?P<q>[\"'])(?P<s>(?:\\.|(?!\1).){1,300})(?P=q)", re.S)
LONG_SECRET_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-+/=]{40,}(?![A-Za-z0-9])")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{5,})?\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
QUERY_VALUE_RE = re.compile(r"([?&][A-Za-z0-9_.-]{1,80}=)[^&#\s\"']+")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_text(value: str) -> str:
    value = JWT_RE.sub("<redacted-jwt>", value)
    value = EMAIL_RE.sub("<redacted-email>", value)
    value = QUERY_VALUE_RE.sub(r"\1<redacted>", value)
    value = LONG_SECRET_RE.sub("<redacted-long-value>", value)
    return value.replace("\x00", " ").strip()


def sensitive(value: str) -> bool:
    low = value.casefold()
    return any(term in low for term in SENSITIVE_KEYS)


def normalize_url(raw: str) -> str | None:
    raw = raw.rstrip(".,;:)]}>\\\"'")
    try:
        p = urlsplit(raw)
    except ValueError:
        return None
    if p.scheme.lower() not in {"http", "https"} or not p.hostname or p.username or p.password:
        return None
    # Query strings are intentionally discarded; they may contain user or app credentials.
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", "", ""))


def redact_json(value: Any, key: str = "") -> Any:
    if sensitive(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): redact_json(v, str(k)) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, list):
        return [redact_json(v, key) for v in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def useful_literal(value: str) -> bool:
    if not value or len(value) > 300 or sensitive(value):
        return False
    low = value.casefold()
    if not any(k in low for k in KEYWORDS):
        return False
    # Keep likely routes, resource names and API model/property literals; drop prose/library diagnostics.
    if any(ch.isspace() for ch in value) and "/" not in value and "." not in value:
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()

    configs: dict[str, Any] = {}
    official_urls: set[str] = set()
    host_contexts: list[dict[str, Any]] = []
    literals: dict[tuple[str, str], int] = {}
    scanned: list[dict[str, Any]] = []
    redactions = 0

    with zipfile.ZipFile(ns.apk) as zf:
        for info in zf.infolist():
            name = info.filename
            low_name = name.casefold()
            if not low_name.startswith("assets/public/"):
                continue
            if not low_name.endswith((".js", ".json", ".txt", ".html", ".properties")):
                continue
            if info.file_size > 8_000_000:
                continue
            raw = zf.read(info)
            text = raw.decode("utf-8", errors="replace")
            scanned.append({"path": name, "size": info.file_size, "sha256": sha256(raw)})

            if low_name.endswith(".json") and "/assets/config/" in low_name:
                try:
                    configs[name] = redact_json(json.loads(text))
                except json.JSONDecodeError:
                    configs[name] = {"parseError": True, "sha256": sha256(raw), "size": info.file_size}

            for match in URL_RE.finditer(text):
                url = normalize_url(match.group(0))
                if url and any(marker in (urlsplit(url).hostname or "") for marker in OFFICIAL_MARKERS):
                    official_urls.add(url)

            low_text = text.casefold()
            for marker in OFFICIAL_MARKERS:
                start = 0
                while True:
                    pos = low_text.find(marker, start)
                    if pos < 0:
                        break
                    left = max(0, pos - 450)
                    right = min(len(text), pos + len(marker) + 650)
                    context = sanitize_text(text[left:right])
                    if sensitive(context):
                        # Preserve only URL/route-bearing contexts; redact assignments around sensitive labels.
                        context = re.sub(
                            r"(?i)(secret|password|access_token|refresh_token|authorization|bearer)[^,;}]{0,160}",
                            r"\1:<redacted>",
                            context,
                        )
                        redactions += 1
                    host_contexts.append({"source": name, "marker": marker, "offset": pos, "context": context})
                    start = pos + len(marker)

            for match in QUOTED_RE.finditer(text):
                literal = match.group("s")
                try:
                    literal = bytes(literal, "utf-8").decode("unicode_escape", errors="replace")
                except Exception:
                    pass
                literal = sanitize_text(literal)
                if useful_literal(literal):
                    literals[(name, literal)] = literals.get((name, literal), 0) + 1

    # Dedupe equal contexts produced by repeated bundled constants.
    dedup_contexts: list[dict[str, Any]] = []
    seen_contexts: set[str] = set()
    for row in sorted(host_contexts, key=lambda r: (r["source"], r["marker"], r["offset"])):
        key = sha256(row["context"].encode("utf-8"))
        if key in seen_contexts:
            continue
        seen_contexts.add(key)
        dedup_contexts.append(row)

    literal_rows = [
        {"source": source, "value": value, "occurrences": count}
        for (source, value), count in literals.items()
    ]
    literal_rows.sort(key=lambda r: (r["value"].casefold(), r["source"]))

    report = {
        "schemaVersion": "1.0.0",
        "dataset": "hera-ricarica-targeted-public-bundle-extraction",
        "country": "IT",
        "application": {
            "package": "com.siemens.hera.mobility",
            "versionName": "6.2.15",
            "versionCode": "62015",
            "apkSha256": sha256(ns.apk.read_bytes()),
        },
        "configs": configs,
        "officialUrls": sorted(official_urls),
        "officialHostContexts": dedup_contexts,
        "relevantLiterals": literal_rows,
        "scan": {"files": scanned, "fileCount": len(scanned)},
        "safety": {
            "queryStringsPersisted": False,
            "sensitiveKeyValuesPersisted": False,
            "redactionsApplied": redactions,
            "userAccountUsed": False,
            "networkRequestsMadeByExtractor": False,
        },
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    low = serialized.casefold()
    forbidden = ("access_token=", "refresh_token=", "authorization: bearer", "client_secret=")
    if any(value in low for value in forbidden):
        raise RuntimeError("sanitization gate failed")
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "officialUrls": len(official_urls),
        "hostContexts": len(dedup_contexts),
        "relevantLiterals": len(literal_rows),
        "configFiles": len(configs),
        "redactions": redactions,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
