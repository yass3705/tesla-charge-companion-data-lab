#!/usr/bin/env python3
"""Sanitized GET-only EVGO/AMPECO tariff route probe.

Purpose: determine whether the branded public mobile backend exposes a read-only
anonymous tariff collection corresponding to the tariff UI/signals already found
in the public EVGO client. No login, credentials, query strings, station IDs or
mutating methods are used. Raw bodies are never persisted.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://cp.evgo.ma"
PATHS = [
    "/api/v1/app/tariffs",
    "/api/v2/app/tariffs",
    "/api/v1/app/tariffs/standard-tod",
    "/api/v2/app/tariffs/standard-tod",
]
OUT = Path("artifacts/morocco-evgo-tariff-routes")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

SAFE_KEYS = {
    "id", "name", "title", "currency", "currencyCode", "price", "amount",
    "unit", "type", "energy", "time", "session", "parking", "idle", "free",
    "elements", "components", "restrictions", "priceComponents", "tariffs",
}


def sanitize(value, depth=0):
    if depth > 4:
        return None
    if isinstance(value, list):
        return [sanitize(x, depth + 1) for x in value[:3]]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if str(k) in SAFE_KEYS:
                out[str(k)] = sanitize(v, depth + 1)
            elif isinstance(v, (dict, list)):
                nested = sanitize(v, depth + 1)
                if nested not in (None, {}, []):
                    out[str(k)] = nested
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
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:80]
        out["collection_counts"] = {
            str(k): len(v) for k, v in obj.items() if isinstance(v, (list, dict))
        }
        out["collection_item_keys"] = {
            str(k): sorted(str(x) for x in v[0].keys())[:120]
            for k, v in obj.items() if isinstance(v, list) and v and isinstance(v[0], dict)
        }
        sample = sanitize(obj)
        if sample not in (None, {}, []):
            out["sanitized_public_sample"] = sample
        if isinstance(obj.get("message"), str):
            out["message"] = obj["message"][:500]
    elif isinstance(obj, list):
        out["list_count"] = len(obj)
        if obj and isinstance(obj[0], dict):
            out["item_keys"] = sorted(str(k) for k in obj[0].keys())[:120]
        sample = sanitize(obj)
        if sample not in (None, {}, []):
            out["sanitized_public_sample"] = sample
    return out


def probe(path: str) -> dict:
    req = urllib.request.Request(
        HOST + path,
        method="GET",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            body = res.read(300_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(300_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"path": path, "status": None, "error_type": type(exc).__name__}
    return {
        "path": path,
        "status": status,
        "content_type": ctype,
        "safe_response": safe_shape(body),
    }


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": HOST.removeprefix("https://"),
        "policy": {
            "read_only_get_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_strings": True,
            "no_station_or_evse_ids": True,
            "no_mutations": True,
            "raw_response_bodies_persisted": False,
            "only_public_tariff_fields_persisted": True,
        },
        "probes": [probe(path) for path in PATHS],
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"path": x["path"], "status": x.get("status")} for x in report["probes"]]))


if __name__ == "__main__":
    main()
