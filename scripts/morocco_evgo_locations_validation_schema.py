#!/usr/bin/env python3
"""Read-only validation-schema probe for EVGO/AMPECO map locations.

The mobile app exposes /api/v1|v2/app/locations as POST-only. This script submits
only deliberately non-actionable validation payloads ({}, an empty locations list,
and a list containing an empty object) to discover the expected request shape.
It does not start charging, mutate account/session state, authenticate, or persist
raw response bodies or location/tariff values.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://evgo.eu-evgo.charge.ampeco.tech"
PATHS = ["/api/v1/app/locations", "/api/v2/app/locations"]
PAYLOADS = [
    ("empty_object", {}),
    ("empty_locations", {"locations": []}),
    ("empty_location_item", {"locations": [{}]}),
]
OUT = Path("artifacts/morocco-evgo-locations-validation-schema")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"


def _shape(value, depth: int = 0):
    """Return only structural metadata; never persist response values."""
    if depth > 3:
        return {"type": type(value).__name__}
    if isinstance(value, dict):
        out = {"type": "object", "keys": sorted(str(k) for k in value.keys())[:120]}
        child_shapes = {}
        for key, item in list(value.items())[:120]:
            if isinstance(item, (dict, list)):
                child_shapes[str(key)] = _shape(item, depth + 1)
        if child_shapes:
            out["children"] = child_shapes
        return out
    if isinstance(value, list):
        out = {"type": "array", "length": len(value)}
        if value:
            out["first_item_shape"] = _shape(value[0], depth + 1)
        return out
    return {"type": type(value).__name__}


def safe_shape(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True, "response_shape": _shape(obj)}
    if isinstance(obj, dict):
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:50]
        out["top_level_collection_counts"] = {
            str(k): len(v) for k, v in obj.items() if isinstance(v, (list, dict))
        }
        errors = obj.get("errors")
        if isinstance(errors, dict):
            out["error_fields"] = sorted(str(k) for k in errors.keys())[:100]
            out["error_messages"] = {
                str(k): [str(x)[:300] for x in v[:5]] if isinstance(v, list) else str(v)[:300]
                for k, v in list(errors.items())[:100]
            }
        msg = obj.get("message")
        if isinstance(msg, str):
            out["message"] = msg[:600]
    return out


def probe(path: str, label: str, payload: dict) -> dict:
    data = json.dumps(payload, separators=(",", ":")).encode()
    req = urllib.request.Request(
        HOST + path,
        data=data,
        method="POST",
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    status = None
    content_type = ""
    body = ""
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            status = res.status
            content_type = res.headers.get("content-type", "")
            body = res.read(180_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(180_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"path": path, "payload_case": label, "status": None, "error_type": type(exc).__name__}
    return {
        "path": path,
        "payload_case": label,
        "status": status,
        "content_type": content_type,
        "safe_validation_shape": safe_shape(body),
    }


def main() -> None:
    probes = [probe(path, label, payload) for path in PATHS for label, payload in PAYLOADS]
    report = {
        "schema_version": 3,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": HOST.removeprefix("https://"),
        "policy": {
            "read_only_query_endpoint": True,
            "validation_only_payloads": True,
            "no_real_coordinates_or_identifiers": True,
            "no_login": True,
            "no_credentials": True,
            "no_account_or_session_mutations": True,
            "raw_response_bodies_persisted": False,
            "response_values_persisted": False,
            "structural_metadata_only": True,
        },
        "probes": probes,
    }
    target = OUT / "summary.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"statuses": [{"path": x["path"], "case": x["payload_case"], "status": x.get("status")} for x in probes]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
