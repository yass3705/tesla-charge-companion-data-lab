#!/usr/bin/env python3
"""Extract sanitized string neighborhoods around Bump Flutter tariff/location markers.

This is a static, read-only analyzer for APK files already downloaded by the workflow. It emits
only concise route/schema-like strings near known Bump functions; raw binary data and values that
look like credentials/secrets are never persisted.
"""
from __future__ import annotations

import json
import math
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT_JSON = Path("reports/bump/mobile_marker_context_latest.json")
OUT_MD = Path("reports/bump/mobile_marker_context_latest.md")
MARKERS = (
    "getTariffDetail",
    "getTariffsDetails",
    "getEvseAndLocationByIdentifier",
    "getLocationByIdentifier",
    "query_charge_location.graphql.dart",
    "fragments_charge_location.graphql.dart",
    "_onEvseTariffRequested",
    "_onTariffsRequested",
)
SENSITIVE = (
    "token", "secret", "password", "passwd", "authorization", "bearer", "cookie",
    "client_secret", "api_key", "apikey", "refresh_token", "access_token", "private_key",
)
KEEP_WORDS = (
    "tariff", "evse", "location", "charge", "connector", "price", "graphql", "query",
    "fragment", "endpoint", "route", "identifier", "api", "v1", "v2", "v3", "uri", "url",
)
PRINTABLE = re.compile(rb"[\x20-\x7e]{3,240}")
PATHISH = re.compile(r"^/?[A-Za-z0-9_.:{}%-]+(?:/[A-Za-z0-9_.:{}%-]+)+$")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,90}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = defaultdict(int)
    for c in text:
        counts[c] += 1
    n = len(text)
    return -sum((v / n) * math.log2(v / n) for v in counts.values())


def safe_candidate(text: str) -> str | None:
    text = text.strip().strip("'\"`()[]<>,;")
    text = text.split("?", 1)[0].split("#", 1)[0]
    if not 3 <= len(text) <= 180:
        return None
    low = text.casefold()
    if any(word in low for word in SENSITIVE):
        return None
    # Reject long random-looking values / certificate-ish material.
    if len(text) > 48 and entropy(text) > 4.7 and "/" not in text and "_" not in text:
        return None
    if any(word in low for word in KEEP_WORDS):
        # Keep concise identifiers, routes and GraphQL/schema terms only.
        if PATHISH.fullmatch(text) or IDENT.fullmatch(text) or any(x in low for x in ("graphql", "query", "fragment", "tariff", "evse", "location", "price")):
            return text
    if text.startswith("/") and PATHISH.fullmatch(text):
        return text
    return None


def scan_blob(data: bytes, source: str) -> list[dict]:
    rows: list[dict] = []
    for marker in MARKERS:
        needle = marker.encode()
        start = 0
        occurrence = 0
        while True:
            pos = data.find(needle, start)
            if pos < 0:
                break
            occurrence += 1
            lo = max(0, pos - 65536)
            hi = min(len(data), pos + len(needle) + 65536)
            window = data[lo:hi]
            candidates = []
            seen = set()
            for m in PRINTABLE.finditer(window):
                text = m.group().decode("utf-8", "ignore")
                safe = safe_candidate(text)
                if not safe or safe in seen:
                    continue
                seen.add(safe)
                absolute = lo + m.start()
                candidates.append({"text": safe, "relativeOffset": absolute - pos})
            # Prefer strings nearest the target marker.
            candidates.sort(key=lambda x: (abs(x["relativeOffset"]), x["relativeOffset"], x["text"].casefold()))
            rows.append({
                "marker": marker,
                "source": source,
                "occurrence": occurrence,
                "candidateCount": len(candidates),
                "nearbyCandidates": candidates[:160],
            })
            start = pos + len(needle)
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <apk-directory>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    apks = sorted(root.glob("*.apk"))
    if not apks:
        raise SystemExit("No APKs found")

    findings = []
    for apk in apks:
        with zipfile.ZipFile(apk) as zf:
            for info in zf.infolist():
                low = info.filename.casefold()
                if not low.endswith(("libapp.so", ".dart", ".js")) and "flutter_assets" not in low:
                    continue
                if info.file_size > 100_000_000:
                    continue
                try:
                    data = zf.read(info)
                except Exception:
                    continue
                findings.extend(scan_blob(data, f"{apk.name}:{info.filename}"))

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "bump-mobile-marker-context",
        "generatedAt": now_iso(),
        "method": {
            "staticOnly": True,
            "windowBytesEachSide": 65536,
            "rawBinaryPersisted": False,
            "sensitiveLookingStringsPersisted": False,
        },
        "markerCount": len(MARKERS),
        "findingCount": len(findings),
        "findings": findings,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Bump mobile marker context",
        "",
        "Sanitized static string neighborhoods around Bump tariff/location functions in Flutter AOT code.",
        "",
    ]
    if not findings:
        lines.append("No target marker was found.")
    for finding in findings:
        lines += [
            f"## `{finding['marker']}`",
            "",
            f"Source: `{finding['source']}` — occurrence {finding['occurrence']}",
            "",
        ]
        for item in finding["nearbyCandidates"][:80]:
            lines.append(f"- `{item['relativeOffset']:+d}` — `{item['text']}`")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"findingCount": len(findings), "markersFound": sorted({x['marker'] for x in findings})}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
