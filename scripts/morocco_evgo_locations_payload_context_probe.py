#!/usr/bin/env python3
"""Sanitized static probe for the EVGO/AMPECO /app/locations POST payload shape.

Downloads the publicly distributed Android package into a temporary directory, extracts the
React-Native bundle, and records only route-adjacent method/payload field signals. No login,
backend request, credential, token, raw bundle, package, or raw context is persisted.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PACKAGE = "ma.evgo.cp.app"
OUT = Path("artifacts/morocco-evgo-locations-payload-context")
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.8)"

MARKERS = [
    "/app/locations",
    "app/locations",
    "locations/withEVSE",
    "locations/withEVSEIdentifier",
]
FIELD_WORDS = [
    "lat", "lng", "latitude", "longitude", "north", "south", "east", "west",
    "northEast", "northWest", "southEast", "southWest", "northeast", "southwest",
    "bounds", "boundingBox", "bbox", "viewport", "region", "mapRegion", "center",
    "radius", "distance", "zoom", "filters", "filter", "connectorTypes", "connectors",
    "power", "powerFrom", "powerTo", "statuses", "status", "available", "occupied",
    "facilities", "operators", "operator", "locationIds", "ids", "query",
]
METHOD_WORDS = ["post", "get", "put", "patch", "delete"]
SENSITIVE_RX = re.compile(r"(?i)(token|secret|authorization|cookie|password|email|phone|account|payment|card)")


def download(dest: Path) -> tuple[str | None, int]:
    for fmt in ("XAPK", "APK"):
        url = f"https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=120) as res:
                data = res.read()
            if len(data) > 100_000:
                dest.write_bytes(data)
                return fmt, len(data)
        except Exception:
            pass
    return None, 0


def unpack(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as zf:
            for info in zf.infolist():
                if ".." in Path(info.filename).parts or info.file_size > 180 * 1024 * 1024:
                    continue
                zf.extract(info, dest)
    except Exception:
        return


def locate_bundle(root: Path) -> Path | None:
    for apk in list(root.rglob("*.apk"))[:40]:
        sub = root / ("apk_" + str(abs(hash(str(apk))) % 1_000_000))
        unpack(apk, sub)
    candidates = list(root.rglob("index.android.bundle")) + list(root.rglob("main.jsbundle"))
    return candidates[0] if candidates else None


def count_word(text: str, word: str) -> int:
    return len(re.findall(r"(?i)(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])", text))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "package": PACKAGE,
        "policy": {
            "static_analysis_only": True,
            "backend_requests_made": False,
            "no_login": True,
            "no_credentials": True,
            "raw_package_persisted": False,
            "raw_bundle_persisted": False,
            "raw_context_persisted": False,
        },
        "download_ok": False,
        "route_signal_count": {},
        "nearby_method_counts": {},
        "nearby_payload_field_counts": {},
        "field_cooccurrence_windows": [],
    }
    with tempfile.TemporaryDirectory(prefix="tcc-evgo-payload-") as tmp:
        root = Path(tmp)
        package_file = root / "evgo.pkg"
        fmt, size = download(package_file)
        result["download_format"] = fmt
        result["download_bytes"] = size
        result["download_ok"] = bool(fmt)
        if fmt:
            unpack(package_file, root / "unpacked")
            bundle = locate_bundle(root / "unpacked")
            if bundle:
                text = bundle.read_text(errors="replace")
                low = text.lower()
                for marker in MARKERS:
                    result["route_signal_count"][marker] = low.count(marker.lower())
                windows = []
                for marker in MARKERS:
                    start = 0
                    while len(windows) < 80:
                        idx = low.find(marker.lower(), start)
                        if idx < 0:
                            break
                        lo = max(0, idx - 1800)
                        hi = min(len(text), idx + len(marker) + 1800)
                        chunk = text[lo:hi]
                        if not SENSITIVE_RX.search(chunk):
                            fields = {w: count_word(chunk, w) for w in FIELD_WORDS if count_word(chunk, w)}
                            methods = {w: count_word(chunk, w) for w in METHOD_WORDS if count_word(chunk, w)}
                            if fields or methods:
                                windows.append({"marker": marker, "fields": fields, "methods": methods})
                        start = idx + len(marker)
                field_totals = {}
                method_totals = {}
                for win in windows:
                    for k, v in win["fields"].items():
                        field_totals[k] = field_totals.get(k, 0) + v
                    for k, v in win["methods"].items():
                        method_totals[k] = method_totals.get(k, 0) + v
                result["nearby_payload_field_counts"] = dict(sorted(field_totals.items(), key=lambda x: (-x[1], x[0])))
                result["nearby_method_counts"] = dict(sorted(method_totals.items(), key=lambda x: (-x[1], x[0])))
                result["field_cooccurrence_windows"] = windows[:30]
                result["bundle_found"] = True
            else:
                result["bundle_found"] = False
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "download_ok": result["download_ok"],
        "bundle_found": result.get("bundle_found"),
        "route_signal_count": result["route_signal_count"],
        "top_fields": list(result["nearby_payload_field_counts"].items())[:12],
        "methods": result["nearby_method_counts"],
    }))


if __name__ == "__main__":
    main()
