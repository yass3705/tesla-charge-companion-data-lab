#!/usr/bin/env python3
"""Read-only comparison of public FastVolt backend hostnames.

Compares the previously observed mobile.ev.fastvolt.ma host with the publicly indexed
app.api.fastvolt.bornerecharge.ma host. Only anonymous GET requests are made, with no
query strings, station IDs, login, credentials, mutations or raw response persistence.
"""
from __future__ import annotations
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOSTS = {
    "current_observed": "https://mobile.ev.fastvolt.ma",
    "public_indexed_alternate": "https://app.api.fastvolt.bornerecharge.ma",
}
PATHS = ["/", "/app/charging_stations/"]
OUT = Path("reports/morocco/fastvolt/latest-public-host-compare.json")
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"


def safe_probe(base: str, path: str) -> dict:
    req = urllib.request.Request(base + path, method="GET", headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            body = res.read(20_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        try:
            body = exc.read(20_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"path": path, "status": None, "error_type": type(exc).__name__}

    summary = {"path": path, "status": status, "content_type": ctype}
    low = body.lower()
    summary["body_markers"] = [m for m in ("business", "organisation", "organization", "unauthorized", "unauthenticated", "fastvolt", "evplug") if m in low]
    if "application/json" in ctype.lower():
        try:
            obj = json.loads(body)
            if isinstance(obj, dict):
                summary["json_top_level_keys"] = sorted(str(k) for k in obj.keys())[:50]
        except Exception:
            pass
    return summary


def main() -> None:
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "read_only_get_only": True,
            "anonymous_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_strings": True,
            "no_station_ids": True,
            "no_mutations": True,
            "raw_response_bodies_persisted": False,
        },
        "hosts": {},
    }
    for label, base in HOSTS.items():
        report["hosts"][label] = {
            "host": base.removeprefix("https://"),
            "probes": [safe_probe(base, p) for p in PATHS],
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
