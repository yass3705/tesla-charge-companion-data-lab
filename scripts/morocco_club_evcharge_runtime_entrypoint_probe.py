#!/usr/bin/env python3
"""Inspect the exact Club EV-Charge Flutter runtime entrypoint named by the public shell.

This probe is deliberately narrow. It is gated by the persisted public-shell
record from PR #64, performs exactly one anonymous GET to the same-origin
`/main.dart.js` path explicitly named by Flutter bootstrap, follows no
redirects, makes no discovered-route requests, and persists no response body or
arbitrary strings. Only bounded hashes, marker counts and sanitized read-only
route/base-URL candidates are retained.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

HOST = "csmstotalenergiesma.numocity.com"
ENTRYPOINT_PATH = "/main.dart.js"
ENTRYPOINT_URL = f"https://{HOST}{ENTRYPOINT_PATH}"
PR64_RECORD = Path(
    "reports/morocco/totalenergies/"
    "club-ev-charge-public-root-assets-2026-09-01.json"
)
OUT = Path("artifacts/morocco-club-evcharge-runtime-entrypoint")
OUT.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/2.3)"
MAX_BYTES = 32 * 1024 * 1024

TARGET_MARKERS = (
    "csmstotalenergiesma",
    "numocity",
    "totalenergies",
    "/api/",
    "/chargestation/",
    "getstationstate",
    "get-connector-status",
    "qr-connector",
    "tariff",
    "connectorstatus",
)
BASE_CONFIG_KEYS = (
    "baseUrl",
    "baseURL",
    "apiUrl",
    "apiURL",
    "apiBaseUrl",
    "apiBaseURL",
    "endpoint",
)
READ_ONLY_TOKENS = (
    "get",
    "list",
    "status",
    "state",
    "station",
    "charger",
    "connector",
    "evse",
    "location",
    "tariff",
    "price",
)
SENSITIVE_TOKENS = (
    "login",
    "auth",
    "token",
    "account",
    "payment",
    "wallet",
    "password",
    "secret",
    "customer",
    "register",
    "start",
    "stop",
    "transaction",
    "session",
    "delete",
    "update",
    "create",
    "profile",
)
QUOTED_PATH_RX = re.compile(r"[\"'](/(?:[A-Za-z0-9._~!$&()*+,;=:@%/-]){2,240})[\"']")
ABS_URL_RX = re.compile(r"https://[A-Za-z0-9.-]*numocity\.com(?:/[A-Za-z0-9._~!$&()*+,;=:@%/-]{0,240})?", re.I)
BASE_LITERAL_RX = re.compile(
    r"(?:baseUrl|baseURL|apiUrl|apiURL|apiBaseUrl|apiBaseURL|endpoint)"
    r"[\"']?\s*[:=]\s*[\"'](https://[A-Za-z0-9.-]*numocity\.com"
    r"(?:/[A-Za-z0-9._~!$&()*+,;=:@%/-]{0,240})?)[\"']",
    re.I,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def exact_gate():
    result = {
        "record_path": str(PR64_RECORD),
        "record_present": PR64_RECORD.is_file(),
        "root_host_matches": False,
        "entrypoint_matches": False,
        "entrypoint_not_previously_fetched": False,
        "public_shell_result_matches": False,
        "production_no_promotion": False,
        "gate_passed": False,
    }
    if not result["record_present"]:
        return result
    try:
        record = json.loads(PR64_RECORD.read_text())
        root = record.get("root", {}).get("url", "")
        findings = record.get("safe_findings", {})
        result["root_host_matches"] = (urlsplit(root).hostname or "").lower() == HOST
        result["entrypoint_matches"] = findings.get("runtime_entrypoint_path") == ENTRYPOINT_PATH
        result["entrypoint_not_previously_fetched"] = findings.get("runtime_entrypoint_fetched") is False
        result["public_shell_result_matches"] = (
            record.get("technical_result")
            == "public_shell_entrypoint_identified_no_target_backend_config"
        )
        result["production_no_promotion"] = record.get("production_decision") == "no_promotion"
    except Exception:
        return result
    result["gate_passed"] = all(
        result[key]
        for key in (
            "record_present",
            "root_host_matches",
            "entrypoint_matches",
            "entrypoint_not_previously_fetched",
            "public_shell_result_matches",
            "production_no_promotion",
        )
    )
    return result


def http_get_exact():
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(
        ENTRYPOINT_URL,
        method="GET",
        headers={
            "User-Agent": UA,
            "Accept": "application/javascript,text/javascript,*/*",
        },
    )
    try:
        with opener.open(request, timeout=45) as response:
            payload = response.read(MAX_BYTES + 1)
            return {
                "status": int(response.status),
                "content_type": response.headers.get("content-type", ""),
                "payload": payload,
                "limit_exceeded": len(payload) > MAX_BYTES,
            }
    except urllib.error.HTTPError as error:
        try:
            payload = error.read(MAX_BYTES + 1)
        except Exception:
            payload = b""
        return {
            "status": int(error.code),
            "content_type": error.headers.get("content-type", "") if error.headers else "",
            "payload": payload,
            "limit_exceeded": len(payload) > MAX_BYTES,
        }
    except Exception as error:
        return {
            "status": 0,
            "content_type": None,
            "payload": b"",
            "limit_exceeded": False,
            "error_type": type(error).__name__,
        }


def safe_url(value: str):
    try:
        parsed = urlsplit(value)
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or not host.endswith("numocity.com"):
        return None
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    if parsed.query or parsed.fragment:
        return None
    path = parsed.path or "/"
    lower = path.lower()
    if any(token in lower for token in SENSITIVE_TOKENS):
        return None
    return f"https://{host}{path}"[:500]


def safe_read_only_path(value: str):
    try:
        parsed = urlsplit(value)
    except Exception:
        return None
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None
    path = parsed.path
    if not path.startswith("/") or len(path) > 240:
        return None
    lower = path.lower()
    if any(token in lower for token in SENSITIVE_TOKENS):
        return None
    if not any(token in lower for token in READ_ONLY_TOKENS):
        return None
    if not ("api" in lower or "station" in lower or "connector" in lower or "charger" in lower):
        return None
    return path


def scan(payload: bytes):
    text = payload.decode("utf-8", "replace")
    lower = text.lower()
    marker_counts = Counter()
    for marker in TARGET_MARKERS:
        count = lower.count(marker.lower())
        if count:
            marker_counts[marker] += count

    config_key_counts = Counter()
    for key in BASE_CONFIG_KEYS:
        count = text.count(key)
        if count:
            config_key_counts[key] += count

    absolute_urls = sorted(
        {
            sanitized
            for raw in ABS_URL_RX.findall(text)
            if (sanitized := safe_url(raw)) is not None
        }
    )[:20]
    base_literals = sorted(
        {
            sanitized
            for raw in BASE_LITERAL_RX.findall(text)
            if (sanitized := safe_url(raw)) is not None
        }
    )[:20]
    read_only_paths = sorted(
        {
            sanitized
            for raw in QUOTED_PATH_RX.findall(text)
            if (sanitized := safe_read_only_path(raw)) is not None
        }
    )[:80]

    return {
        "target_marker_counts": dict(sorted(marker_counts.items())),
        "base_config_key_counts": dict(sorted(config_key_counts.items())),
        "safe_numocity_absolute_urls": absolute_urls,
        "safe_numocity_base_literals": base_literals,
        "safe_read_only_path_candidates": read_only_paths,
        "safe_numocity_absolute_url_count": len(absolute_urls),
        "safe_numocity_base_literal_count": len(base_literals),
        "safe_read_only_path_candidate_count": len(read_only_paths),
    }


def main():
    gate = exact_gate()
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "subject": "Club EV-Charge exact public Flutter runtime entrypoint",
        "policy": {
            "pr64_public_shell_record_gate": True,
            "anonymous_read_only_get_only": True,
            "exact_same_origin_entrypoint_only": True,
            "entrypoint_must_be_explicitly_named_by_public_bootstrap": True,
            "no_discovered_route_requests": True,
            "no_path_enumeration": True,
            "no_redirects_followed": True,
            "no_query_parameters": True,
            "no_request_body": True,
            "no_login": True,
            "no_credentials": True,
            "no_cookies": True,
            "no_station_or_connector_ids": True,
            "no_charging_or_account_actions": True,
            "raw_runtime_body_persisted": False,
            "arbitrary_strings_persisted": False,
            "sanitized_read_only_candidates_only": True,
        },
        "limits": {"max_runtime_bytes": MAX_BYTES},
        "evidence_gate": gate,
        "request": {
            "url": ENTRYPOINT_URL,
            "path": ENTRYPOINT_PATH,
            "request_count": 0,
            "method": "GET",
            "status": 0,
            "content_type": None,
            "bytes": 0,
            "sha256": None,
            "limit_exceeded": False,
        },
        "safe_findings": {
            "target_marker_counts": {},
            "base_config_key_counts": {},
            "safe_numocity_absolute_urls": [],
            "safe_numocity_base_literals": [],
            "safe_read_only_path_candidates": [],
            "safe_numocity_absolute_url_count": 0,
            "safe_numocity_base_literal_count": 0,
            "safe_read_only_path_candidate_count": 0,
        },
        "network": {"total_request_count": 0, "cross_origin_request_count": 0},
        "modeling": {
            "cpo_operator": "unresolved_station_specific",
            "site_brand": "TotalEnergies when station-specific evidence supports it",
            "app_source_access_network": "Club EV-Charge / TotalEnergies Marketing Maroc",
            "tariff_channel": "unresolved_without_native_station-specific evidence",
            "status_source": "unresolved_until_station-specific native payload validation",
            "implementation_partner": "GM AFRICA",
            "numocity_role": "unverified_current_production_backend",
        },
        "technical_result": "evidence_gate_failed_no_network_request",
        "production_decision": "no_promotion",
        "next_step": "No network action until the evidence gate passes.",
    }

    if not gate["gate_passed"]:
        (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"gate": gate, "technical_result": report["technical_result"]}))
        return

    response = http_get_exact()
    payload = response.pop("payload")
    report["request"].update(response)
    report["request"]["request_count"] = 1
    report["request"]["bytes"] = len(payload)
    report["network"]["total_request_count"] = 1

    full = not report["request"]["limit_exceeded"]
    if full:
        report["request"]["sha256"] = hashlib.sha256(payload).hexdigest()

    javascript_like = "javascript" in (report["request"].get("content_type") or "").lower()
    if report["request"]["status"] == 200 and full and javascript_like:
        report["safe_findings"] = scan(payload)
        findings = report["safe_findings"]
        if (
            findings["safe_numocity_absolute_url_count"]
            or findings["safe_numocity_base_literal_count"]
            or findings["safe_read_only_path_candidate_count"]
        ):
            report["technical_result"] = "runtime_public_readonly_candidate_shape_identified"
            report["next_step"] = (
                "Review only sanitized read-only candidates. A later probe may issue one exact anonymous GET "
                "only if a candidate is explicitly supported by this public runtime; do not enumerate paths."
            )
        else:
            report["technical_result"] = "runtime_fetched_no_readonly_candidate_shape"
            report["next_step"] = (
                "Do not guess API paths. Seek another explicit public client artifact or app-verifiable example."
            )
    elif report["request"]["limit_exceeded"]:
        report["technical_result"] = "runtime_exceeded_bounded_scan_limit"
        report["next_step"] = "Do not broaden automatically; document the bounded-scan blocker."
    else:
        report["technical_result"] = "runtime_entrypoint_not_readable_as_public_javascript"
        report["next_step"] = "Do not guess alternate paths."

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "gate_passed": gate["gate_passed"],
        "request": report["request"],
        "safe_findings": report["safe_findings"],
        "technical_result": report["technical_result"],
        "production_decision": report["production_decision"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
