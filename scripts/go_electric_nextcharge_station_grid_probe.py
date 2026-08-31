#!/usr/bin/env python3
"""Read-only sample probe for the public NextCharge stationsGrid endpoint.

This reproduces the anonymous public map request discovered from the NextCharge
web frontend. It calls only the stationsGrid read path, over small Italian map
windows, and stores a compact/redacted schema sample for exact-EVSE research.
No session start/stop, payment, account, or mutation endpoint is reachable here.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT = "https://nextcharge.app/apps/map/apis/stationsGrid"
REFERER = "https://nextcharge.app/map?nextcharge=only"
USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
APP_VERSION = "6.1.4"
OWNER = "ITGES"
MAX_RESPONSE_BYTES = 8_000_000

# Deliberately small windows: enough to inspect response semantics without a
# national scrape. Rome/Milan/Bologna provide three independent Italian samples.
WINDOWS = [
    {"name": "rome", "lonSW": 12.35, "lonNE": 12.65, "latSW": 41.75, "latNE": 42.05},
    {"name": "milan", "lonSW": 9.05, "lonNE": 9.35, "latSW": 45.35, "latNE": 45.60},
    {"name": "bologna", "lonSW": 11.20, "lonNE": 11.50, "latSW": 44.40, "latNE": 44.60},
]

SENSITIVE_KEY_PARTS = (
    "token", "secret", "password", "cookie", "authorization", "card", "pan",
    "paymentmethod", "clientsecret", "accesskey",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_key(key: str) -> bool:
    low = key.lower().replace("_", "")
    return not any(part in low for part in SENSITIVE_KEY_PARTS)


def redact(value: Any, depth: int = 0, list_limit: int = 8) -> Any:
    if depth > 7:
        return "<depth-limit>"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            skey = str(key)
            if not safe_key(skey):
                out[skey] = "<redacted>"
            else:
                out[skey] = redact(item, depth + 1, list_limit)
        return out
    if isinstance(value, list):
        shown = [redact(x, depth + 1, list_limit) for x in value[:list_limit]]
        if len(value) > list_limit:
            shown.append({"_truncatedItems": len(value) - list_limit})
        return shown
    if isinstance(value, str):
        return value[:2000]
    return value


def schema(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "..."
    if isinstance(value, dict):
        return {str(k): schema(v, depth + 1) for k, v in list(value.items())[:80]}
    if isinstance(value, list):
        return [schema(value[0], depth + 1)] if value else []
    return type(value).__name__


def station_candidates(payload: Any) -> list[dict[str, Any]]:
    """Find station-like dicts without depending on one response schema."""
    found: list[dict[str, Any]] = []

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 7 or len(found) >= 20:
            return
        if isinstance(node, dict):
            keys = {str(k).lower() for k in node}
            stationish = any(k in keys for k in ("idstation", "stationid", "station_id"))
            geoish = any(k in keys for k in ("latitude", "lat")) and any(k in keys for k in ("longitude", "lng", "lon"))
            connectorish = any(k in keys for k in ("connectors", "evses", "sockets", "plugs"))
            if stationish or (geoish and connectorish):
                found.append(node)
                return
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node[:200]:
                walk(v, depth + 1)

    walk(payload)
    return found


def request_window(window: dict[str, Any]) -> dict[str, Any]:
    form = {
        "lonSW": window["lonSW"],
        "lonNE": window["lonNE"],
        "latSW": window["latSW"],
        "latNE": window["latNE"],
        "filterIsReady": "true",
        "includeNextcharge": "only",
        "favorites": "0",
        "userCountry": "IT",
        "owner": OWNER,
        "osType": "desktop",
        "appVersion": APP_VERSION,
        "idGroupProvider": "",
    }
    body = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "client-type": "webapp",
            "Origin": "https://nextcharge.app",
            "Referer": REFERER,
            "X-Requested-With": "XMLHttpRequest",
        },
    )

    result: dict[str, Any] = {
        "name": window["name"],
        "bounds": {k: window[k] for k in ("lonSW", "lonNE", "latSW", "latNE")},
        "request": {
            "endpoint": ENDPOINT,
            "method": "POST",
            "purpose": "anonymous public map station-grid read",
            "form": form,
        },
    }
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("stationsGrid response exceeds safety limit")
            text = raw.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
            result["httpStatus"] = resp.status
            result["contentType"] = str(resp.headers.get("Content-Type") or "")
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_RESPONSE_BYTES + 1)
        text = raw.decode("utf-8", errors="replace")
        result["httpStatus"] = exc.code
        result["httpError"] = str(exc.reason)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result["responseBytes"] = len(text.encode("utf-8"))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        result["json"] = False
        result["bodyPrefix"] = text[:4000]
        return result

    result["json"] = True
    result["topLevelType"] = type(payload).__name__
    result["topLevelKeys"] = list(payload.keys())[:100] if isinstance(payload, dict) else None
    result["responseSchema"] = schema(payload)
    candidates = station_candidates(payload)
    result["stationCandidateCountInSample"] = len(candidates)
    result["stationSamples"] = [redact(x, list_limit=5) for x in candidates[:5]]

    # Keep a very small redacted top-level sample for structures where our
    # heuristic does not yet recognize the station collection.
    result["redactedTopLevelSample"] = redact(payload, list_limit=3)
    return result


def main() -> None:
    reports = [request_window(w) for w in WINDOWS]
    payload = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "allowedEndpoint": ENDPOINT,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "nationalScrape": False,
            "smallSampleWindows": [w["name"] for w in WINDOWS],
        },
        "frontendContract": {
            "owner": OWNER,
            "appVersion": APP_VERSION,
            "osType": "desktop",
            "userCountry": "IT",
            "includeNextcharge": "only",
        },
        "windows": reports,
    }
    out = Path("artifacts/go_electric_nextcharge_station_grid_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps([
        {
            "name": r["name"],
            "status": r.get("httpStatus"),
            "bytes": r.get("responseBytes"),
            "json": r.get("json"),
            "topLevelKeys": r.get("topLevelKeys"),
            "stationCandidates": r.get("stationCandidateCountInSample"),
            "error": r.get("error"),
        }
        for r in reports
    ], ensure_ascii=False, indent=2))

    if not any(r.get("httpStatus") == 200 and r.get("json") is True for r in reports):
        raise SystemExit("no successful JSON stationsGrid sample")


if __name__ == "__main__":
    main()
