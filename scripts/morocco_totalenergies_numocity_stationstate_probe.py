#!/usr/bin/env python3
"""Sanitized read-only probe for the TotalEnergies Morocco / Numocity station-state route.

The route `/chargestation/getstationstate` was recovered from the public Android client
near the official Numocity host marker. This probe performs GET requests only, without
login, credentials, real station IDs, charging actions, or account/session mutations.
It persists only HTTP status, content type, JSON top-level keys, validation-message text,
and collection/object key names. Placeholder values are deliberately invalid (`0`).
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "https://csmstotalenergiesma.numocity.com"
PATHS = [
    "/chargestation/getstationstate",
    "/api/chargestation/getstationstate",
]
CASES = [
    ("no_query", {}),
    ("stationId_placeholder", {"stationId": "0"}),
    ("stationid_placeholder", {"stationid": "0"}),
    ("id_placeholder", {"id": "0"}),
]
OUT = Path("artifacts/morocco-totalenergies-numocity-stationstate")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"
SAFE_MESSAGE_KEYS = {"message", "detail", "error", "errors", "status"}


def sanitize_body(body: str) -> dict:
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
            str(k): sorted(str(x) for x in v[0].keys())[:100]
            for k, v in obj.items()
            if isinstance(v, list) and v and isinstance(v[0], dict)
        }
        for key in SAFE_MESSAGE_KEYS:
            val = obj.get(key)
            if isinstance(val, str):
                out[key] = val[:500]
            elif isinstance(val, dict):
                out[key + "_keys"] = sorted(str(k) for k in val.keys())[:80]
    elif isinstance(obj, list):
        out["list_count"] = len(obj)
        if obj and isinstance(obj[0], dict):
            out["first_item_keys"] = sorted(str(k) for k in obj[0].keys())[:100]
    return out


def probe(path: str, label: str, query: dict[str, str]) -> dict:
    url = HOST + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            body = res.read(150_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(150_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"path": path, "case": label, "status": None, "error_type": type(exc).__name__}
    return {
        "path": path,
        "case": label,
        "status": status,
        "content_type": ctype,
        "safe_response": sanitize_body(body),
    }


def main() -> None:
    probes = [probe(path, label, query) for path in PATHS for label, query in CASES]
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": HOST.removeprefix("https://"),
        "source_signal": "public Android client static route /chargestation/getstationstate",
        "policy": {
            "read_only_get_only": True,
            "no_login": True,
            "no_credentials": True,
            "placeholder_values_only": True,
            "no_real_station_ids": True,
            "no_charging_actions": True,
            "no_account_or_session_mutations": True,
            "raw_response_bodies_persisted": False,
        },
        "probes": probes,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"path": p["path"], "case": p["case"], "status": p.get("status")} for p in probes]))


if __name__ == "__main__":
    main()
