#!/usr/bin/env python3
"""Statically inspect downloaded Bump APKs for station/tariff API clues.

The analyzer is intentionally read-only and privacy/safety conservative:
- APKs are supplied by the workflow and never committed.
- no app execution, login, credentials, charging or payment actions;
- no network requests are made by this script;
- output contains only sanitized host/path metadata and hashes, never query strings,
  headers, cookies, bearer tokens, raw APK contents or full app bundles.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PACKAGE = "bump.charge.com.app"
OUT_JSON = Path("reports/bump/mobile_api_discovery_latest.json")
OUT_MD = Path("reports/bump/mobile_api_discovery_latest.md")

KEYWORDS = (
    "api", "graphql", "station", "stations", "location", "locations", "evse",
    "connector", "connectors", "chargepoint", "charge-point", "charge_point",
    "tariff", "tariffs", "price", "prices", "pricing", "charging", "charge",
)
SENSITIVE = (
    "token", "secret", "password", "passwd", "authorization", "bearer", "cookie",
    "client_secret", "api_key", "apikey", "refresh_token", "access_token",
)
URL_RE = re.compile(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{4,500}", re.I)
PATH_RE = re.compile(
    rb"[\"'](/(?:api|graphql|v\d+|stations?|locations?|evses?|connectors?|chargepoints?|tariffs?|pricing|prices?)[A-Za-z0-9._~!$&'()*+,;=:@%/?#\[\]-]{0,300})[\"']",
    re.I,
)
ASCII_STRING_RE = re.compile(rb"[\x20-\x7e]{6,1000}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize_url(raw: str) -> tuple[str, str] | None:
    raw = raw.strip().rstrip(".,);]}'\"")
    try:
        p = urllib.parse.urlsplit(raw)
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    host = p.hostname.lower().rstrip(".")
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return None
    path = re.sub(r"/{2,}", "/", p.path or "/")
    # Never retain query/fragment because they can contain tokens or identifiers.
    return host, path[:320]


def interesting(text: str) -> bool:
    low = text.casefold()
    return any(k in low for k in KEYWORDS)


def sensitive(text: str) -> bool:
    low = text.casefold()
    return any(k in low for k in SENSITIVE)


def strings_from_bytes(data: bytes) -> Iterable[bytes]:
    # ASCII is sufficient for URL/path discovery in typical Android bundles and native libs.
    yield from ASCII_STRING_RE.findall(data)


def inspect_blob(data: bytes, source: str, urls: dict, paths: dict, markers: Counter) -> None:
    # Direct URL/path regexes catch compacted/minified code even when adjacent strings are huge.
    candidates = list(URL_RE.findall(data))
    for s in strings_from_bytes(data):
        if interesting(s.decode("utf-8", errors="ignore")):
            candidates.extend(URL_RE.findall(s))
            for m in PATH_RE.findall(s):
                path = m.decode("utf-8", errors="ignore")
                if not sensitive(path):
                    paths.setdefault(path[:320], set()).add(source)

    for raw in candidates:
        text = raw.decode("utf-8", errors="ignore")
        if not interesting(text) or sensitive(text):
            continue
        cleaned = sanitize_url(text)
        if not cleaned:
            continue
        host, path = cleaned
        key = f"https://{host}{path}"
        urls.setdefault(key, {"host": host, "path": path, "sources": set()})["sources"].add(source)

    low = data.lower()
    framework_checks = {
        "react_native_bundle": b"index.android.bundle",
        "react_native": b"reactnative",
        "flutter": b"flutter_assets",
        "retrofit": b"retrofit2",
        "apollo_graphql": b"apollo",
        "okhttp": b"okhttp",
        "firebase": b"firebase",
    }
    for key, needle in framework_checks.items():
        if needle in low:
            markers[key] += 1


def inspect_apk(apk: Path, urls: dict, paths: dict, markers: Counter) -> dict:
    meta = {
        "filename": apk.name,
        "bytes": apk.stat().st_size,
        "sha256": sha256(apk),
        "zipEntries": 0,
        "entriesScanned": 0,
    }
    try:
        with zipfile.ZipFile(apk) as zf:
            infos = zf.infolist()
            meta["zipEntries"] = len(infos)
            for info in infos:
                # Skip obviously irrelevant large media assets, but scan code/config/native libs.
                name = info.filename
                lowname = name.casefold()
                relevant = (
                    lowname.endswith((".dex", ".so", ".js", ".json", ".xml", ".txt", ".properties", ".html"))
                    or "assets/" in lowname
                    or "flutter_assets" in lowname
                    or "manifest" in lowname
                )
                if not relevant or info.file_size > 80_000_000:
                    continue
                try:
                    data = zf.read(info)
                except Exception:
                    continue
                meta["entriesScanned"] += 1
                inspect_blob(data, f"{apk.name}:{name}", urls, paths, markers)
    except zipfile.BadZipFile:
        meta["error"] = "bad_zip"
    return meta


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <apk-directory>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    apks = sorted(root.glob("*.apk"))
    if not apks:
        raise SystemExit(f"No APK files found in {root}")

    urls: dict[str, dict] = {}
    paths: dict[str, set[str]] = {}
    markers: Counter = Counter()
    apk_meta = [inspect_apk(apk, urls, paths, markers) for apk in apks]

    url_rows = []
    for key, row in sorted(urls.items()):
        url_rows.append({
            "url": key,
            "host": row["host"],
            "path": row["path"],
            "sourceCount": len(row["sources"]),
            "sources": sorted(row["sources"])[:8],
        })
    path_rows = [
        {"path": path, "sourceCount": len(srcs), "sources": sorted(srcs)[:8]}
        for path, srcs in sorted(paths.items())
        if interesting(path) and not sensitive(path)
    ]

    host_counts = Counter(r["host"] for r in url_rows)
    likely = [
        r for r in url_rows
        if any(k in (r["host"] + r["path"]).casefold() for k in ("api", "station", "evse", "tariff", "price", "graphql", "chargepoint"))
    ]

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "bump-mobile-static-api-discovery",
        "generatedAt": now_iso(),
        "package": PACKAGE,
        "method": {
            "staticAnalysisOnly": True,
            "appExecuted": False,
            "authenticatedToBump": False,
            "chargingSessionStarted": False,
            "paymentSubmitted": False,
            "queriesOrFragmentsPersisted": False,
            "apkBinariesPersisted": False,
        },
        "apks": apk_meta,
        "frameworkMarkers": dict(sorted(markers.items())),
        "hostCounts": [{"host": h, "candidateCount": n} for h, n in host_counts.most_common()],
        "candidateUrls": url_rows[:500],
        "candidatePaths": path_rows[:500],
        "likelyStationTariffCandidates": likely[:250],
        "counts": {
            "apkCount": len(apks),
            "urlCandidateCount": len(url_rows),
            "pathCandidateCount": len(path_rows),
            "likelyStationTariffCandidateCount": len(likely),
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Bump mobile static API discovery",
        "",
        "Read-only static inspection of the current Google Play APK/splits. No Bump account, app execution, charging or payment action was used.",
        "",
        "## Result",
        "",
        f"- APK/split files inspected: **{len(apks)}**",
        f"- Sanitized URL candidates: **{len(url_rows)}**",
        f"- Relative API/path candidates: **{len(path_rows)}**",
        f"- Likely station/tariff API candidates: **{len(likely)}**",
        "",
        "## Candidate hosts",
        "",
    ]
    if host_counts:
        for host, count in host_counts.most_common(30):
            lines.append(f"- `{host}` — {count} candidate(s)")
    else:
        lines.append("No relevant hostnames found.")
    lines += ["", "## Likely station/tariff candidates", ""]
    if likely:
        for row in likely[:80]:
            lines.append(f"- `{row['url']}`")
    else:
        lines.append("No likely station/tariff URL found in static strings.")
    if path_rows:
        lines += ["", "## Relative API/path candidates", ""]
        for row in path_rows[:80]:
            lines.append(f"- `{row['path']}`")
    lines += [
        "",
        "## Safety / TCC rule",
        "",
        "Static clues are discovery evidence only. No endpoint is used to publish a Bump tariff until a public/read-only station lookup is verified against official Bump station/PDC identifiers and returns an explicit driver-facing price.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
