#!/usr/bin/env python3
"""Sanitized read-only EVGO/AMPECO visible-operators route probe.

The public EVGO Android client contains a `getVisibleOperators` map-service symbol.
This probe tests a very small set of plausible GET-only mobile-app paths on the already
validated EVGO AMPECO tenant. It uses no login, credentials, query strings, coordinates,
station IDs, or mutations. Persisted output contains only HTTP status, response shape,
validation messages, and whitelisted public charging-network fields.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://evgo.eu-evgo.charge.ampeco.tech"
PATHS = [
    "/api/v1/app/operators",
    "/api/v2/app/operators",
    "/api/v1/app/operators/visible",
    "/api/v2/app/operators/visible",
    "/api/v1/app/visible-operators",
    "/api/v2/app/visible-operators",
    "/api/v1/app/map/operators",
    "/api/v2/app/map/operators",
]
OUT = Path("artifacts/morocco-evgo-visible-operators")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

ALLOW = {
    "id", "name", "title", "operator", "operators", "network", "networks",
    "cpo", "brand", "code", "status", "visible", "availability", "country",
    "countryCode", "country_code", "currency", "currencies",
}
BLOCK = (
    "token", "secret", "password", "authorization", "cookie", "email", "phone",
    "payment", "wallet", "account", "customer", "user", "bearer", "api_key", "apikey",
)


def sanitize(value, depth=0):
    if depth > 4:
        return None
    if isinstance(value, list):
        return [sanitize(x, depth + 1) for x in value[:10]]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            kl = str(key).lower()
            if any(x in kl for x in BLOCK):
                continue
            if key in ALLOW or kl in {x.lower() for x in ALLOW}:
                out[str(key)] = sanitize(item, depth + 1)
            elif isinstance(item, (dict, list)):
                nested = sanitize(item, depth + 1)
                if nested not in (None, {}, []):
                    out[str(key)] = nested
        return out
    if isinstance(value, str):
        return value[:300]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return None


def safe_shape(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = [str(k) for k in obj.keys() if not any(x in str(k).lower() for x in BLOCK)][:60]
        out["collection_counts"] = {
            str(k): len(v) for k, v in obj.items()
            if isinstance(v, (list, dict)) and not any(x in str(k).lower() for x in BLOCK)
        }
        out["collection_item_keys"] = {
            str(k): [str(x) for x in v[0].keys() if not any(b in str(x).lower() for b in BLOCK)][:80]
            for k, v in obj.items()
            if isinstance(v, list) and v and isinstance(v[0], dict)
        }
        if isinstance(obj.get("message"), str):
            out["message"] = obj["message"][:500]
        if isinstance(obj.get("errors"), dict):
            out["error_fields"] = [str(k) for k in obj["errors"].keys() if not any(x in str(k).lower() for x in BLOCK)][:40]
        safe = sanitize(obj)
        if safe not in ({}, None):
            out["sanitized_public_sample"] = safe
    elif isinstance(obj, list):
        out["list_count"] = len(obj)
        if obj and isinstance(obj[0], dict):
            out["item_keys"] = [str(k) for k in obj[0].keys() if not any(x in str(k).lower() for x in BLOCK)][:80]
        safe = sanitize(obj)
        if safe not in ([], None):
            out["sanitized_public_sample"] = safe
    return out


def request(path: str) -> dict:
    req = urllib.request.Request(
        HOST + path,
        method="GET",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            allow = res.headers.get("allow")
            body = res.read(250_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        allow = exc.headers.get("allow") if exc.headers else None
        try:
            body = exc.read(250_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"path": path, "status": None, "error_type": type(exc).__name__}
    rec = {"path": path, "status": status, "content_type": ctype, "safe_response": safe_shape(body)}
    if allow:
        rec["allow"] = allow
    return rec


def main():
    probes = [request(path) for path in PATHS]
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": HOST.removeprefix("https://"),
        "source_signal": "getVisibleOperators",
        "policy": {
            "read_only_get_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_strings": True,
            "no_coordinates": True,
            "no_station_ids": True,
            "no_mutations": True,
            "raw_response_bodies_persisted": False,
        },
        "probes": probes,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"path": p["path"], "status": p.get("status"), "allow": p.get("allow")} for p in probes]))


if __name__ == "__main__":
    main()
