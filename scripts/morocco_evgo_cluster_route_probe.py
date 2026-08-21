#!/usr/bin/env python3
"""Targeted anonymous GET-only probe for EVGO map/cluster route names.

Uses only the branded public backend and route names suggested by client symbols. No login,
credentials, query strings, coordinates, station IDs, POSTs or mutations. Persists only
status codes, content type, JSON top-level keys and short validation/not-found messages.
"""
from __future__ import annotations
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://cp.evgo.ma"
PATHS = [
    "/api/v1/app/clusters", "/api/v2/app/clusters",
    "/api/v1/app/map/clusters", "/api/v2/app/map/clusters",
    "/api/v1/app/locations/clusters", "/api/v2/app/locations/clusters",
    "/api/v1/app/map", "/api/v2/app/map",
    "/api/v1/app/pins", "/api/v2/app/pins",
    "/api/v1/app/map/locations", "/api/v2/app/map/locations",
]
OUT = Path("artifacts/morocco-evgo-cluster-routes")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"


def safe_shape(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:40]
        if isinstance(obj.get("message"), str):
            out["message"] = obj["message"][:300]
        if isinstance(obj.get("errors"), dict):
            out["error_fields"] = sorted(str(k) for k in obj["errors"].keys())[:40]
    elif isinstance(obj, list):
        out["list_count"] = len(obj)
        if obj and isinstance(obj[0], dict):
            out["first_item_keys"] = sorted(str(k) for k in obj[0].keys())[:60]
    return out


def probe(path: str) -> dict:
    req = urllib.request.Request(HOST + path, method="GET", headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            body = res.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(200_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"path": path, "status": None, "error_type": type(exc).__name__}
    return {"path": path, "status": status, "content_type": ctype, "safe_response": safe_shape(body)}


def main():
    probes = [probe(p) for p in PATHS]
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": "cp.evgo.ma",
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
    print(json.dumps([{"path": x["path"], "status": x.get("status")} for x in probes]))


if __name__ == "__main__":
    main()
