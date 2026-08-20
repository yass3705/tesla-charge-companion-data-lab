#!/usr/bin/env python3
"""Sanitized read-only reachability probe for EVGO Morocco candidate app domains.

The public Android client contains cp.evgo.ma and evgo.ma strings in addition to the
confirmed AMPECO tenant. This probe performs only unauthenticated HTTPS GET requests
to root and known read-only app route shapes. It never logs in, mutates charging or
account state, submits coordinates, or persists response bodies/credentials.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOSTS = ["cp.evgo.ma", "evgo.ma"]
PATHS = [
    "/",
    "/api/v1/app/evses/search",
    "/api/v2/app/evses/search",
    "/api/v1/app/locations",
    "/api/v2/app/locations",
]
OUT = Path("artifacts/morocco-evgo-candidate-domains")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"


def safe_json_shape(body: str) -> dict:
    try:
        obj = json.loads(body)
    except Exception:
        return {"json": False}
    out = {"json": True}
    if isinstance(obj, dict):
        out["top_level_keys"] = sorted(str(k) for k in obj.keys())[:50]
        if isinstance(obj.get("message"), str):
            out["message"] = obj["message"][:300]
        if isinstance(obj.get("errors"), dict):
            out["error_fields"] = sorted(str(k) for k in obj["errors"].keys())[:50]
    elif isinstance(obj, list):
        out["list_length"] = len(obj)
    return out


def get(host: str, path: str) -> dict:
    url = f"https://{host}{path}"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = res.status
            ctype = res.headers.get("content-type", "")
            location = res.headers.get("location")
            body = res.read(100_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        location = exc.headers.get("location") if exc.headers else None
        try:
            body = exc.read(100_000).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as exc:
        return {"host": host, "path": path, "status": None, "error_type": type(exc).__name__}

    rec = {"host": host, "path": path, "status": status, "content_type": ctype}
    if location:
        # Persist only redirect path/host shape, not query strings.
        rec["redirect_location"] = location.split("?", 1)[0][:300]
    if "json" in ctype.lower() or body.lstrip().startswith(("{", "[")):
        rec["safe_response"] = safe_json_shape(body)
    return rec


def main() -> None:
    probes = [get(host, path) for host in HOSTS for path in PATHS]
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "read_only_get_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_parameters": True,
            "no_coordinates_submitted": True,
            "no_mutations": True,
            "raw_response_bodies_persisted": False,
        },
        "source_evidence": "Candidate domains cp.evgo.ma and evgo.ma were extracted from the public EVGO Android client.",
        "probes": probes,
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"host": p["host"], "path": p["path"], "status": p.get("status")} for p in probes]))


if __name__ == "__main__":
    main()
