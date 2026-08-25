#!/usr/bin/env python3
"""Conservative unauthenticated GET probe of Bump's production driver API.

Purpose: determine whether station/EVSE/tariff lookup used by the public driver app is readable
without a Bump account. The script uses one station/EVSE identifier from Bump's own IRVE dataset.
It never logs response bodies, credentials, cookies or query strings, and performs no write action.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_direct_inventory import DATASET_API, get_bytes, get_json, is_bump_operator, norm, resolve_csv_resource, decode_csv

BASE = "https://api.bump-charge.com"
OUT_JSON = Path("reports/bump/public_api_probe_latest.json")
OUT_MD = Path("reports/bump/public_api_probe_latest.md")
UA = "TeslaChargeCompanionDataLab/1.0 (read-only Bump public API discovery)"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sample_ids() -> dict[str, str]:
    dataset = get_json(DATASET_API)
    resource = resolve_csv_resource(dataset)
    rows, _ = decode_csv(get_bytes(str(resource.get("url") or resource.get("latest"))))
    rows = [r for r in rows if is_bump_operator(r.get("nom_operateur"))]
    if not rows:
        raise RuntimeError("No official Bump row available")
    # Prefer a row with both interoperable station and PDC IDs.
    rows.sort(key=lambda r: (not bool(norm(r.get("id_pdc_itinerance"))), not bool(norm(r.get("id_station_itinerance")))))
    r = rows[0]
    return {
        "station": norm(r.get("id_station_itinerance")) or norm(r.get("id_station_local")),
        "evse": norm(r.get("id_pdc_itinerance")) or norm(r.get("id_pdc_local")),
        "stationName": norm(r.get("nom_station")),
    }


def json_shape(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > 2_000_000:
        return {"parsed": False}
    try:
        obj = json.loads(raw)
    except Exception:
        return {"parsed": False}
    if isinstance(obj, dict):
        keys = sorted(str(k) for k in obj.keys())[:100]
        # One nested level of keys is enough to identify station/tariff payloads without retaining values.
        nested = {}
        for k, v in obj.items():
            if isinstance(v, dict):
                nested[str(k)] = sorted(str(x) for x in v.keys())[:50]
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                nested[str(k)] = sorted(str(x) for x in v[0].keys())[:50]
        return {"parsed": True, "type": "object", "keys": keys, "nestedKeys": nested}
    if isinstance(obj, list):
        keys = sorted(str(k) for k in obj[0].keys())[:100] if obj and isinstance(obj[0], dict) else []
        return {"parsed": True, "type": "array", "length": len(obj), "firstItemKeys": keys}
    return {"parsed": True, "type": type(obj).__name__}


def probe(path: str) -> dict[str, Any]:
    # Only same-origin GET requests; no query string and no auth header.
    assert path.startswith("/") and "?" not in path and "#" not in path
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}, method="GET")
    result: dict[str, Any] = {"path": path, "method": "GET"}
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            final = urllib.parse.urlsplit(r.geturl())
            if final.hostname != "api.bump-charge.com":
                return {**result, "status": "redirected_off_origin", "finalHost": final.hostname}
            body = r.read(2_000_001)
            result.update({
                "status": int(r.status),
                "contentType": (r.headers.get("Content-Type") or "").split(";", 1)[0],
                "responseBytesRead": len(body),
                "jsonShape": json_shape(body),
            })
    except urllib.error.HTTPError as e:
        body = e.read(100_000)
        result.update({
            "status": int(e.code),
            "contentType": (e.headers.get("Content-Type") or "").split(";", 1)[0],
            "responseBytesRead": len(body),
            "jsonShape": json_shape(body),
        })
    except Exception as e:
        result.update({"status": "network_error", "errorType": type(e).__name__})
    return result


def main() -> None:
    ids = sample_ids()
    station = urllib.parse.quote(ids["station"], safe="")
    evse = urllib.parse.quote(ids["evse"], safe="")

    # Small, bounded candidate set based on app strings plus conventional API metadata locations.
    paths = [
        "/",
        "/openapi.json",
        "/swagger.json",
        "/docs",
        "/health",
        f"/evse/{evse}",
        f"/evses/{evse}",
        f"/location/{station}",
        f"/locations/{station}",
        f"/charge-location/{station}",
        f"/charge-locations/{station}",
        f"/evse/{evse}/tariff",
        f"/evses/{evse}/tariff",
        f"/tariff/{evse}",
        f"/tariffs/{evse}",
    ]
    results = [probe(p) for p in paths]

    successful = [r for r in results if r.get("status") == 200]
    auth_required = [r for r in results if r.get("status") in (401, 403)]
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "bump-public-production-api-probe",
        "generatedAt": now_iso(),
        "base": BASE,
        "method": {
            "unauthenticated": True,
            "getOnly": True,
            "writeRequests": False,
            "responseBodiesPersisted": False,
            "queryStringsUsed": False,
            "sampleSource": "Bump official IRVE data.gouv dataset",
        },
        "sample": {
            "stationIdKind": "official IRVE station identifier",
            "evseIdKind": "official IRVE PDC identifier",
            "stationName": ids["stationName"],
            # IDs intentionally not persisted; only the kind/source is needed for the report.
        },
        "counts": {
            "requestCount": len(results),
            "http200Count": len(successful),
            "authRequiredCount": len(auth_required),
        },
        "results": results,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Bump production API — public GET probe",
        "",
        "One official Bump station/EVSE sample was used. Requests were unauthenticated GET only; no response body is retained.",
        "",
        f"- Requests: **{len(results)}**",
        f"- HTTP 200: **{len(successful)}**",
        f"- HTTP 401/403: **{len(auth_required)}**",
        "",
        "## Results",
        "",
    ]
    for r in results:
        shape = r.get("jsonShape") or {}
        suffix = ""
        if shape.get("parsed"):
            keys = shape.get("keys") or shape.get("firstItemKeys") or []
            if keys:
                suffix = " — JSON keys: " + ", ".join(keys[:25])
        lines.append(f"- `GET {r['path']}` → **{r.get('status')}**{suffix}")
    lines += [
        "",
        "## Decision",
        "",
        "A station/tariff route is usable for TCC only if it returns an explicit driver-facing tariff through an unauthenticated/read-only lookup and can be matched to Bump's official station/PDC inventory. Authentication barriers are not bypassed.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))


if __name__ == "__main__":
    main()
