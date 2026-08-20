#!/usr/bin/env python3
"""Sanitized, read-only EVGO/AMPECO mobile path-prefix probe.

Tests a very small set of plausible non-mutating path prefixes inferred from the
public EVGO client route strings. No login, credentials, query parameters,
request bodies, charging operations, or mutations are used. Response bodies are
never persisted; only HTTP status, content type, final path and coarse JSON shape
are recorded.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "evgo.eu-evgo.charge.ampeco.tech"
ROUTES = ["app/evses/search", "app/locations/withEVSE"]
PREFIXES = ["", "api", "api/v1", "api/v2", "mobile", "mobile/api", "mobile/api/v1"]
OUT = Path("artifacts/morocco-evgo-ampeco-prefix")
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.1)"


def safe_shape(body: bytes, content_type: str) -> dict:
    if "json" not in (content_type or "").lower():
        return {"type": "non_json", "sampled_bytes": len(body)}
    try:
        obj = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return {"type": "invalid_json", "sampled_bytes": len(body)}
    if isinstance(obj, dict):
        return {"type": "object", "keys": sorted(str(k) for k in obj.keys())[:30]}
    if isinstance(obj, list):
        return {"type": "array", "sampled_items": min(len(obj), 10)}
    return {"type": type(obj).__name__}


def probe(path: str) -> dict:
    url = f"https://{HOST}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read(20000)
            return {
                "path": "/" + path.lstrip("/"),
                "status": res.status,
                "final_path": urllib.parse.urlsplit(res.geturl()).path,
                "content_type": res.headers.get("content-type", ""),
                "json_shape": safe_shape(body, res.headers.get("content-type", "")),
            }
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(20000)
        except Exception:
            body = b""
        return {
            "path": "/" + path.lstrip("/"),
            "status": exc.code,
            "final_path": urllib.parse.urlsplit(exc.geturl()).path if exc.geturl() else "/" + path.lstrip("/"),
            "content_type": exc.headers.get("content-type", "") if exc.headers else "",
            "json_shape": safe_shape(body, exc.headers.get("content-type", "") if exc.headers else ""),
        }
    except Exception as exc:
        return {"path": "/" + path.lstrip("/"), "status": None, "error": type(exc).__name__}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    probes = []
    for prefix in PREFIXES:
        for route in ROUTES:
            path = "/".join(x for x in (prefix, route) if x)
            probes.append(probe(path))
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
            "response_bodies_persisted": False,
            "candidate_set_is_small_and_client_inferred": True,
        },
        "probes": probes,
        "interpretation": "HTTP 401/403 on a candidate may indicate a real route requiring normal app authentication; 404 suggests the tested prefix is not the mobile route shape. No authentication bypass is attempted.",
    }
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"host": HOST, "probe_count": len(probes), "statuses": [p.get("status") for p in probes]}))


if __name__ == "__main__":
    main()
