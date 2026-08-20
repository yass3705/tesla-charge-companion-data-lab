#!/usr/bin/env python3
"""Sanitized, read-only EVGO/AMPECO validation-error probe.

The preceding prefix probe found that GET /api/v1/app/evses/search and
/api/v2/app/evses/search return HTTP 422 rather than 404. This probe calls only
those already-discovered read-only routes without credentials, query parameters
or request bodies, and persists only validation field names / error types. It
never stores raw response text or user/account data.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

HOST = "evgo.eu-evgo.charge.ampeco.tech"
PATHS = ["/api/v1/app/evses/search", "/api/v2/app/evses/search"]
OUT = Path("artifacts/morocco-evgo-ampeco-validation")
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.2)"
SAFE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,80}$")
SENSITIVE = re.compile(r"token|auth|cookie|password|secret|email|phone|user|account|payment|card", re.I)


def sanitize_scalar(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value if -1000000 <= value <= 1000000 else None
    if isinstance(value, str):
        # Keep only short schema-like identifiers or generic validation labels.
        if len(value) <= 100 and SAFE_FIELD.match(value) and not SENSITIVE.search(value):
            return value
    return None


def validation_shape(obj, depth=0):
    if depth > 5:
        return None
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            k = str(key)
            if SENSITIVE.search(k):
                continue
            if not SAFE_FIELD.match(k):
                continue
            nested = validation_shape(value, depth + 1)
            if nested not in (None, {}, []):
                out[k] = nested
        return out
    if isinstance(obj, list):
        vals = []
        for value in obj[:20]:
            nested = validation_shape(value, depth + 1)
            if nested not in (None, {}, []):
                vals.append(nested)
        return vals
    return sanitize_scalar(obj)


def probe(path: str) -> dict:
    url = f"https://{HOST}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read(20000)
            status = res.status
            ctype = res.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(20000)
        except Exception:
            body = b""
    except Exception as exc:
        return {"path": path, "status": None, "error": type(exc).__name__}

    result = {"path": path, "status": status, "content_type": ctype}
    if "json" in ctype.lower() and body:
        try:
            obj = json.loads(body.decode("utf-8", "replace"))
            result["validation_shape"] = validation_shape(obj)
            if isinstance(obj, dict):
                result["top_level_keys"] = [str(k) for k in obj.keys() if SAFE_FIELD.match(str(k)) and not SENSITIVE.search(str(k))][:30]
        except Exception:
            result["json_parse"] = "failed"
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    probes = [probe(path) for path in PATHS]
    result = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": HOST,
        "policy": {
            "read_only": True,
            "no_login": True,
            "no_mutations": True,
            "no_query_parameters": True,
            "no_credentials": True,
            "raw_response_bodies_persisted": False,
            "only_validation_schema_persisted": True,
        },
        "probes": probes,
        "interpretation": "A 422 response on these paths confirms route resolution and normally exposes only the missing/invalid request schema; this report stores identifiers only, never raw response bodies or credentials.",
    }
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"statuses": [p.get("status") for p in probes], "paths": PATHS}))


if __name__ == "__main__":
    main()
