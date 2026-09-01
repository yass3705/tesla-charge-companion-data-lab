#!/usr/bin/env python3
"""Inspect the Club EV-Charge public web shell without enumerating paths.

The probe is gated by the persisted rejected-candidate record from PR #63. It
performs one anonymous GET on the exact public root and then fetches only
same-origin JavaScript/CSS assets explicitly referenced by that HTML. It does
not recursively follow asset-discovered paths, and it never persists response
bodies or arbitrary strings.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit


HOST = "csmstotalenergiesma.numocity.com"
ROOT_URL = f"https://{HOST}/"
PR63_RECORD = Path(
    "reports/morocco/totalenergies/"
    "club-ev-charge-exact-target-get-2026-09-01.json"
)
OUT = Path("artifacts/morocco-club-evcharge-public-root-assets")
OUT.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/2.2)"
MAX_ROOT_BYTES = 256 * 1024
MAX_ASSETS = 20
MAX_ASSET_BYTES = 2 * 1024 * 1024
MAX_TOTAL_ASSET_BYTES = 12 * 1024 * 1024

TARGET_MARKERS = (
    "csmstotalenergiesma",
    "numocity",
    "totalenergies",
    "gm-africa",
    "/api/",
    "/chargestation/",
    "getstationstate",
    "get-connector-status",
)
TARGET_RUNTIME_EVIDENCE_MARKERS = (
    "numocity.com/2",
    "/chargestation/getstationstate",
    "/api/get-connector-status",
    "/api/qr-connector",
)
CONFIG_KEYS = (
    "mainJsPath",
    "compileTarget",
    "renderer",
    "engineRevision",
    "serviceWorkerVersion",
    "authority",
    "knownAuthorities",
    "tenant",
    "clientId",
    "redirectUri",
    "postLogoutRedirectUri",
)
KNOWN_RELATIVE_ASSETS = ("main.dart.js", "flutter_service_worker.js")
SAFE_INFRA_URLS = (
    "https://login.microsoftonline.com/",
    "https://www.gstatic.com/flutter-canvaskit",
)
SENSITIVE_PATH_RX = re.compile(
    r"(?:^|[/_.-])(login|auth|token|account|payment|session|transaction|"
    r"start|stop|password|secret|wallet|customer)(?:$|[/_.-])",
    re.I,
)
SAFE_ASSET_PATH_RX = re.compile(r"/[A-Za-z0-9._~!$&'()*+,;=:@%/-]{1,500}\.(?:js|css)$", re.I)
SAFE_LITERAL_RX = re.compile(
    r"[\"']?(mainJsPath|compileTarget|renderer|engineRevision|serviceWorkerVersion)"
    r"[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9._/${}-]{1,128})",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RootAssetParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = {str(key).lower(): value for key, value in attrs if value is not None}
        tag = tag.lower()
        if tag == "script" and values.get("src"):
            self.references.append(values["src"])
            return
        if tag != "link" or not values.get("href"):
            return
        rel = {part.lower() for part in values.get("rel", "").split()}
        as_value = values.get("as", "").lower()
        href_path = urlsplit(values["href"]).path.lower()
        if (
            "stylesheet" in rel
            or "modulepreload" in rel
            or ("preload" in rel and as_value in {"script", "style"})
            or href_path.endswith((".js", ".css"))
        ):
            self.references.append(values["href"])


def exact_gate():
    result = {
        "record_path": str(PR63_RECORD),
        "record_present": PR63_RECORD.is_file(),
        "candidate_host_matches": False,
        "rejected_candidate_recorded": False,
        "production_no_promotion": False,
        "gate_passed": False,
    }
    if not result["record_present"]:
        return result
    try:
        record = json.loads(PR63_RECORD.read_text())
        candidate = record.get("candidate", {}).get("url", "")
        result["candidate_host_matches"] = (
            (urlsplit(candidate).hostname or "").lower() == HOST
        )
        result["rejected_candidate_recorded"] = (
            record.get("technical_result") == "evidence_derived_candidate_not_matched"
        )
        result["production_no_promotion"] = record.get("production_decision") == "no_promotion"
    except Exception:
        return result
    result["gate_passed"] = all(
        result[key]
        for key in (
            "record_present",
            "candidate_host_matches",
            "rejected_candidate_recorded",
            "production_no_promotion",
        )
    )
    return result


def same_origin_asset(reference: str):
    try:
        resolved = urlsplit(urljoin(ROOT_URL, reference))
    except Exception:
        return None
    if resolved.scheme.lower() != "https" or (resolved.hostname or "").lower() != HOST:
        return None
    if resolved.username or resolved.password or resolved.port not in (None, 443):
        return None
    if resolved.query or resolved.fragment:
        return None
    path = resolved.path or "/"
    if not SAFE_ASSET_PATH_RX.fullmatch(path) or SENSITIVE_PATH_RX.search(path):
        return None
    return path


def sanitized_cross_origin_reference(reference: str):
    try:
        parsed = urlsplit(urljoin(ROOT_URL, reference))
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or not host or host == HOST:
        return None
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    path = parsed.path or "/"
    if SENSITIVE_PATH_RX.search(path):
        return None
    return f"https://{host}{path}"[:600]


def http_get(url: str, limit: int, accept: str):
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": UA, "Accept": accept},
    )
    try:
        with opener.open(request, timeout=30) as response:
            payload = response.read(limit + 1)
            return {
                "status": int(response.status),
                "content_type": response.headers.get("content-type", ""),
                "payload": payload,
                "limit_exceeded": len(payload) > limit,
            }
    except urllib.error.HTTPError as error:
        try:
            payload = error.read(limit + 1)
        except Exception:
            payload = b""
        return {
            "status": int(error.code),
            "content_type": error.headers.get("content-type", "") if error.headers else "",
            "payload": payload,
            "limit_exceeded": len(payload) > limit,
        }
    except Exception as error:
        return {
            "status": 0,
            "content_type": None,
            "payload": b"",
            "limit_exceeded": False,
            "error_type": type(error).__name__,
        }


def safe_bootstrap_literals(text: str):
    found: dict[str, str] = {}
    allowed_values = {
        "compileTarget": {"dart2js", "dartdevc"},
        "renderer": {"canvaskit", "html", "skwasm"},
    }
    for key, raw_value in SAFE_LITERAL_RX.findall(text):
        value = raw_value.strip("\"'")
        if key == "mainJsPath":
            parsed = urlsplit(value)
            if (
                not parsed.scheme
                and not parsed.netloc
                and not parsed.query
                and not parsed.fragment
                and re.fullmatch(r"[A-Za-z0-9._/-]{1,120}\.js", parsed.path)
            ):
                found[key] = parsed.path.lstrip("/")
        elif key in allowed_values and value in allowed_values[key]:
            found[key] = value
        elif key == "engineRevision" and re.fullmatch(r"[0-9a-f]{7,64}", value, re.I):
            found[key] = value.lower()
        elif key == "serviceWorkerVersion" and re.fullmatch(r"[0-9]{1,32}", value):
            found[key] = value
    return dict(sorted(found.items()))


def scan_allowlisted(payloads: list[bytes]):
    target_counts = Counter()
    runtime_evidence_counts = Counter()
    config_counts = Counter()
    relative_asset_counts = Counter()
    infra_urls = Counter()
    bootstrap = {}

    for payload in payloads:
        text = payload.decode("utf-8", "replace")
        lower = text.lower()
        for marker in TARGET_MARKERS:
            count = lower.count(marker.lower())
            if count:
                target_counts[marker] += count
        for marker in TARGET_RUNTIME_EVIDENCE_MARKERS:
            count = lower.count(marker.lower())
            if count:
                runtime_evidence_counts[marker] += count
        for key in CONFIG_KEYS:
            count = text.count(key)
            if count:
                config_counts[key] += count
        for marker in KNOWN_RELATIVE_ASSETS:
            count = text.count(marker)
            if count:
                relative_asset_counts[marker] += count
        for safe_url in SAFE_INFRA_URLS:
            count = text.count(safe_url)
            if count:
                infra_urls[safe_url] += count
        bootstrap.update(safe_bootstrap_literals(text))

    entrypoint = bootstrap.get("mainJsPath")
    if entrypoint:
        resolved = same_origin_asset(entrypoint)
    else:
        resolved = None
    return {
        "target_marker_counts": dict(sorted(target_counts.items())),
        "target_runtime_evidence_marker_counts": dict(sorted(runtime_evidence_counts.items())),
        "config_key_counts": dict(sorted(config_counts.items())),
        "known_relative_asset_counts": dict(sorted(relative_asset_counts.items())),
        "safe_public_infrastructure_url_counts": dict(sorted(infra_urls.items())),
        "safe_flutter_bootstrap_literals": bootstrap,
        "runtime_entrypoint_path": resolved,
        "runtime_entrypoint_fetched": False,
        "target_backend_markers_found": bool(runtime_evidence_counts),
    }


def main():
    gate = exact_gate()
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "subject": "Club EV-Charge public root and explicit same-origin asset configuration",
        "policy": {
            "pr63_rejected_candidate_record_gate": True,
            "anonymous_read_only_get_only": True,
            "exact_public_root_only": True,
            "assets_must_be_explicit_root_src_or_href": True,
            "same_origin_https_assets_only": True,
            "asset_discovery_is_not_recursive": True,
            "no_path_enumeration": True,
            "no_redirects_followed": True,
            "no_query_parameters": True,
            "no_request_body": True,
            "no_login": True,
            "no_credentials": True,
            "no_cookies": True,
            "no_station_or_connector_ids": True,
            "no_charging_or_account_actions": True,
            "raw_root_html_persisted": False,
            "raw_asset_bodies_persisted": False,
            "arbitrary_strings_persisted": False,
        },
        "limits": {
            "max_root_bytes": MAX_ROOT_BYTES,
            "max_assets": MAX_ASSETS,
            "max_asset_bytes": MAX_ASSET_BYTES,
            "max_total_asset_bytes": MAX_TOTAL_ASSET_BYTES,
        },
        "evidence_gate": gate,
        "root": {
            "url": ROOT_URL,
            "request_count": 0,
            "method": "GET",
            "status": 0,
            "content_type": None,
            "bytes": 0,
            "sha256": None,
            "limit_exceeded": False,
        },
        "discovery": {
            "explicit_reference_count": 0,
            "eligible_same_origin_asset_paths": [],
            "cross_origin_references_not_fetched": [],
            "asset_limit_exceeded": False,
        },
        "assets": [],
        "safe_findings": {
            "target_marker_counts": {},
            "target_runtime_evidence_marker_counts": {},
            "config_key_counts": {},
            "known_relative_asset_counts": {},
            "safe_public_infrastructure_url_counts": {},
            "safe_flutter_bootstrap_literals": {},
            "runtime_entrypoint_path": None,
            "runtime_entrypoint_fetched": False,
            "target_backend_markers_found": False,
        },
        "network": {
            "total_request_count": 0,
            "root_request_count": 0,
            "asset_request_count": 0,
            "cross_origin_request_count": 0,
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
        "technical_result": "evidence_gate_failed_no_network_request",
        "production_decision": "no_promotion",
        "next_step": "No network action until the evidence gate passes.",
    }

    if not gate["gate_passed"]:
        (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"gate": gate, "technical_result": report["technical_result"]}))
        return

    root_response = http_get(ROOT_URL, MAX_ROOT_BYTES, "text/html,*/*")
    report["network"]["root_request_count"] = 1
    report["network"]["total_request_count"] = 1
    root_payload = root_response.pop("payload")
    root_full = not root_response["limit_exceeded"]
    report["root"].update(root_response)
    report["root"]["request_count"] = 1
    report["root"]["bytes"] = len(root_payload)
    report["root"]["sha256"] = hashlib.sha256(root_payload).hexdigest() if root_full else None

    text_html = "text/html" in (report["root"].get("content_type") or "").lower()
    if report["root"]["status"] == 200 and root_full and text_html:
        parser = RootAssetParser()
        parser.feed(root_payload.decode("utf-8", "replace"))
        report["discovery"]["explicit_reference_count"] = len(parser.references)
        eligible = sorted({path for ref in parser.references if (path := same_origin_asset(ref))})
        cross_origin = sorted(
            {value for ref in parser.references if (value := sanitized_cross_origin_reference(ref))}
        )
        report["discovery"]["cross_origin_references_not_fetched"] = cross_origin
        report["discovery"]["asset_limit_exceeded"] = len(eligible) > MAX_ASSETS
        if len(eligible) <= MAX_ASSETS:
            report["discovery"]["eligible_same_origin_asset_paths"] = eligible

    scanned_payloads = [root_payload] if root_full else []
    total_asset_bytes = 0
    for path in report["discovery"]["eligible_same_origin_asset_paths"]:
        if total_asset_bytes >= MAX_TOTAL_ASSET_BYTES:
            break
        remaining = MAX_TOTAL_ASSET_BYTES - total_asset_bytes
        limit = min(MAX_ASSET_BYTES, remaining)
        response = http_get(
            f"https://{HOST}{path}",
            limit,
            "application/javascript,text/javascript,text/css,*/*",
        )
        report["network"]["asset_request_count"] += 1
        report["network"]["total_request_count"] += 1
        payload = response.pop("payload")
        complete = not response["limit_exceeded"]
        item = {
            "path": path,
            **response,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest() if complete else None,
            "scanned": False,
        }
        total_asset_bytes += len(payload)
        content_type = (item.get("content_type") or "").lower()
        text_like = content_type.startswith("text/") or any(
            marker in content_type for marker in ("javascript", "ecmascript")
        )
        if item["status"] == 200 and complete and text_like:
            scanned_payloads.append(payload)
            item["scanned"] = True
        report["assets"].append(item)

    report["safe_findings"] = scan_allowlisted(scanned_payloads)
    findings = report["safe_findings"]
    if findings["runtime_entrypoint_path"] and not findings["target_backend_markers_found"]:
        report["technical_result"] = "public_shell_entrypoint_identified_no_target_backend_config"
        report["next_step"] = (
            "Validate exactly the same-origin runtime entrypoint named by the fetched public "
            "Flutter bootstrap. Do not enumerate other assets or API paths."
        )
    elif findings["target_backend_markers_found"]:
        report["technical_result"] = "target_backend_marker_present_in_public_shell_assets"
        report["next_step"] = (
            "Review only the allowlisted public marker counts before deriving any new request."
        )
    else:
        report["technical_result"] = "public_shell_assets_no_runtime_authority_resolved"
        report["next_step"] = (
            "Keep the native endpoint unresolved; do not enumerate paths or fetch assets not "
            "explicitly evidenced by the public shell."
        )

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "gate_passed": gate["gate_passed"],
        "root": report["root"],
        "assets": report["assets"],
        "safe_findings": report["safe_findings"],
        "network": report["network"],
        "technical_result": report["technical_result"],
        "production_decision": report["production_decision"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
