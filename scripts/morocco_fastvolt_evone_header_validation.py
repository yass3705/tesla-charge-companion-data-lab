#!/usr/bin/env python3
"""Read-only header-name validation for FastVolt and EVOne station endpoints.

Uses only deliberately invalid placeholder values to determine whether public client
headers recognized in the Android bundles change the anonymous validation response.
No credentials, real organisation identifiers, station IDs, query strings, account
data, or mutations are used or persisted.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

TARGETS = {
    "fastvolt": "https://mobile.ev.fastvolt.ma",
    "evone": "https://mobile.evplugv2.bornerecharge.ma",
}
PATH = "/app/charging_stations/"
CASES = [
    ("no_context_header", {}),
    ("x_client_placeholder", {"X-Client": "0"}),
    ("organization_placeholder", {"Organization": "0"}),
    ("organisation_code_placeholder", {"ORGANISATION_CODE": "0"}),
]
OUT = Path("artifacts/morocco-fastvolt-evone-header-validation")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

SAFE_MESSAGE_KEYS = {"message", "detail", "error", "errors"}


def sanitize_body(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:50]
        for key in SAFE_MESSAGE_KEYS:
            val = obj.get(key)
            if isinstance(val, str):
                out[key] = val[:300]
            elif isinstance(val, dict):
                # persist field names only, never values
                out[key + "_keys"] = sorted(str(k) for k in val.keys())[:50]
    return out


def probe(base: str, label: str, extra_headers: dict[str, str]) -> dict:
    headers = {"User-Agent": UA, "Accept": "application/json", **extra_headers}
    req = urllib.request.Request(base + PATH, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            body = res.read(100_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(100_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"case": label, "status": None, "error_type": type(exc).__name__}
    return {
        "case": label,
        "status": status,
        "content_type": ctype,
        "safe_response": sanitize_body(body),
    }


def main() -> None:
    apps = {}
    for name, base in TARGETS.items():
        apps[name] = {
            "host": base.removeprefix("https://"),
            "path": PATH,
            "probes": [probe(base, label, hdrs) for label, hdrs in CASES],
        }
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "read_only_get_only": True,
            "no_login": True,
            "no_credentials": True,
            "placeholder_header_values_only": True,
            "no_station_ids": True,
            "no_query_strings": True,
            "no_mutations": True,
            "raw_response_bodies_persisted": False,
        },
        "apps": apps,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: [{"case": p["case"], "status": p.get("status")} for p in v["probes"]] for k, v in apps.items()}))


if __name__ == "__main__":
    main()
