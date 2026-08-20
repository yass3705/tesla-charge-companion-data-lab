#!/usr/bin/env python3
"""Static-only TotalEnergies Morocco / Numocity URL-construction probe.

Examines the publicly distributed Android client around the known connector route
fragments and persists only public host/path literals and syntax-like identifier
names. No backend request, login, credential, real QR, connector ID or raw bundle
context is persisted.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE = "com.namp.totalev"
MARKERS = ("/api/qr-connector", "/api/qr-connector-list", "/api/get-connector-status")
OUT = Path("artifacts/morocco-numocity-url-construction")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

URL_RX = re.compile(r"https?://[^\s\x00\"'<>\\]{5,500}", re.I)
PATH_RX = re.compile(r"/(?:[A-Za-z0-9._~-]+/?){1,10}")
IDENT_RX = re.compile(
    r"\b(?:baseURL|baseUrl|base_url|apiURL|apiUrl|api_url|endpoint|apiEndpoint|"
    r"backendURL|backendUrl|backend_url|serverURL|serverUrl|server_url|host|domain|"
    r"route|path|request|headers?|axios|fetch|client|connectorId|connector_id|qrCode|qrcode|qr)\b",
    re.I,
)
SENSITIVE_RX = re.compile(r"password|secret|token|authorization|cookie|email|phone|wallet|payment|card|account|customer|bearer", re.I)


def download(dest: Path):
    for fmt in ("XAPK", "APK"):
        try:
            req = urllib.request.Request(
                f"https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest",
                headers={"User-Agent": UA, "Accept": "*/*"},
            )
            with urllib.request.urlopen(req, timeout=120) as res:
                data = res.read()
            if len(data) > 100_000:
                dest.write_bytes(data)
                return fmt, len(data)
        except Exception:
            pass
    return None, 0


def unpack(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as archive:
            for info in archive.infolist():
                if ".." in Path(info.filename).parts or info.file_size > 180 * 1024 * 1024:
                    continue
                archive.extract(info, dst)
    except Exception:
        pass


def offset_strings(path: Path):
    try:
        proc = subprocess.run(
            ["strings", "-a", "-t", "d", "-n", "3", str(path)],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=180,
        )
    except Exception:
        return []
    out = []
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*(\d+)\s+(.*)$", line)
        if not m:
            continue
        try:
            off = int(m.group(1))
        except ValueError:
            continue
        out.append((off, m.group(2)))
    return out


def safe_url(raw: str):
    try:
        u = urlsplit(raw)
    except Exception:
        return None
    if not u.scheme or not u.hostname:
        return None
    # Strip queries/fragments/userinfo. Hosts and public paths are safe infrastructure literals.
    return f"{u.scheme}://{u.hostname}{u.path or '/'}"[:500]


def safe_path(raw: str):
    p = raw.split("?", 1)[0].split("#", 1)[0]
    if len(p) < 2 or len(p) > 220:
        return None
    if SENSITIVE_RX.search(p):
        return None
    return p


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "package": PACKAGE,
        "policy": {
            "static_analysis_only": True,
            "backend_requests_made": False,
            "no_login": True,
            "raw_package_persisted": False,
            "raw_bundle_context_persisted": False,
            "raw_values_persisted": False,
            "credentials_or_real_station_ids_persisted": False,
            "queries_and_fragments_stripped_from_urls": True,
        },
        "download_ok": False,
        "marker_hits": [],
        "nearby_public_urls": [],
        "nearby_public_paths": [],
        "nearby_identifier_names": {},
    }
    with tempfile.TemporaryDirectory(prefix="tcc-numocity-url-") as td:
        root = Path(td)
        pkg = root / "total.pkg"
        fmt, size = download(pkg)
        report.update({"download_ok": bool(fmt), "download_format": fmt, "download_bytes": size})
        if not fmt:
            (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
            return
        tree = root / "tree"
        unpack(pkg, tree)
        for idx, apk in enumerate(list(tree.rglob("*.apk"))[:30]):
            unpack(apk, tree / f"apk_{idx}")

        urls = {}
        paths = {}
        identifiers = Counter()
        hits = []
        for file in tree.rglob("*"):
            if not file.is_file():
                continue
            try:
                if file.stat().st_size > 150 * 1024 * 1024:
                    continue
            except OSError:
                continue
            rows = offset_strings(file)
            if not rows:
                continue
            marker_rows = [(idx, off, text, marker) for idx, (off, text) in enumerate(rows) for marker in MARKERS if marker in text]
            for idx, off, text, marker in marker_rows:
                hits.append({"marker": marker, "source": str(file.relative_to(tree)), "offset": off})
                # String-table proximity is more useful than arbitrary raw byte context for Hermes/RN bundles.
                for j in range(max(0, idx - 140), min(len(rows), idx + 141)):
                    noff, s = rows[j]
                    distance = abs(noff - off)
                    if SENSITIVE_RX.search(s):
                        continue
                    for raw in URL_RX.findall(s):
                        value = safe_url(raw)
                        if value:
                            urls[(value, marker)] = min(distance, urls.get((value, marker), 10**12))
                    for raw in PATH_RX.findall(s):
                        value = safe_path(raw)
                        if value and ("api" in value.lower() or "connector" in value.lower() or "status" in value.lower() or "qr" in value.lower()):
                            paths[(value, marker)] = min(distance, paths.get((value, marker), 10**12))
                    for name in IDENT_RX.findall(s):
                        if not SENSITIVE_RX.search(name):
                            identifiers[name] += 1

        report["marker_hits"] = hits[:100]
        report["nearby_public_urls"] = [
            {"value": value, "marker": marker, "distance_bytes": distance}
            for (value, marker), distance in sorted(urls.items(), key=lambda x: x[1])[:100]
        ]
        report["nearby_public_paths"] = [
            {"value": value, "marker": marker, "distance_bytes": distance}
            for (value, marker), distance in sorted(paths.items(), key=lambda x: x[1])[:120]
        ]
        report["nearby_identifier_names"] = dict(identifiers.most_common(80))

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"markers": len(report["marker_hits"]), "urls": report["nearby_public_urls"][:10], "paths": report["nearby_public_paths"][:10]}))


if __name__ == "__main__":
    main()
