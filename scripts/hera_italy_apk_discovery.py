#!/usr/bin/env python3
"""Inspect the pinned public Hera Ricarica Android APK without exposing secrets.

The report is intentionally sanitized: it records package/signing identity, public
URL/host/path candidates and read-only HTTP probe metadata. Values that resemble
credentials, access tokens, payment data or user identifiers are never emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import socket
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import requests
from androguard.core.apk import APK

PACKAGE = "com.siemens.hera.mobility"
VERSION_NAME = "6.2.15"
VERSION_CODE = "62015"
APK_SHA256 = "4300171fe767b0a79f4edc41dc05aad5563308630cabf97247a7dff7e80092c0"

URL_RE = re.compile(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%{}-]{4,500}", re.I)
ASCII_RE = re.compile(rb"[\x20-\x7e]{4,500}")
PATH_RE = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%{}\-/]{2,240}$")

RELEVANT_TERMS = (
    "api", "tariff", "tariffe", "price", "pricing", "rate", "offerta", "offer",
    "flat", "consumo", "charging", "charger", "station", "evse", "connector",
    "ocpi", "oauth", "mobility", "ricarica", "hera", "contract", "penalt",
    "parking", "idle", "kwh", "minute", "map", "location",
)
SENSITIVE_TERMS = (
    "client_secret", "secret", "api_key", "apikey", "authorization", "bearer",
    "access_token", "refresh_token", "password", "passwd", "payment_token",
    "credit_card", "private_key", "session_token",
)
UNSAFE_PROBE_TERMS = (
    "start", "stop", "delete", "remove", "activate", "deactivate", "payment",
    "checkout", "purchase", "session", "command", "remote", "token", "oauth",
    "login", "logout", "password", "register", "signup", "reset",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def cert_fingerprints(apk: APK) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for cert in apk.get_certificates():
        der = cert.dump()
        result.append(
            {
                "md5": hashlib.md5(der).hexdigest(),  # nosec: identity fingerprint only
                "sha1": hashlib.sha1(der).hexdigest(),  # nosec: identity fingerprint only
                "sha256": hashlib.sha256(der).hexdigest(),
            }
        )
    return sorted(result, key=lambda row: row["sha256"])


def strip_trailing_punctuation(value: str) -> str:
    return value.rstrip(".,;:)]}>\\\"'")


def normalize_url(value: str) -> str | None:
    value = strip_trailing_punctuation(value.strip())
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    if parts.username or parts.password:
        return None
    host = parts.hostname.lower().rstrip(".")
    try:
        port = parts.port
    except ValueError:
        return None
    netloc = host
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parts.path or "/"
    if len(path) > 300:
        return None
    # Query strings may contain API keys, user IDs or one-time values: never persist them.
    return urlunsplit((parts.scheme.lower(), netloc, path, "", ""))


def looks_sensitive(value: str) -> bool:
    lowered = value.casefold()
    if any(term in lowered for term in SENSITIVE_TERMS):
        # Mere field names are safe; values/assignments are not.
        return any(marker in value for marker in ("=", ":", " ")) or len(value) > 40
    return False


def extract_ascii_strings(blobs: Iterable[bytes]) -> tuple[set[str], Counter[str], int]:
    urls: set[str] = set()
    endpoint_paths: Counter[str] = Counter()
    redacted = 0
    for blob in blobs:
        for match in URL_RE.finditer(blob):
            raw = match.group(0).decode("ascii", errors="ignore")
            normalized = normalize_url(raw)
            if normalized:
                urls.add(normalized)
        for match in ASCII_RE.finditer(blob):
            text = match.group(0).decode("ascii", errors="ignore").strip()
            if not text or looks_sensitive(text):
                redacted += 1
                continue
            lowered = text.casefold()
            if not any(term in lowered for term in RELEVANT_TERMS):
                continue
            if PATH_RE.fullmatch(text):
                endpoint_paths[text.split("?", 1)[0]] += 1
    return urls, endpoint_paths, redacted


def candidate_blobs(apk_path: Path, apk: APK) -> tuple[list[bytes], dict[str, Any]]:
    blobs: list[bytes] = []
    scanned_files: list[dict[str, Any]] = []
    with zipfile.ZipFile(apk_path) as archive:
        for info in archive.infolist():
            name = info.filename
            lowered = name.casefold()
            scan = (
                lowered.endswith((".dex", ".xml", ".json", ".txt", ".properties", ".html", ".js"))
                or lowered in {"resources.arsc", "androidmanifest.xml"}
            )
            if not scan or info.file_size > 80_000_000:
                continue
            data = archive.read(info)
            blobs.append(data)
            scanned_files.append({"path": name, "size": info.file_size, "sha256": sha256_bytes(data)})

    resource_scan_error: str | None = None
    try:
        resources = apk.get_android_resources()
        if resources is not None:
            raw = resources.get_string_resources(PACKAGE, "\x00\x00")
            if isinstance(raw, str):
                raw = raw.encode("utf-8", errors="replace")
            if isinstance(raw, bytes):
                blobs.append(raw)
    except Exception as exc:  # best-effort enrichment; ZIP/Dex scanning remains authoritative
        resource_scan_error = f"{type(exc).__name__}: {exc}"

    return blobs, {
        "files": scanned_files,
        "fileCount": len(scanned_files),
        "resourceStringScanError": resource_scan_error,
    }


def is_public_host(host: str) -> bool:
    lowered = host.casefold()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith((".local", ".internal")):
        return False
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def safe_probe_candidate(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or not is_public_host(parts.hostname):
        return False
    lowered = parts.path.casefold()
    if any(term in lowered for term in UNSAFE_PROBE_TERMS):
        return False
    return True


def probe_urls(urls: list[str], limit: int) -> list[dict[str, Any]]:
    candidates: list[str] = []
    seen: set[str] = set()
    for url in urls:
        parts = urlsplit(url)
        root = urlunsplit(("https", parts.netloc, "/", "", ""))
        for candidate in (root, url):
            if candidate not in seen and safe_probe_candidate(candidate):
                seen.add(candidate)
                candidates.append(candidate)
    candidates = candidates[:limit]

    session = requests.Session()
    session.headers.update({"User-Agent": f"Hera-Ricarica-public-audit/{VERSION_NAME}"})
    results: list[dict[str, Any]] = []
    for url in candidates:
        row: dict[str, Any] = {"url": url}
        try:
            response = session.get(url, timeout=(8, 15), allow_redirects=True, stream=True)
            row.update(
                {
                    "status": response.status_code,
                    "contentType": response.headers.get("content-type"),
                    "contentLength": response.headers.get("content-length"),
                    "finalUrl": normalize_url(response.url),
                    "redirectCount": len(response.history),
                }
            )
            response.close()
        except requests.RequestException as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        results.append(row)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-limit", type=int, default=40)
    args = parser.parse_args()

    apk_bytes = args.apk.read_bytes()
    actual_sha = sha256_bytes(apk_bytes)
    if actual_sha != APK_SHA256:
        raise RuntimeError(f"unexpected APK sha256 {actual_sha}")

    apk = APK(str(args.apk))
    package = apk.get_package()
    version_name = str(apk.get_androidversion_name())
    version_code = str(apk.get_androidversion_code())
    if package != PACKAGE:
        raise RuntimeError(f"unexpected package {package}")
    if version_name != VERSION_NAME or version_code != VERSION_CODE:
        raise RuntimeError(f"unexpected version {version_name} ({version_code})")

    blobs, scan = candidate_blobs(args.apk, apk)
    urls, paths, redacted_count = extract_ascii_strings(blobs)
    sorted_urls = sorted(urls)
    hosts = sorted({urlsplit(url).hostname for url in sorted_urls if urlsplit(url).hostname})

    report = {
        "schemaVersion": "1.0.0",
        "dataset": "hera-ricarica-apk-public-discovery",
        "country": "IT",
        "application": {
            "package": package,
            "versionName": version_name,
            "versionCode": version_code,
            "apkSha256": actual_sha,
            "apkSize": len(apk_bytes),
            "certificates": cert_fingerprints(apk),
            "signing": {
                "v1": apk.is_signed_v1(),
                "v2": apk.is_signed_v2(),
                "v3": apk.is_signed_v3(),
            },
        },
        "discovery": {
            "urls": sorted_urls,
            "hosts": hosts,
            "endpointPaths": [
                {"path": path, "occurrences": count}
                for path, count in sorted(paths.items(), key=lambda item: (-item[1], item[0]))
            ],
            "redactedStringCount": redacted_count,
            "scan": scan,
        },
        "readOnlyProbes": probe_urls(sorted_urls, max(0, args.probe_limit)),
        "safety": {
            "queryStringsPersisted": False,
            "credentialLikeValuesPersisted": False,
            "httpMethod": "GET",
            "stateChangingPathsExcluded": True,
            "privateHostsExcluded": True,
            "userAccountUsed": False,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "package": package,
        "version": version_name,
        "hosts": hosts,
        "urlCount": len(sorted_urls),
        "endpointPathCount": len(paths),
        "probeCount": len(report["readOnlyProbes"]),
        "redactedStringCount": redacted_count,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
