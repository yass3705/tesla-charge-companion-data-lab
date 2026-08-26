#!/usr/bin/env python3
"""Probe Bump's public map read endpoints with one official Bump-operated station.

Bounded, unauthenticated, read-only discovery. Only public technical charging data are retained.
No credentials, cookies, account data, payment data, session data or mutations are used.
"""
from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_direct_inventory import DATASET_API, decode_csv, get_bytes, get_json, is_bump_operator, norm, resolve_csv_resource

BASE = "https://api.bump-charge.com"
OUT_JSON = Path("reports/bump/public_map_probe_latest.json")
OUT_MD = Path("reports/bump/public_map_probe_latest.md")
UA = "TeslaChargeCompanionDataLab/1.0 (public Bump map tariff discovery)"

SAFE_KEY_RE = re.compile(r"(id|identifier|reference|tariff|price|currency|operator|roaming|power|name|status|latitude|longitude|coordinate|connector)", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_coords(value: Any) -> tuple[float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            lon, lat = float(value[0]), float(value[1])
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                return lat, lon
        except Exception:
            return None
    s = norm(value)
    if not s:
        return None
    try:
        obj = json.loads(s)
        got = parse_coords(obj)
        if got:
            return got
    except Exception:
        pass
    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if len(nums) >= 2:
        a, b = float(nums[0]), float(nums[1])
        # IRVE coordonneesXY is conventionally [longitude, latitude].
        if -180 <= a <= 180 and -90 <= b <= 90:
            return b, a
    return None


def sample_station() -> dict[str, Any]:
    ds = get_json(DATASET_API)
    res = resolve_csv_resource(ds)
    rows, _ = decode_csv(get_bytes(str(res.get("url") or res.get("latest"))))
    candidates = []
    for r in rows:
        if not is_bump_operator(r.get("nom_operateur")):
            continue
        coords = parse_coords(r.get("coordonneesXY"))
        if not coords:
            continue
        station = norm(r.get("id_station_itinerance")) or norm(r.get("id_station_local"))
        evse = norm(r.get("id_pdc_itinerance")) or norm(r.get("id_pdc_local"))
        if station and evse:
            candidates.append((station, evse, coords, r))
    if not candidates:
        raise RuntimeError("No official Bump sample with coordinates and interoperable identifiers")
    candidates.sort(key=lambda x: (x[0], x[1]))
    station, evse, (lat, lon), r = candidates[0]
    return {
        "stationIdentifier": station,
        "evseIdentifier": evse,
        "stationName": norm(r.get("nom_station")),
        "powerKw": norm(r.get("puissance_nominale")),
        "latitude": lat,
        "longitude": lon,
    }


def safe_projection(value: Any, depth: int = 0) -> Any:
    if depth > 7:
        return None
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if SAFE_KEY_RE.search(str(k)):
                if isinstance(v, (dict, list)):
                    projected = safe_projection(v, depth + 1)
                    if projected not in (None, {}, []):
                        out[str(k)] = projected
                elif isinstance(v, (str, int, float, bool)) or v is None:
                    out[str(k)] = v
            elif isinstance(v, (dict, list)):
                projected = safe_projection(v, depth + 1)
                if projected not in (None, {}, []):
                    out[str(k)] = projected
        return out
    if isinstance(value, list):
        return [x for x in (safe_projection(v, depth + 1) for v in value[:100]) if x not in (None, {}, [])]
    return value if isinstance(value, (str, int, float, bool)) or value is None else None


def collect_key_values(value: Any, regex: re.Pattern[str], limit: int = 100) -> list[Any]:
    out = []
    def walk(v: Any):
        if len(out) >= limit:
            return
        if isinstance(v, dict):
            for k, x in v.items():
                if regex.search(str(k)) and isinstance(x, (str, int, float, bool)) and x not in (None, ""):
                    out.append(x)
                    if len(out) >= limit:
                        return
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
                if len(out) >= limit:
                    return
    walk(value)
    dedup = []
    seen = set()
    for x in out:
        marker = json.dumps(x, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            seen.add(marker)
            dedup.append(x)
    return dedup


def contains_sample(value: Any, sample: dict[str, Any]) -> bool:
    needles = {sample["stationIdentifier"], sample["evseIdentifier"]}
    def walk(v: Any) -> bool:
        if isinstance(v, dict):
            return any(walk(x) for x in v.values())
        if isinstance(v, list):
            return any(walk(x) for x in v)
        if isinstance(v, str):
            return any(n in v for n in needles)
        return False
    return walk(value)


def post(path: str, body: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any]:
    assert path.startswith("/v") and "?" not in path
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
    )
    result: dict[str, Any] = {"path": path, "bodyVariant": body}
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read(2_000_001)
            result["status"] = int(r.status)
            result["contentType"] = (r.headers.get("Content-Type") or "").split(";", 1)[0]
    except urllib.error.HTTPError as e:
        raw = e.read(500_000)
        result["status"] = int(e.code)
        result["contentType"] = (e.headers.get("Content-Type") or "").split(";", 1)[0]
    except Exception as e:
        result.update({"status": "network_error", "errorType": type(e).__name__})
        return result
    result["responseBytesRead"] = len(raw)
    if len(raw) > 2_000_000:
        result["truncated"] = True
        return result
    try:
        obj = json.loads(raw)
    except Exception:
        result["jsonParsed"] = False
        return result
    result["jsonParsed"] = True
    result["responseType"] = "object" if isinstance(obj, dict) else "array" if isinstance(obj, list) else type(obj).__name__
    if isinstance(obj, dict):
        result["topLevelKeys"] = sorted(str(k) for k in obj.keys())[:100]
    result["containsOfficialSampleId"] = contains_sample(obj, sample)
    result["tariffGroupValues"] = collect_key_values(obj, re.compile(r"tariff.*group|group.*tariff", re.I), 50)
    result["tariffValues"] = collect_key_values(obj, re.compile(r"tariff|price|currency", re.I), 100)
    result["identifierValues"] = collect_key_values(obj, re.compile(r"(^id$|identifier|evse.*id|location.*id|chargepoint.*id)", re.I), 100)
    projected = safe_projection(obj)
    # Bound persisted projection size to avoid accidentally storing the whole map payload.
    encoded = json.dumps(projected, ensure_ascii=False)
    if len(encoded) <= 120_000:
        result["safeProjection"] = projected
    else:
        result["safeProjectionOmittedTooLarge"] = True
    return result


def main() -> None:
    s = sample_station()
    lat, lon = s["latitude"], s["longitude"]
    # Bounded variants based on strings present in the public app binary: latitude, longitude, filters.
    filter_variants = [
        {},
        {"latitude": lat, "longitude": lon},
        {"latitude": lat, "longitude": lon, "filters": []},
        {"latitude": lat, "longitude": lon, "filters": {}},
        {"latitude": lat, "longitude": lon, "radius": 5, "filters": []},
        {"northEast": {"latitude": lat + 0.02, "longitude": lon + 0.02}, "southWest": {"latitude": lat - 0.02, "longitude": lon - 0.02}, "filters": []},
    ]
    single_variants = [
        {"identifier": s["evseIdentifier"]},
        {"identifier": s["stationIdentifier"]},
        {"evseIdentifier": s["evseIdentifier"]},
        {"stationIdentifier": s["stationIdentifier"]},
        {"latitude": lat, "longitude": lon},
    ]
    attempts = []
    for path in ("/v1/maps/chargepoints/filter", "/v2/maps/chargepoints/filter"):
        for body in filter_variants:
            attempts.append(post(path, body, s))
    for path in ("/v1/maps/chargepoints/single", "/v1/maps/chargepoints/cluster"):
        for body in single_variants:
            attempts.append(post(path, body, s))

    useful = [a for a in attempts if a.get("status") == 200 and (a.get("containsOfficialSampleId") or a.get("tariffGroupValues") or a.get("tariffValues"))]
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "bump-public-map-probe",
        "generatedAt": now_iso(),
        "method": {
            "unauthenticated": True,
            "publicReadOnlySearchOnly": True,
            "postUsedForSearchEndpointsOnly": True,
            "credentialsUsed": False,
            "cookiesUsed": False,
            "mutationsUsed": False,
            "personalDataQueried": False,
            "sampleFromOfficialBumpIrve": True,
        },
        "sample": s,
        "attemptCount": len(attempts),
        "http200Count": sum(1 for a in attempts if a.get("status") == 200),
        "usefulCount": len(useful),
        "useful": useful,
        "attempts": [{k: v for k, v in a.items() if k != "safeProjection"} for a in attempts],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Bump public map endpoint probe",
        "",
        "Unauthenticated, read-only map/search POST requests only, using one station from Bump's official IRVE inventory.",
        "",
        f"- Sample: **{s['stationName']}** / `{s['stationIdentifier']}` / `{s['evseIdentifier']}`",
        f"- Attempts: **{len(attempts)}**",
        f"- HTTP 200: **{payload['http200Count']}**",
        f"- Useful responses (official ID or tariff marker): **{len(useful)}**",
        "",
    ]
    for a in useful:
        lines += [
            f"## `{a['path']}`",
            "",
            f"- Body: `{json.dumps(a['bodyVariant'], ensure_ascii=False)}`",
            f"- Official sample ID present: **{a.get('containsOfficialSampleId')}**",
            f"- Tariff group values: `{a.get('tariffGroupValues')}`",
            f"- Tariff/price values: `{a.get('tariffValues')}`",
            f"- Identifier values (sample): `{(a.get('identifierValues') or [])[:20]}`",
            "",
        ]
    lines += [
        "## Decision rule",
        "",
        "TCC may use this route only if the public response can be deterministically matched to an official Bump-operated station/EVSE and exposes the internal identifiers needed to query an explicit driver-facing tariff. No authentication boundary is bypassed.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"attempts": len(attempts), "http200": payload["http200Count"], "useful": len(useful)}, indent=2))


if __name__ == "__main__":
    main()
