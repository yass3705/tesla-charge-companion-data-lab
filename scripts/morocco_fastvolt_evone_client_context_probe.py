#!/usr/bin/env python3
"""Static-only client-context discovery for Morocco FastVolt and EVOne.

Purpose: identify *names* of public client context/header/field symbols around the
known read-only station routes without persisting any values, credentials, IDs,
query strings, raw APK/XAPK files, or raw bundle context.
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

OUT = Path("artifacts/morocco-fastvolt-evone-client-context")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"
APPS = {
    "fastvolt": "ma.fastgo",
    "evone": "ma.evplug",
}
ROUTE_MARKERS = (
    "/app/charging_stations/",
    "/user/get_charging_station_details/",
    "GetChargingStationsCall",
    "charging_stations",
    "get_charging_station_details",
)
CONTEXT_MARKERS = ("business", "organisation", "organization", "tenant", "company", "client")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
SAFE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,48}")
SENSITIVE = re.compile(r"(password|secret|token|bearer|authorization|cookie|email|phone|wallet|payment|card|account|customer|user_id)", re.I)


def download_package(package: str, dest: Path):
    for fmt in ("XAPK", "APK"):
        try:
            req = urllib.request.Request(
                f"https://d.apkpure.com/b/{fmt}/{package}?version=latest",
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
        with zipfile.ZipFile(src) as z:
            for info in z.infolist():
                if ".." in Path(info.filename).parts or info.file_size > 180 * 1024 * 1024:
                    continue
                z.extract(info, dst)
    except Exception:
        pass


def strings(path: Path):
    try:
        if path.name in {"libapp.so", "index.android.bundle", "main.jsbundle"}:
            p = subprocess.run(
                ["strings", "-a", "-n", "3", str(path)],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=240,
            )
            return p.stdout.splitlines()
        return path.read_text(errors="replace").splitlines()
    except Exception:
        return []


def safe_symbol_names(text: str):
    names = set()
    for name in SAFE_NAME.findall(text):
        low = name.lower()
        if SENSITIVE.search(name):
            continue
        if any(k in low for k in CONTEXT_MARKERS):
            names.add(name[:50])
    return sorted(names)


def inspect(name: str, package: str, root: Path):
    pkg = root / f"{name}.pkg"
    fmt, size = download_package(package, pkg)
    rec = {"package": package, "download_ok": bool(fmt), "download_format": fmt, "download_bytes": size}
    if not fmt:
        return rec
    tree = root / f"{name}-tree"
    unpack(pkg, tree)
    for i, apk in enumerate(list(tree.rglob("*.apk"))[:30]):
        unpack(apk, tree / f"apk_{i}")

    lines = []
    for path in tree.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 150 * 1024 * 1024:
                continue
        except OSError:
            continue
        if path.name in {"libapp.so", "index.android.bundle", "main.jsbundle", "app.config"} or path.suffix.lower() in {".json", ".js", ".txt", ".xml"}:
            lines.extend(strings(path))

    route_counts = {m: 0 for m in ROUTE_MARKERS}
    context_counts = {m: 0 for m in CONTEXT_MARKERS}
    method_near_route = {m: 0 for m in METHODS}
    safe_names = set()

    for idx, line in enumerate(lines):
        low = line.lower()
        for marker in ROUTE_MARKERS:
            if marker.lower() in low:
                route_counts[marker] += 1
                # Inspect only a small local window and retain symbol names/counts, never raw text.
                window = " ".join(lines[max(0, idx - 4): min(len(lines), idx + 5)])
                for method in METHODS:
                    method_near_route[method] += len(re.findall(rf"\b{method}\b", window, re.I))
                safe_names.update(safe_symbol_names(window))
        for marker in CONTEXT_MARKERS:
            context_counts[marker] += low.count(marker)

    rec.update({
        "route_marker_counts": route_counts,
        "context_keyword_counts": context_counts,
        "http_method_counts_near_route_markers": method_near_route,
        "safe_context_symbol_names_near_routes": sorted(safe_names)[:120],
        "interpretation_note": "Only symbol/header/field-like names are persisted; no context values or identifiers are retained.",
    })
    return rec


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "static_analysis_only": True,
            "backend_requests_made": False,
            "no_login": True,
            "raw_packages_persisted": False,
            "raw_bundle_context_persisted": False,
            "raw_context_values_persisted": False,
            "credentials_or_ids_persisted": False,
        },
        "apps": {},
    }
    with tempfile.TemporaryDirectory(prefix="tcc-ma-client-context-") as td:
        root = Path(td)
        for name, package in APPS.items():
            report["apps"][name] = inspect(name, package, root)
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: {"download_ok": v.get("download_ok"), "safe_names": v.get("safe_context_symbol_names_near_routes", [])} for k, v in report["apps"].items()}))


if __name__ == "__main__":
    main()
