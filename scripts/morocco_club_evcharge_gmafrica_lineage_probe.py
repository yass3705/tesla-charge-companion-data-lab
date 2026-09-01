#!/usr/bin/env python3
"""Compare two public GM Africa-related EV clients without contacting their backends.

The probe downloads only publicly distributed Android packages, scans them in a
temporary directory, and persists a strict allowlist of public route/domain
literals. It never stores raw packages, arbitrary bundle strings, credentials,
identifiers, station data, or response bodies.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import tempfile
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

PACKAGES = {
    "club_ev_charge": {
        "package_id": "com.namp.totalev",
        "public_listing": "https://play.google.com/store/apps/details?id=com.namp.totalev",
        "role": "target_client",
    },
    "ma_charge": {
        "package_id": "com.namp.macharge",
        "public_listing": "https://play.google.com/store/apps/details?id=com.namp.macharge",
        "role": "GM_AFRICA_public_sibling_comparison_only",
    },
}

ROUTE_MARKERS = (
    "/api/qr-connector",
    "/api/qr-connector-list",
    "/api/get-connector-status",
    "/chargestation/getstationstate",
)
SAFE_SOURCE_MARKERS = (
    "/network/api_service.dart",
    "/functions/stationFunctions.dart",
    "/models/stationModel/charge_station_detail_model.dart",
)
CONSTRUCTION_MARKERS = (
    "baseUrl",
    "baseURL",
    "apiUrl",
    "apiURL",
    "authority",
    "scheme",
    "Dio",
    "BaseOptions",
)

ALLOWED_PUBLIC_DOMAIN_SUFFIXES = (
    "numocity.com",
    "gm-africa.com",
    "totalenergies.ma",
)
DOMAIN_RX = re.compile(rb"(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:com|ma|net|io|tech)(?![A-Za-z0-9.-])", re.I)
URL_RX = re.compile(rb"https?://[^\s\x00\"'<>\\]{5,500}", re.I)
SENSITIVE_RX = re.compile(r"password|secret|token|authorization|cookie|email|phone|wallet|payment|card|account|customer|bearer", re.I)
SCAN_SUFFIXES = {".so", ".dex", ".apk", ".xml", ".json", ".arsc"}

OUT = Path("artifacts/morocco-club-evcharge-gmafrica-lineage")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/2.0)"
MAX_DOWNLOAD = 180 * 1024 * 1024
MAX_SCAN_FILE = 150 * 1024 * 1024
MAX_SCAN_FILES = 100


def download_public_package(package_id: str, destination: Path):
    for package_format in ("XAPK", "APK"):
        url = f"https://d.apkpure.com/b/{package_format}/{package_id}?version=latest"
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": UA, "Accept": "*/*"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read(MAX_DOWNLOAD + 1)
            if 100_000 < len(payload) <= MAX_DOWNLOAD:
                destination.write_bytes(payload)
                return {
                    "download_ok": True,
                    "download_format": package_format,
                    "download_bytes": len(payload),
                    "download_sha256": hashlib.sha256(payload).hexdigest(),
                }
        except Exception:
            continue
    return {
        "download_ok": False,
        "download_format": None,
        "download_bytes": 0,
        "download_sha256": None,
    }


def safe_unpack(source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                member = Path(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    continue
                if info.file_size > MAX_SCAN_FILE:
                    continue
                archive.extract(info, destination)
    except Exception:
        return


def safe_public_url(raw: bytes):
    try:
        text = raw.decode("utf-8", "ignore")
        parsed = urlsplit(text)
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    if not host or not any(host.endswith(suffix) for suffix in ALLOWED_PUBLIC_DOMAIN_SUFFIXES):
        return None
    path = parsed.path or "/"
    if SENSITIVE_RX.search(path):
        return None
    return f"{parsed.scheme.lower()}://{host}{path}"[:500]


def scan_package(package_file: Path, unpack_root: Path):
    safe_unpack(package_file, unpack_root)
    nested_apks = list(unpack_root.rglob("*.apk"))[:40]
    for index, apk in enumerate(nested_apks):
        safe_unpack(apk, unpack_root / f"apk_{index}")

    candidates = [package_file]
    for path in unpack_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size <= 0 or size > MAX_SCAN_FILE:
            continue
        if path.suffix.lower() in SCAN_SUFFIXES or path.name == "resources.arsc":
            candidates.append(path)
        if len(candidates) >= MAX_SCAN_FILES:
            break

    route_counts = Counter()
    source_marker_counts = Counter()
    construction_counts = Counter()
    domains = Counter()
    urls = Counter()
    scanned_bytes = 0
    scanned_files = 0

    for path in candidates:
        try:
            data = path.read_bytes()
        except Exception:
            continue
        scanned_files += 1
        scanned_bytes += len(data)

        for marker in ROUTE_MARKERS:
            count = data.count(marker.encode("ascii"))
            if count:
                route_counts[marker] += count
        for marker in SAFE_SOURCE_MARKERS:
            count = data.count(marker.encode("ascii"))
            if count:
                source_marker_counts[marker] += count
        for marker in CONSTRUCTION_MARKERS:
            count = data.lower().count(marker.lower().encode("ascii"))
            if count:
                construction_counts[marker] += count

        for raw_domain in DOMAIN_RX.findall(data):
            try:
                domain = raw_domain.decode("ascii").lower()
            except Exception:
                continue
            if any(domain.endswith(suffix) for suffix in ALLOWED_PUBLIC_DOMAIN_SUFFIXES):
                domains[domain] += 1

        for raw_url in URL_RX.findall(data):
            value = safe_public_url(raw_url)
            if value:
                urls[value] += 1

    return {
        "files_scanned": scanned_files,
        "bytes_scanned": scanned_bytes,
        "route_marker_counts": dict(sorted(route_counts.items())),
        "safe_source_marker_counts": dict(sorted(source_marker_counts.items())),
        "construction_marker_counts": dict(sorted(construction_counts.items())),
        "public_domain_literals": sorted(domains),
        "sanitized_public_urls": sorted(urls),
    }


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "subject": "Club EV-Charge current public-client lineage and request-construction evidence",
        "policy": {
            "static_public_client_analysis_only": True,
            "backend_requests_made": False,
            "no_login": True,
            "no_credentials": True,
            "no_user_or_account_data": True,
            "no_station_or_connector_identifiers": True,
            "raw_packages_persisted": False,
            "arbitrary_bundle_strings_persisted": False,
            "only_allowlisted_public_domains_routes_and_counts_persisted": True,
            "cross_network_station_data_reused": False,
            "sibling_client_is_not_a_production_data_source": True,
        },
        "packages": {},
        "comparison": {},
        "modeling": {
            "cpo_operator": "unresolved_station_specific",
            "site_brand": "TotalEnergies when station-specific evidence supports it",
            "app_source_access_network": "Club EV-Charge / TotalEnergies Marketing Maroc",
            "tariff_channel": "unresolved_without_native_station-specific evidence",
            "status_source": "unresolved_without_validated_public_read-only request",
            "implementation_partner": "GM AFRICA",
            "numocity_role": "unverified_current_production_backend",
        },
        "production_decision": "diagnostic_only",
        "next_step": "Use only target-client public configuration evidence to validate an anonymous read-only inventory/status request. Never transplant ma charge hosts, station data, identifiers or responses into Club EV-Charge.",
    }

    with tempfile.TemporaryDirectory(prefix="tcc-club-gmafrica-") as temp_dir:
        root = Path(temp_dir)
        for label, metadata in PACKAGES.items():
            package_path = root / f"{label}.pkg"
            download = download_public_package(metadata["package_id"], package_path)
            item = {
                **metadata,
                **download,
                "raw_package_persisted": False,
                "analysis": {
                    "files_scanned": 0,
                    "bytes_scanned": 0,
                    "route_marker_counts": {},
                    "safe_source_marker_counts": {},
                    "construction_marker_counts": {},
                    "public_domain_literals": [],
                    "sanitized_public_urls": [],
                },
            }
            if download["download_ok"]:
                item["analysis"] = scan_package(package_path, root / f"{label}_tree")
            report["packages"][label] = item

    club = report["packages"]["club_ev_charge"]["analysis"]
    sibling = report["packages"]["ma_charge"]["analysis"]
    club_routes = set(club["route_marker_counts"])
    sibling_routes = set(sibling["route_marker_counts"])
    club_domains = set(club["public_domain_literals"])
    sibling_domains = set(sibling["public_domain_literals"])

    report["comparison"] = {
        "shared_route_markers": sorted(club_routes & sibling_routes),
        "club_only_route_markers": sorted(club_routes - sibling_routes),
        "ma_charge_only_route_markers": sorted(sibling_routes - club_routes),
        "shared_public_domains": sorted(club_domains & sibling_domains),
        "club_only_public_domains": sorted(club_domains - sibling_domains),
        "ma_charge_only_public_domains": sorted(sibling_domains - club_domains),
        "template_lineage_signal": bool(club_routes & sibling_routes),
        "interpretation": (
            "Shared public route/domain literals may corroborate reusable client-template lineage only. "
            "They do not establish a working Club EV-Charge endpoint, a current backend vendor, physical CPO, "
            "station inventory, tariff channel or live status source."
        ),
    }

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "downloads": {
            label: {
                "ok": item["download_ok"],
                "bytes": item["download_bytes"],
                "sha256": item["download_sha256"],
            }
            for label, item in report["packages"].items()
        },
        "comparison": report["comparison"],
        "production_decision": report["production_decision"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
