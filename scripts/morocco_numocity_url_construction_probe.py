#!/usr/bin/env python3
"""Static-only TotalEnergies Morocco / Numocity URL-construction probe.

Examines the publicly distributed Android client around known connector/station-state routes and the
public Numocity hostname. Persists only public host/path literals, HTTP-method-like syntax markers,
safe URL-construction symbol names, safe Numocity domain literals and identifier names. No backend
request, login, credential, real QR, connector/station ID or raw bundle context is persisted.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE = "com.namp.totalev"
MARKERS = (
    "/api/qr-connector",
    "/api/qr-connector-list",
    "/api/get-connector-status",
    "/chargestation/getstationstate",
)
HOST_MARKERS = ("csmstotalenergiesma.numocity.com", "numocity.com")
CONSTRUCTION_MARKERS = (
    "Uri.parse", "Uri.http", "Uri.https", "baseUrl", "baseURL", "apiUrl", "apiURL",
    "ApiClient", "Dio", "BaseOptions", "path", "authority", "scheme", "host",
)
METHOD_MARKERS = (
    "GET", "POST", "PUT", "PATCH", "DELETE",
    ".get(", ".post(", ".put(", ".patch(", ".delete(",
    "dio.get", "dio.post", "dio.put", "dio.patch", "dio.delete",
)
OUT = Path("artifacts/morocco-numocity-url-construction")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.5)"

URL_RX = re.compile(r"https?://[^\s\x00\"'<>\\]{5,500}", re.I)
HOST_RX = re.compile(r"(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:com|ma|net|tech|io)(?![A-Za-z0-9.-])", re.I)
NUMOCITY_DOMAIN_RX = re.compile(r"(?:[A-Za-z0-9-]+\.)*numocity\.com", re.I)
BINARY_NUMOCITY_RX = re.compile(rb"(?:[A-Za-z0-9-]+\.)*numocity\.com", re.I)
PATH_RX = re.compile(r"/(?:[A-Za-z0-9._~-]+/?){1,10}")
IDENT_RX = re.compile(
    r"\b(?:baseURL|baseUrl|base_url|apiURL|apiUrl|api_url|endpoint|apiEndpoint|"
    r"backendURL|backendUrl|backend_url|serverURL|serverUrl|server_url|host|domain|"
    r"authority|scheme|route|path|request|headers?|axios|fetch|client|ApiClient|Dio|"
    r"BaseOptions|connectorId|connector_id|stationId|station_id|qrCode|qrcode|qr)\b",
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
    return f"{u.scheme}://{u.hostname}{u.path or '/'}"[:500]


def safe_path(raw: str):
    p = raw.split("?", 1)[0].split("#", 1)[0]
    if len(p) < 2 or len(p) > 220 or SENSITIVE_RX.search(p):
        return None
    return p


def keep_path(value: str) -> bool:
    low = value.lower()
    return any(k in low for k in ("api", "connector", "status", "qr", "station", "charge", "location", "mobile", "app"))


def binary_domains_near_marker(path: Path, marker: str, radius: int = 512) -> list[str]:
    """Recover only public *.numocity.com literals from raw bytes around a known public route.

    Two harmless normalizations are tried: raw ASCII and NUL-stripped bytes, the latter covering
    UTF-16-ish/static packing where printable hostname labels may be separated by zero bytes.
    No arbitrary context is returned.
    """
    try:
        data = path.read_bytes()
    except Exception:
        return []
    needle = marker.encode("ascii", "ignore")
    if not needle:
        return []
    found: set[str] = set()
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            break
        window = data[max(0, pos - radius): min(len(data), pos + len(needle) + radius)]
        for candidate in (window, window.replace(b"\x00", b"")):
            for m in BINARY_NUMOCITY_RX.findall(candidate):
                try:
                    host = m.decode("ascii").lower()
                except Exception:
                    continue
                if host.endswith("numocity.com") and len(host) <= 120:
                    found.add(host)
        start = pos + len(needle)
    return sorted(found)


def main():
    report = {
        "schema_version": 6,
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
            "method_detection_is_static_signal_only": True,
            "construction_detection_is_static_signal_only": True,
            "near_route_numocity_domains_are_public_domain_literals_only": True,
            "binary_domain_recovery_persists_public_numocity_hosts_only": True,
        },
        "download_ok": False,
        "marker_hits": [],
        "host_marker_hits": [],
        "nearby_public_urls": [],
        "nearby_public_hosts": [],
        "nearby_public_paths": [],
        "near_host_public_paths": [],
        "near_route_numocity_domains": {},
        "binary_numocity_domains_by_route": {},
        "nearby_identifier_names": {},
        "construction_marker_counts": {},
        "construction_marker_counts_by_route": {},
        "method_marker_counts_by_route": {},
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
        hosts = {}
        paths = {}
        host_paths = {}
        numocity_domains_by_route = defaultdict(Counter)
        binary_domains_by_route = defaultdict(Counter)
        identifiers = Counter()
        constructions = Counter()
        constructions_by_route = defaultdict(Counter)
        methods_by_route = defaultdict(Counter)
        hits = []
        host_hits = []

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
            host_rows = [(idx, off, text, marker) for idx, (off, text) in enumerate(rows) for marker in HOST_MARKERS if marker in text]

            present_markers = sorted({marker for _idx, _off, _text, marker in marker_rows})
            for marker in present_markers:
                for host in binary_domains_near_marker(file, marker):
                    binary_domains_by_route[marker][host] += 1

            for _idx, off, _text, marker in host_rows:
                host_hits.append({"marker": marker, "source": str(file.relative_to(tree)), "offset": off})

            for idx, off, text, marker in marker_rows:
                hits.append({"marker": marker, "source": str(file.relative_to(tree)), "offset": off})
                for j in range(max(0, idx - 220), min(len(rows), idx + 221)):
                    noff, s = rows[j]
                    distance = abs(noff - off)
                    if SENSITIVE_RX.search(s):
                        continue
                    for raw in URL_RX.findall(s):
                        value = safe_url(raw)
                        if value:
                            urls[(value, marker)] = min(distance, urls.get((value, marker), 10**12))
                    for raw in HOST_RX.findall(s):
                        value = raw.lower()
                        hosts[(value, marker)] = min(distance, hosts.get((value, marker), 10**12))
                    if distance <= 1024:
                        for domain in NUMOCITY_DOMAIN_RX.findall(s):
                            numocity_domains_by_route[marker][domain.lower()] += 1
                    for raw in PATH_RX.findall(s):
                        value = safe_path(raw)
                        if value and keep_path(value):
                            paths[(value, marker)] = min(distance, paths.get((value, marker), 10**12))
                    for name in IDENT_RX.findall(s):
                        if not SENSITIVE_RX.search(name):
                            identifiers[name] += 1
                    for cm in CONSTRUCTION_MARKERS:
                        if cm.lower() in s.lower():
                            constructions[cm] += 1
                            if distance <= 1024:
                                constructions_by_route[marker][cm] += 1
                    if distance <= 1024:
                        low = s.lower()
                        for mm in METHOD_MARKERS:
                            if mm.lower() in low:
                                methods_by_route[marker][mm] += 1

            for idx, off, text, marker in host_rows:
                for j in range(max(0, idx - 350), min(len(rows), idx + 351)):
                    noff, s = rows[j]
                    distance = abs(noff - off)
                    if SENSITIVE_RX.search(s):
                        continue
                    for raw in PATH_RX.findall(s):
                        value = safe_path(raw)
                        if value and keep_path(value):
                            key = (value, marker)
                            host_paths[key] = min(distance, host_paths.get(key, 10**12))
                    for cm in CONSTRUCTION_MARKERS:
                        if cm.lower() in s.lower():
                            constructions[cm] += 1

        report["marker_hits"] = hits[:120]
        report["host_marker_hits"] = host_hits[:100]
        report["nearby_public_urls"] = [
            {"value": value, "marker": marker, "distance_bytes": distance}
            for (value, marker), distance in sorted(urls.items(), key=lambda x: x[1])[:100]
        ]
        report["nearby_public_hosts"] = [
            {"value": value, "marker": marker, "distance_bytes": distance}
            for (value, marker), distance in sorted(hosts.items(), key=lambda x: x[1])[:100]
        ]
        report["nearby_public_paths"] = [
            {"value": value, "marker": marker, "distance_bytes": distance}
            for (value, marker), distance in sorted(paths.items(), key=lambda x: x[1])[:140]
        ]
        report["near_host_public_paths"] = [
            {"value": value, "host_marker": marker, "distance_bytes": distance}
            for (value, marker), distance in sorted(host_paths.items(), key=lambda x: x[1])[:180]
        ]
        report["near_route_numocity_domains"] = {
            route: dict(counts.most_common()) for route, counts in sorted(numocity_domains_by_route.items())
        }
        report["binary_numocity_domains_by_route"] = {
            route: dict(counts.most_common()) for route, counts in sorted(binary_domains_by_route.items())
        }
        report["nearby_identifier_names"] = dict(identifiers.most_common(100))
        report["construction_marker_counts"] = dict(constructions.most_common())
        report["construction_marker_counts_by_route"] = {
            route: dict(counts.most_common()) for route, counts in sorted(constructions_by_route.items())
        }
        report["method_marker_counts_by_route"] = {
            route: dict(counts.most_common()) for route, counts in sorted(methods_by_route.items())
        }

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "markers": len(report["marker_hits"]),
        "host_markers": len(report["host_marker_hits"]),
        "urls": report["nearby_public_urls"][:8],
        "host_paths": report["near_host_public_paths"][:12],
        "numocity_domains": report["near_route_numocity_domains"],
        "binary_numocity_domains": report["binary_numocity_domains_by_route"],
        "construction_by_route": report["construction_marker_counts_by_route"],
        "methods": report["method_marker_counts_by_route"],
    }))


if __name__ == "__main__":
    main()
