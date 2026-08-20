#!/usr/bin/env python3
"""Static-only FastVolt/EVOne client-context key discovery.

Downloads the publicly distributed Android packages to a temporary directory and
looks only for *key/header/symbol names* around the known read-only station
routes. No backend request is made and no candidate value, credential, account
identifier or package content is persisted.
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

APPS = {"fastvolt": "ma.fastgo", "evone": "ma.evplug"}
ROUTES = ("/app/charging_stations/", "/user/get_charging_station_details/")
OUT = Path("artifacts/morocco-fastvolt-evone-resource-keys")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

# We retain names only. These patterns intentionally target syntax-like key names.
KEY_RX = re.compile(
    r"\b(?:x[-_])?(?:business|organisation|organization|tenant|company|client)"
    r"(?:[-_](?:id|key|code|name|uuid|context|identifier))?\b",
    re.I,
)
HEADERISH_RX = re.compile(r"\b(?:headers?|requestHeaders?|defaultHeaders?|customHeaders?)\b", re.I)
METHOD_RX = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\b")
SENSITIVE_NAME_RX = re.compile(r"password|secret|token|authorization|cookie|email|phone|wallet|payment|card|account|customer", re.I)


def download(package: str, dest: Path):
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
        with zipfile.ZipFile(src) as archive:
            for info in archive.infolist():
                if ".." in Path(info.filename).parts or info.file_size > 180 * 1024 * 1024:
                    continue
                archive.extract(info, dst)
    except Exception:
        pass


def strings(path: Path):
    try:
        proc = subprocess.run(
            ["strings", "-a", "-n", "3", str(path)],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=180,
        )
        return proc.stdout.splitlines()
    except Exception:
        return []


def candidate_names(text: str):
    found = []
    for m in KEY_RX.finditer(text):
        value = m.group(0)
        if not SENSITIVE_NAME_RX.search(value):
            found.append(value)
    return found


def inspect(name: str, package: str, tmp: Path):
    pkg = tmp / f"{name}.pkg"
    fmt, size = download(package, pkg)
    result = {
        "package": package,
        "download_ok": bool(fmt),
        "download_format": fmt,
        "download_bytes": size,
        "route_hits": {},
        "global_context_key_names": {},
        "near_route_context_key_names": {},
        "near_route_header_symbols": {},
        "near_route_http_methods": {},
    }
    if not fmt:
        return result

    tree = tmp / f"{name}-tree"
    unpack(pkg, tree)
    for idx, apk in enumerate(list(tree.rglob("*.apk"))[:30]):
        unpack(apk, tree / f"apk_{idx}")

    global_keys = Counter()
    near_keys = Counter()
    near_header = Counter()
    near_methods = Counter()
    route_hits = Counter()

    for path in tree.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 150 * 1024 * 1024:
                continue
        except OSError:
            continue
        # String extraction is used for binaries too, but nothing raw is retained.
        lines = strings(path)
        if not lines:
            continue
        for line in lines:
            for key in candidate_names(line):
                global_keys[key] += 1
        for i, line in enumerate(lines):
            matched = [route for route in ROUTES if route in line]
            if not matched:
                continue
            for route in matched:
                route_hits[route] += 1
            window = lines[max(0, i - 60): min(len(lines), i + 61)]
            for item in window:
                for key in candidate_names(item):
                    near_keys[key] += 1
                for h in HEADERISH_RX.findall(item):
                    near_header[h] += 1
                for method in METHOD_RX.findall(item):
                    near_methods[method] += 1

    result["route_hits"] = dict(route_hits)
    result["global_context_key_names"] = dict(global_keys.most_common(80))
    result["near_route_context_key_names"] = dict(near_keys.most_common(80))
    result["near_route_header_symbols"] = dict(near_header.most_common(40))
    result["near_route_http_methods"] = dict(near_methods.most_common(10))
    return result


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "static_analysis_only": True,
            "backend_requests_made": False,
            "no_login": True,
            "raw_packages_persisted": False,
            "raw_strings_persisted": False,
            "raw_values_persisted": False,
            "credentials_or_ids_persisted": False,
            "only_key_and_symbol_names_persisted": True,
        },
        "apps": {},
    }
    with tempfile.TemporaryDirectory(prefix="tcc-fv-evone-keys-") as td:
        root = Path(td)
        for name, package in APPS.items():
            report["apps"][name] = inspect(name, package, root)
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: {"download_ok": v["download_ok"], "near_keys": v["near_route_context_key_names"]} for k, v in report["apps"].items()}))


if __name__ == "__main__":
    main()
