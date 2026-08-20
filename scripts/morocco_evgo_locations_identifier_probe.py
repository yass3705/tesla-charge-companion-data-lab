#!/usr/bin/env python3
"""Read-only EVGO/AMPECO locations identifier-shape probe.

Tests whether /api/v1|v2/app/locations accepts a locations array containing
simple public/non-sensitive identifiers. No login, credentials, coordinates,
charging actions, or account/session mutations are used. Persisted output is
limited to HTTP status, collection counts, object field names and whitelisted
public charging-infrastructure values when a match is returned.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://evgo.eu-evgo.charge.ampeco.tech"
PATHS = ["/api/v1/app/locations", "/api/v2/app/locations"]
CASES = [
    ("string_zero", {"locations": ["0"]}),
    ("numeric_zero", {"locations": [0]}),
    ("public_site_name", {"locations": ["Marjane Mohammedia"]}),
    ("public_evone_id_1004", {"locations": ["1004"]}),
]
OUT = Path("artifacts/morocco-evgo-locations-identifier")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

ALLOW = {
    "id", "name", "title", "status", "availability", "available", "power",
    "powerKw", "maxPower", "latitude", "longitude", "lat", "lng", "address",
    "city", "currency", "tariff", "tariffs", "price", "free", "evse", "evses",
    "connectors", "connectorType", "operator", "network", "cpo",
}


def sanitize(value, depth=0):
    if depth > 4:
        return None
    if isinstance(value, list):
        return [sanitize(x, depth + 1) for x in value[:3]]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in ALLOW:
                out[k] = sanitize(v, depth + 1)
            elif isinstance(v, (dict, list)):
                nested = sanitize(v, depth + 1)
                if nested not in (None, {}, []):
                    out[k] = nested
        return out
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def safe_shape(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:50]
        out["collection_counts"] = {str(k): len(v) for k, v in obj.items() if isinstance(v, (list, dict))}
        out["collection_item_keys"] = {
            str(k): sorted(str(x) for x in v[0].keys())[:120]
            for k, v in obj.items() if isinstance(v, list) and v and isinstance(v[0], dict)
        }
        safe = sanitize(obj)
        if safe not in ({}, None):
            out["sanitized_public_sample"] = safe
        if isinstance(obj.get("message"), str):
            out["message"] = obj["message"][:500]
    return out


def request(path: str, label: str, payload: dict) -> dict:
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        method="POST",
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            body = res.read(250_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(250_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"path": path, "case": label, "status": None, "error_type": type(exc).__name__}
    return {"path": path, "case": label, "status": status, "content_type": ctype, "safe_response": safe_shape(body)}


def main():
    probes = [request(path, label, payload) for path in PATHS for label, payload in CASES]
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": HOST.removeprefix("https://"),
        "policy": {
            "read_only_query_endpoint": True,
            "no_login": True,
            "no_credentials": True,
            "no_coordinates_submitted": True,
            "no_account_or_session_mutations": True,
            "raw_response_bodies_persisted": False,
            "only_public_station_identifiers_tested": True,
        },
        "probes": probes,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"path": x["path"], "case": x["case"], "status": x.get("status")} for x in probes]))


if __name__ == "__main__":
    main()
