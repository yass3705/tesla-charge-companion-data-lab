#!/usr/bin/env python3
"""Run one anonymous GET derived from Club EV-Charge target-client evidence only.

The candidate is gated by three static literals from the current public target
package: the branded host, the station-state route and a Numocity "/2" fragment
located next to that route. No sibling-client host, brute-force prefix, query,
identifier, credential or mutation is used.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE = "com.namp.totalev"
HOST = "csmstotalenergiesma.numocity.com"
ROUTE = "/chargestation/getstationstate"
VERSIONED_NEAR_ROUTE_FRAGMENT = "numocity.com/2"
CANDIDATE_URL = f"https://{HOST}/2{ROUTE}"

OUT = Path("artifacts/morocco-club-evcharge-exact-target-get")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/2.1)"
MAX_DOWNLOAD = 180 * 1024 * 1024
MAX_SCAN_FILE = 150 * 1024 * 1024
MAX_BODY_SAMPLE = 120_000
SCAN_SUFFIXES = {".so", ".dex", ".apk", ".xml", ".json", ".arsc"}
SAFE_MESSAGE_KEYS = ("message", "error", "detail", "status")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_public_package(destination: Path):
    for package_format in ("XAPK", "APK"):
        try:
            url = f"https://d.apkpure.com/b/{package_format}/{PACKAGE}?version=latest"
            request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
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


def occurrences(data: bytes, needle: bytes):
    count = 0
    positions = []
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            break
        count += 1
        positions.append(pos)
        start = pos + max(1, len(needle))
    return count, positions


def static_gate(package_file: Path, root: Path):
    safe_unpack(package_file, root)
    for index, apk in enumerate(list(root.rglob("*.apk"))[:40]):
        safe_unpack(apk, root / f"apk_{index}")

    candidates = [package_file]
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if 0 < size <= MAX_SCAN_FILE and (
            path.suffix.lower() in SCAN_SUFFIXES or path.name == "resources.arsc"
        ):
            candidates.append(path)
        if len(candidates) >= 100:
            break

    host_hits = 0
    route_hits = 0
    near_v2_hits = 0
    same_file_hits = 0
    files_scanned = 0
    bytes_scanned = 0
    host_b = HOST.encode("ascii")
    route_b = ROUTE.encode("ascii")
    fragment_b = VERSIONED_NEAR_ROUTE_FRAGMENT.encode("ascii")

    for path in candidates:
        try:
            data = path.read_bytes()
        except Exception:
            continue
        files_scanned += 1
        bytes_scanned += len(data)
        normalized = data.replace(b"\x00", b"")

        h_count, _ = occurrences(normalized, host_b)
        r_count, route_positions = occurrences(normalized, route_b)
        host_hits += h_count
        route_hits += r_count
        if h_count and r_count:
            same_file_hits += 1

        radius = 1024
        for pos in route_positions:
            window = normalized[max(0, pos - radius): min(len(normalized), pos + len(route_b) + radius)]
            if fragment_b in window:
                near_v2_hits += 1

    return {
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "host_literal_hits": host_hits,
        "route_literal_hits": route_hits,
        "near_route_numocity_v2_hits": near_v2_hits,
        "host_and_route_same_file_count": same_file_hits,
        "gate_passed": bool(host_hits and route_hits and near_v2_hits),
    }


def safe_shape(body: str):
    try:
        value = json.loads(body)
    except Exception:
        lower = body.lower()
        return {
            "json": False,
            "body_length_sampled": len(body),
            "signals": {
                key: key in lower
                for key in ("not found", "route", "required", "missing", "unauthorized", "forbidden")
            },
        }

    if isinstance(value, dict):
        result = {
            "json": True,
            "top_level_type": "object",
            "top_level_keys": sorted(str(key) for key in value)[:80],
        }
        for key in SAFE_MESSAGE_KEYS:
            message = value.get(key)
            if isinstance(message, str):
                result[f"{key}_present"] = True
                result[f"{key}_length"] = len(message)
        errors = value.get("errors")
        if isinstance(errors, dict):
            result["error_fields"] = sorted(str(key) for key in errors)[:80]
        elif isinstance(errors, list):
            result["errors_type"] = "list"
            result["errors_count"] = len(errors)
        return result

    if isinstance(value, list):
        return {
            "json": True,
            "top_level_type": "list",
            "item_count": len(value),
        }

    return {
        "json": True,
        "top_level_type": type(value).__name__,
    }


def sanitized_final_target(url: str):
    try:
        parsed = urlsplit(url)
    except Exception:
        return None
    if (parsed.hostname or "").lower() != HOST:
        return "cross_host_redirect_blocked"
    return f"{parsed.scheme.lower()}://{HOST}{parsed.path or '/'}"


def one_get():
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(
        CANDIDATE_URL,
        method="GET",
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with opener.open(request, timeout=25) as response:
            status = response.status
            content_type = response.headers.get("content-type", "")
            body = response.read(MAX_BODY_SAMPLE).decode("utf-8", "replace")
            final_target = sanitized_final_target(response.geturl())
    except urllib.error.HTTPError as error:
        status = error.code
        content_type = error.headers.get("content-type", "") if error.headers else ""
        try:
            body = error.read(MAX_BODY_SAMPLE).decode("utf-8", "replace")
        except Exception:
            body = ""
        final_target = CANDIDATE_URL
    except Exception as error:
        return {
            "request_count": 1,
            "method": "GET",
            "query_parameters_used": False,
            "request_body_used": False,
            "status": 0,
            "error_type": type(error).__name__,
            "content_type": None,
            "final_target": CANDIDATE_URL,
            "safe_response_shape": {"json": False, "transport_error": True},
        }

    return {
        "request_count": 1,
        "method": "GET",
        "query_parameters_used": False,
        "request_body_used": False,
        "status": int(status),
        "content_type": content_type,
        "final_target": final_target,
        "safe_response_shape": safe_shape(body),
    }


def technical_result(probe):
    status = probe.get("status")
    shape = probe.get("safe_response_shape") or {}
    if 200 <= status < 300 and shape.get("json"):
        return "anonymous_read_only_shape_reached"
    if status in (400, 405, 409, 422) and shape.get("json"):
        return "route_reached_request_shape_incomplete"
    if status in (401, 403):
        return "authentication_required_blocker"
    if status == 404:
        return "evidence_derived_candidate_not_matched"
    if status == 0:
        return "transport_blocker"
    return "diagnostic_response_only"


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "subject": "Club EV-Charge target-only evidence-gated anonymous station-state GET",
        "policy": {
            "target_client_only": True,
            "static_gate_before_network": True,
            "anonymous_read_only_get_only": True,
            "no_path_enumeration": True,
            "single_evidence_derived_candidate": True,
            "no_login": True,
            "no_credentials": True,
            "no_real_station_or_connector_ids": True,
            "no_query_parameters": True,
            "no_request_body": True,
            "no_charging_or_account_actions": True,
            "redirects_followed": False,
            "raw_response_body_persisted": False,
            "raw_package_persisted": False,
        },
        "target_package": {
            "package_id": PACKAGE,
            "public_listing": f"https://play.google.com/store/apps/details?id={PACKAGE}",
        },
        "candidate": {
            "url": CANDIDATE_URL,
            "constructed_from_target_package_only": True,
            "construction": {
                "host_literal": HOST,
                "version_prefix_signal": "/2",
                "route_literal": ROUTE,
            },
            "static_evidence": {},
        },
        "probe": {
            "request_count": 0,
            "method": "GET",
            "query_parameters_used": False,
            "request_body_used": False,
            "status": 0,
            "safe_response_shape": {"json": False, "not_run": True},
        },
        "modeling": {
            "cpo_operator": "unresolved_station_specific",
            "site_brand": "TotalEnergies when station-specific evidence supports it",
            "app_source_access_network": "Club EV-Charge / TotalEnergies Marketing Maroc",
            "tariff_channel": "unresolved_without_native_station-specific evidence",
            "status_source": "unresolved_until_station-specific native payload validation",
            "implementation_partner": "GM AFRICA",
            "numocity_role": "unverified_current_production_backend",
        },
        "technical_result": "static_gate_not_run",
        "production_decision": "no_promotion",
    }

    with tempfile.TemporaryDirectory(prefix="tcc-club-target-get-") as temp_dir:
        root = Path(temp_dir)
        package_file = root / "club.pkg"
        download = download_public_package(package_file)
        report["target_package"].update(download)
        report["target_package"]["raw_package_persisted"] = False

        if download["download_ok"]:
            gate = static_gate(package_file, root / "tree")
        else:
            gate = {
                "files_scanned": 0,
                "bytes_scanned": 0,
                "host_literal_hits": 0,
                "route_literal_hits": 0,
                "near_route_numocity_v2_hits": 0,
                "host_and_route_same_file_count": 0,
                "gate_passed": False,
            }
        report["candidate"]["static_evidence"] = gate

        if gate["gate_passed"]:
            report["probe"] = one_get()
            report["technical_result"] = technical_result(report["probe"])
        else:
            report["technical_result"] = "static_gate_failed_no_network_request"

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "target_package": {
            "download_ok": report["target_package"].get("download_ok"),
            "download_bytes": report["target_package"].get("download_bytes"),
            "download_sha256": report["target_package"].get("download_sha256"),
        },
        "static_evidence": report["candidate"]["static_evidence"],
        "candidate": CANDIDATE_URL,
        "probe": report["probe"],
        "technical_result": report["technical_result"],
        "production_decision": report["production_decision"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
