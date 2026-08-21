#!/usr/bin/env python3
"""Read-only FastVolt/EVOne header-name differential probe.

Purpose: determine which public client-context *header name* the station-list endpoints
recognize, using only a fixed dummy value. No login, credential guessing, real tenant IDs,
station IDs, account data, mutations, or raw response bodies are used or persisted.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path("artifacts/morocco-fastvolt-evone-header-names")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

TARGETS = {
    "fastvolt": "https://mobile.ev.fastvolt.ma/app/charging_stations/",
    "evone": "https://mobile.evplugv2.bornerecharge.ma/app/charging_stations/",
}

# Names are derived from sanitized static client symbols already present in this repo.
# Every probe uses the same inert dummy value and never attempts to discover a real value.
HEADER_NAMES = [
    "X-Client",
    "Client",
    "Organization",
    "Organisation",
    "X-Organization",
    "X-Organisation",
    "Business",
    "X-Business",
    "Tenant",
    "X-Tenant",
]

SENSITIVE = re.compile(r"(?i)(token|secret|password|cookie|authorization|email|phone|account|customer|card|payment)")


def safe_json_shape(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = [str(k) for k in obj.keys() if not SENSITIVE.search(str(k))][:30]
        msg = obj.get("message")
        if isinstance(msg, str):
            # Validation/auth messages are retained, but strip suspicious long token-like runs.
            msg = re.sub(r"\b[A-Za-z0-9_-]{32,}\b", "[REDACTED]", msg)
            out["message"] = msg[:500]
        errors = obj.get("errors")
        if isinstance(errors, dict):
            out["error_keys"] = [str(k) for k in errors.keys() if not SENSITIVE.search(str(k))][:30]
    return out


def call(url: str, label: str, header_name: str | None = None) -> dict:
    headers = {"User-Agent": UA, "Accept": "application/json,text/plain,*/*"}
    if header_name:
        headers[header_name] = "0"
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            body = res.read(80_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(80_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"case": label, "status": None, "error_type": type(exc).__name__}
    return {
        "case": label,
        "status": status,
        "content_type": ctype,
        "safe_response": safe_json_shape(body),
    }


def main() -> None:
    apps = {}
    for app, url in TARGETS.items():
        baseline = call(url, "baseline_no_context_header")
        probes = [call(url, f"dummy_{name.lower().replace('-', '_')}", name) for name in HEADER_NAMES]
        base_sig = (baseline.get("status"), baseline.get("safe_response", {}).get("message"), tuple(baseline.get("safe_response", {}).get("error_keys", [])))
        changed = []
        for p, name in zip(probes, HEADER_NAMES):
            sig = (p.get("status"), p.get("safe_response", {}).get("message"), tuple(p.get("safe_response", {}).get("error_keys", [])))
            if sig != base_sig:
                changed.append(name)
        apps[app] = {
            "baseline": baseline,
            "dummy_header_probes": probes,
            "header_names_with_response_change": changed,
        }

    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "read_only_get_only": True,
            "no_login": True,
            "no_credentials": True,
            "dummy_value_only": True,
            "no_real_tenant_or_business_ids": True,
            "no_station_ids": True,
            "no_mutations": True,
            "raw_response_bodies_persisted": False,
        },
        "apps": apps,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v["header_names_with_response_change"] for k, v in apps.items()}))


if __name__ == "__main__":
    main()
