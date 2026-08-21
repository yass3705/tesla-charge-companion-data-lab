#!/usr/bin/env python3
"""Targeted anonymous GET-only probe for EVGO map/cluster route names.

Uses only the branded public backend and route names suggested by client symbols. No login,
credentials, query strings, coordinates submitted, station IDs submitted, POSTs or mutations.
Persists status/shape metadata plus a tightly whitelisted sample of public charging-infrastructure
fields when a public collection is returned.
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
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.1)"
ALLOW = {
    "id", "name", "title", "label", "status", "availability", "available",
    "latitude", "longitude", "lat", "lng", "power", "powerKw", "maxPower",
    "connectorType", "connectors", "evse", "evses", "locationId", "location_id",
    "operator", "network", "cpo", "currency", "tariff", "tariffs", "price", "free",
    "type", "icon", "image", "url",
}


def sanitize(value, depth=0):
    if depth > 3:
        return None
    if isinstance(value, list):
        return [sanitize(v, depth + 1) for v in value[:3]]
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


def collection_shape(name: str, value) -> dict:
    out = {"name": name, "type": type(value).__name__}
    if isinstance(value, list):
        out["count"] = len(value)
        if value and isinstance(value[0], dict):
            out["first_item_keys"] = sorted(str(k) for k in value[0].keys())[:100]
            sample = sanitize(value[:3])
            if sample not in (None, [], [{}]):
                out["sanitized_sample"] = sample
    elif isinstance(value, dict):
        out["count"] = len(value)
        out["keys"] = sorted(str(k) for k in value.keys())[:100]
        sample = sanitize(value)
        if sample not in (None, {}):
            out["sanitized_sample"] = sample
    return out


def safe_shape(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:40]
        out["collections"] = [collection_shape(str(k), v) for k, v in obj.items() if isinstance(v, (list, dict))]
        if isinstance(obj.get("message"), str):
            out["message"] = obj["message"][:300]
        if isinstance(obj.get("errors"), dict):
            out["error_fields"] = sorted(str(k) for k in obj["errors"].keys())[:40]
    elif isinstance(obj, list):
        out.update(collection_shape("root", obj))
    return out


def probe(path: str) -> dict:
    req = urllib.request.Request(HOST + path, method="GET", headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
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
        return {"path": path, "status": None, "error_type": type(exc).__name__}
    return {"path": path, "status": status, "content_type": ctype, "safe_response": safe_shape(body)}


def main():
    probes = [probe(p) for p in PATHS]
    report = {
        "schema_version": 2,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": "cp.evgo.ma",
        "policy": {
            "read_only_get_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_strings": True,
            "no_coordinates_submitted": True,
            "no_station_ids_submitted": True,
            "no_mutations": True,
            "raw_response_bodies_persisted": False,
            "only_whitelisted_public_charging_fields_sampled": True,
        },
        "probes": probes,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"path": x["path"], "status": x.get("status")} for x in probes]))


if __name__ == "__main__":
    main()
