#!/usr/bin/env python3
"""Static-only discovery around EVGO map cluster-service symbols.

Targets the public Android package ma.evgo.cp.app and records only sanitized structural
signals: candidate hosts, route-like paths and safe identifiers near cluster/map symbols.
No backend request, login, credential, query value, coordinate, raw package or raw bundle
context is persisted.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE = "ma.evgo.cp.app"
OUT = Path("artifacts/morocco-evgo-cluster-service")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

MARKERS = (
    "loadClusters",
    "fetchCustomPinImagesFromClustersService",
    "fetchLocations",
    "getLocations",
    "locationIds",
    "location_ids",
    "ClusterMarker",
)
SAFE_HINTS = (
    "cluster", "location", "map", "marker", "pin", "evse", "station", "charger",
    "bound", "viewport", "region", "north", "south", "east", "west", "zoom",
    "radius", "distance", "fetch", "load", "service", "endpoint", "host", "base",
)
BLOCK = re.compile(
    r"(token|secret|password|authorization|cookie|email|phone|payment|wallet|account|customer|bearer|apikey|api_key)",
    re.I,
)
URL_RX = re.compile(r"https?://[^\s\x00\"'<>\\]{5,500}", re.I)
HOST_RX = re.compile(
    r"(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:com|ma|io|net|app|cloud|dev|tech|org)(?::\d{2,5})?(?![A-Za-z0-9.-])",
    re.I,
)
PATH_RX = re.compile(
    r"/(?:api(?:/v\d+)?/)?[A-Za-z0-9_.:-]*(?:cluster|location|map|marker|pin|evse|station|charger|search|nearby)[A-Za-z0-9_./:{}-]{0,180}",
    re.I,
)
IDENT_RX = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]{2,100}\b")


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


def unzip_safe(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as archive:
            for info in archive.infolist():
                if ".." not in Path(info.filename).parts and info.file_size < 180 * 1024 * 1024:
                    archive.extract(info, dst)
    except Exception:
        pass


def offset_strings(path: Path):
    try:
        lines = subprocess.run(
            ["strings", "-a", "-t", "d", "-n", "3", str(path)],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=240,
        ).stdout.splitlines()
    except Exception:
        return []
    rows = []
    for line in lines:
        m = re.match(r"^\s*(\d+)\s+(.*)$", line)
        if m:
            rows.append((int(m.group(1)), m.group(2)))
    return rows


def safe_url(raw: str):
    try:
        u = urlsplit(raw)
        if not u.hostname:
            return None
        path = (u.path or "/").split("?", 1)[0]
        return f"{u.scheme}://{u.hostname}{path}"[:500]
    except Exception:
        return None


def main():
    report = {
        "schema_version": 1,
        "package": PACKAGE,
        "policy": {
            "static_analysis_only": True,
            "backend_requests_made": False,
            "no_login": True,
            "credentials_persisted": False,
            "coordinates_persisted": False,
            "query_values_persisted": False,
            "raw_package_persisted": False,
            "raw_bundle_context_persisted": False,
        },
    }
    with tempfile.TemporaryDirectory(prefix="evgo-cluster-service-") as td:
        root = Path(td)
        pkg = root / "evgo.pkg"
        fmt, size = download(pkg)
        report.update({"download_ok": bool(fmt), "download_format": fmt, "download_bytes": size})
        if not fmt:
            (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
            return
        tree = root / "tree"
        unzip_safe(pkg, tree)
        for idx, apk in enumerate(list(tree.rglob("*.apk"))[:30]):
            unzip_safe(apk, tree / f"apk_{idx}")
        bundles = [
            p for p in tree.rglob("*")
            if p.is_file() and p.name in ("index.android.bundle", "main.jsbundle", "libapp.so")
        ]
        hosts = Counter()
        urls = Counter()
        paths = Counter()
        ids = Counter()
        marker_hits = []
        nearest = []
        for bundle in bundles:
            rows = offset_strings(bundle)
            hits = [(off, text, marker) for off, text in rows for marker in MARKERS if marker.lower() in text.lower()]
            for off, _text, marker in hits:
                marker_hits.append({"marker": marker, "source": str(bundle.relative_to(tree)), "offset": off})
                # Wider byte window than previous probe to catch separately-emitted URL/config strings.
                for other_off, text in rows:
                    dist = abs(other_off - off)
                    if dist > 96_000 or BLOCK.search(text):
                        continue
                    lower = text.lower()
                    relevant = any(h in lower for h in SAFE_HINTS)
                    for raw_url in URL_RX.findall(text):
                        value = safe_url(raw_url.rstrip(".,;:)]}"))
                        if value and any(h in value.lower() for h in ("evgo", "ampeco", "cluster", "map", "location", "charge")):
                            urls[value] += 1
                            nearest.append({"marker": marker, "kind": "url", "distance_bytes": dist, "value": value})
                    for host in HOST_RX.findall(text):
                        h = host.lower()
                        if any(x in h for x in ("evgo", "ampeco", "cluster", "map", "charge")):
                            hosts[h] += 1
                            nearest.append({"marker": marker, "kind": "host", "distance_bytes": dist, "value": h})
                    if relevant:
                        for path in PATH_RX.findall(text):
                            p = path.split("?", 1)[0]
                            if not BLOCK.search(p):
                                paths[p] += 1
                                nearest.append({"marker": marker, "kind": "path", "distance_bytes": dist, "value": p})
                        for ident in IDENT_RX.findall(text):
                            il = ident.lower()
                            if not BLOCK.search(il) and any(h in il for h in SAFE_HINTS):
                                ids[ident] += 1
                                if dist <= 12_000:
                                    nearest.append({"marker": marker, "kind": "identifier", "distance_bytes": dist, "value": ident})
        # Preserve only structural names/paths and offsets, never arbitrary surrounding text.
        seen = set()
        clean_nearest = []
        for item in sorted(nearest, key=lambda x: (x["distance_bytes"], x["kind"], x["value"])):
            key = (item["marker"], item["kind"], item["value"])
            if key in seen:
                continue
            seen.add(key)
            clean_nearest.append(item)
            if len(clean_nearest) >= 250:
                break
        report.update({
            "bundle_count": len(bundles),
            "marker_hits": marker_hits[:60],
            "candidate_hosts": [{"host": k, "count": v} for k, v in hosts.most_common(80)],
            "candidate_urls": [{"url": k, "count": v} for k, v in urls.most_common(80)],
            "candidate_paths": [{"path": k, "count": v} for k, v in paths.most_common(120)],
            "safe_identifiers": [{"name": k, "count": v} for k, v in ids.most_common(160)],
            "nearest_structural_tokens": clean_nearest,
        })
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "markers": len(report.get("marker_hits", [])),
        "hosts": report.get("candidate_hosts", [])[:8],
        "paths": report.get("candidate_paths", [])[:8],
    }))


if __name__ == "__main__":
    main()
