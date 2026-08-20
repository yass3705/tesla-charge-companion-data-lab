#!/usr/bin/env python3
"""Sanitized static probe around EVGO map-service symbols.

Downloads the public Android package transiently, inspects string-table offsets around
known map/service symbols, and persists only safe structural tokens (candidate paths,
hosts and identifier names). No backend requests, login, credentials, coordinates,
query values, raw package or raw bundle context are persisted.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PACKAGE = "ma.evgo.cp.app"
OUT = Path("artifacts/morocco-evgo-service-literals")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"
MARKERS = (
    "getVisibleOperators",
    "fetchCustomPinImagesFromClustersService",
    "loadClusters",
    "fetchLocations",
    "getLocations",
    "locationIds",
    "location_ids",
)
SENSITIVE = re.compile(r"(?i)(password|secret|token|authorization|cookie|email|phone|wallet|payment|card|account|customer|bearer|apikey|api_key)")
IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$.-]{2,120}$")
PATH = re.compile(r"/(?:api|app|map|maps|location|locations|operator|operators|cluster|clusters|evse|evses)[A-Za-z0-9_./{}:-]{0,180}", re.I)
HOST = re.compile(r"(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:ma|com|io|net|app|cloud|dev|tech)(?![A-Za-z0-9.-])", re.I)


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


def unzip(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as z:
            for info in z.infolist():
                if ".." in Path(info.filename).parts or info.file_size > 180 * 1024 * 1024:
                    continue
                z.extract(info, dst)
    except Exception:
        pass


def offset_strings(bundle: Path):
    proc = subprocess.run(
        ["strings", "-a", "-n", "3", "-t", "d", str(bundle)],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=240,
    )
    out = []
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*(\d+)\s+(.*)$", line)
        if m:
            out.append((int(m.group(1)), m.group(2).strip()))
    return out


def safe_token(text: str):
    if not text or len(text) > 220 or SENSITIVE.search(text):
        return None
    low = text.lower()
    interesting = any(k in low for k in (
        "endpoint", "service", "cluster", "operator", "location", "map", "evse",
        "visible", "fetch", "load", "route", "baseurl", "base_url", "host", "url",
    ))
    if not interesting:
        return None
    if IDENT.match(text):
        return text
    paths = PATH.findall(text)
    if paths:
        return paths[0][:200]
    hosts = HOST.findall(text)
    if hosts:
        return hosts[0].lower()
    return None


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
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
        "markers": {},
    }
    with tempfile.TemporaryDirectory(prefix="evgo-service-lit-") as td:
        root = Path(td)
        pkg = root / "evgo.pkg"
        fmt, size = download(pkg)
        report.update({"download_ok": bool(fmt), "download_format": fmt, "download_bytes": size})
        if not fmt:
            (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
            return
        tree = root / "tree"
        unzip(pkg, tree)
        for i, apk in enumerate(list(tree.rglob("*.apk"))[:30]):
            unzip(apk, tree / f"apk_{i}")
        bundles = list(tree.rglob("index.android.bundle")) + list(tree.rglob("main.jsbundle"))
        report["bundle_count"] = len(bundles)
        for bundle in bundles[:4]:
            strings = offset_strings(bundle)
            for marker in MARKERS:
                hit_offsets = [off for off, s in strings if marker.lower() in s.lower()]
                if not hit_offsets:
                    continue
                entry = report["markers"].setdefault(marker, {"hit_count": 0, "nearby_safe_tokens": []})
                entry["hit_count"] += len(hit_offsets)
                seen = set(entry["nearby_safe_tokens"])
                for center in hit_offsets[:12]:
                    for off, text in strings:
                        if abs(off - center) > 12000:
                            continue
                        token = safe_token(text)
                        if token and token not in seen:
                            seen.add(token)
                            entry["nearby_safe_tokens"].append(token)
                entry["nearby_safe_tokens"] = entry["nearby_safe_tokens"][:120]
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({m: v.get("nearby_safe_tokens", [])[:15] for m, v in report["markers"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
