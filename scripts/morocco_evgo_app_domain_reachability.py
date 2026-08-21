#!/usr/bin/env python3
"""Read-only reachability probe for EVGO public domains exposed by the Android client.

GET probes use no credentials, station IDs, coordinates or query values. In addition, the
known read-only location-hydration route is tested with the inert payload {"locations": []}
only. The output retains status, content type, redirect target host/path, JSON top-level keys,
collection counts and short validation messages. Raw response bodies are never persisted.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path("artifacts/morocco-evgo-app-domain-reachability")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"
BASES = ["https://cp.evgo.ma", "https://evgo.ma"]
GET_PATHS = [
    "/",
    "/api/v1/app/evses/search",
    "/api/v2/app/evses/search",
    "/api/v1/app/locations",
    "/api/v2/app/locations",
]
POST_PATHS = ["/api/v1/app/locations", "/api/v2/app/locations"]
TOKENISH = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")


def safe_body(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:40]
        out["collection_counts"] = {
            str(k): len(v) for k, v in obj.items() if isinstance(v, (list, dict))
        }
        msg = obj.get("message")
        if isinstance(msg, str):
            out["message"] = TOKENISH.sub("[REDACTED]", msg)[:500]
        errors = obj.get("errors")
        if isinstance(errors, dict):
            out["error_keys"] = sorted(str(k) for k in errors.keys())[:30]
    return out


def request(base: str, path: str, method: str, payload: dict | None = None) -> dict:
    url = base + path
    headers = {"User-Agent": UA, "Accept": "application/json,text/plain,*/*"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, separators=(",", ":")).encode()
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            final = res.geturl()
            body = res.read(100_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        final = exc.geturl()
        try:
            body = exc.read(100_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"base": base, "path": path, "method": method, "status": None, "error_type": type(exc).__name__}
    q = urlsplit(final)
    return {
        "base": base,
        "path": path,
        "method": method,
        "status": status,
        "content_type": ctype,
        "final_host": q.hostname,
        "final_path": q.path,
        "safe_response": safe_body(body),
    }


def main() -> None:
    probes = []
    for base in BASES:
        probes.extend(request(base, path, "GET") for path in GET_PATHS)
        probes.extend(request(base, path, "POST", {"locations": []}) for path in POST_PATHS)
    report = {
        "schema_version": 2,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "read_only_queries_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_values": True,
            "no_coordinates": True,
            "no_station_ids": True,
            "post_payload_restricted_to_empty_locations_list": True,
            "no_charging_or_account_mutations": True,
            "raw_response_bodies_persisted": False,
        },
        "probes": probes,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"base": x["base"], "method": x["method"], "path": x["path"], "status": x.get("status"), "final_host": x.get("final_host")} for x in probes]))


if __name__ == "__main__":
    main()
