#!/usr/bin/env python3
"""Read-only sample probe for NextCharge public station detail records.

Consumes station IDs already discovered by the small Italy stationsGrid probe and
calls only the public station detail endpoint used by the web map. The output is
redacted and sample-limited. No charging, payment, account, reservation, or other
remote action endpoint is reachable from this script.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT = "https://nextcharge.app/apps/map/apis/station"
REFERER = "https://nextcharge.app/map?nextcharge=only"
USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
APP_VERSION = "6.1.4"
MAX_RESPONSE_BYTES = 4_000_000
MAX_STATIONS = 6

SENSITIVE_KEY_PARTS = (
    "token", "secret", "password", "cookie", "authorization", "card", "pan",
    "paymentmethod", "clientsecret", "accesskey", "nonce",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_key(key: str) -> bool:
    low = key.lower().replace("_", "")
    return not any(part in low for part in SENSITIVE_KEY_PARTS)


def redact(value: Any, depth: int = 0, list_limit: int = 12) -> Any:
    if depth > 9:
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
        return value[:4000]
    return value


def schema(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "..."
    if isinstance(value, dict):
        return {str(k): schema(v, depth + 1) for k, v in list(value.items())[:120]}
    if isinstance(value, list):
        return [schema(value[0], depth + 1)] if value else []
    return type(value).__name__


def extract_station_ids(grid_report: dict[str, Any]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for window in grid_report.get("windows") or []:
        name = str(window.get("name") or "unknown")
        for station in window.get("stationSamples") or []:
            if not isinstance(station, dict):
                continue
            sid = str(station.get("idStation") or "").strip()
            if not sid or any(x["idStation"] == sid for x in selected):
                continue
            selected.append({"window": name, "idStation": sid})
            # At most two samples from each window.
            if sum(x["window"] == name for x in selected) >= 2:
                break
        if len(selected) >= MAX_STATIONS:
            break
    return selected[:MAX_STATIONS]


def collect_key_paths(value: Any, prefix: str = "", depth: int = 0, out: set[str] | None = None) -> set[str]:
    if out is None:
        out = set()
    if depth > 8:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.add(path)
            collect_key_paths(child, path, depth + 1, out)
    elif isinstance(value, list) and value:
        collect_key_paths(value[0], f"{prefix}[]", depth + 1, out)
    return out


def detail_for(item: dict[str, str]) -> dict[str, Any]:
    sid = item["idStation"]
    form = {
        "idStation": sid,
        "osType": "desktop",
        "appVersion": APP_VERSION,
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
        **item,
        "request": {
            "endpoint": ENDPOINT,
            "method": "POST",
            "purpose": "anonymous public web-map station detail read",
            "form": form,
        },
    }
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("station detail response exceeds safety limit")
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
    result["keyPaths"] = sorted(collect_key_paths(payload))[:1200]
    result["redactedResponse"] = redact(payload, list_limit=12)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid-report", default="artifacts/go_electric_nextcharge_station_grid_probe.json")
    ap.add_argument("--out", default="artifacts/go_electric_nextcharge_station_detail_probe.json")
    args = ap.parse_args()

    grid = json.loads(Path(args.grid_report).read_text(encoding="utf-8"))
    ids = extract_station_ids(grid)
    if not ids:
        raise SystemExit("no station IDs available from grid probe")

    details = [detail_for(item) for item in ids]
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "allowedEndpoint": ENDPOINT,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "sampleLimit": MAX_STATIONS,
        },
        "inputStations": ids,
        "details": details,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps([
        {
            "window": d["window"],
            "idStation": d["idStation"],
            "status": d.get("httpStatus"),
            "bytes": d.get("responseBytes"),
            "json": d.get("json"),
            "keys": d.get("topLevelKeys"),
            "error": d.get("error"),
        }
        for d in details
    ], ensure_ascii=False, indent=2))

    successes = [d for d in details if d.get("httpStatus") == 200 and d.get("json") is True]
    if not successes:
        raise SystemExit("no successful JSON station-detail sample")


if __name__ == "__main__":
    main()
