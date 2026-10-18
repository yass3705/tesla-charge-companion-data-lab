#!/usr/bin/env python3
"""Stateful REVE tariff/status stream collector.

Modes:
  --seed-probe  Merge the already-paid page-1 live probe into persistent stores.
                Zero network requests. Idempotent and never rewinds cursors.
  --collect     Fetch at most five pages total, preferring three tariff pages and
                two operational-status pages while both streams remain open.

This collector never calls /locations and never publishes TCC runtime data.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import tempfile
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

DATA = Path(os.environ.get("REVE_DATA_DIR", "data/spain_reve"))
PROBE = DATA / "live_tariff_status_probe.json"
STATE = DATA / "tariff_status_stream_state.json"
TARIFF_STORE = DATA / "reve_connector_tariffs_raw.json.gz"
STATUS_STORE = DATA / "reve_operational_status_raw.json.gz"
LAST_RUN = DATA / "tariff_status_stream_last_run.json"
BASE_URL = "https://www.mapareve.es/api/external/v1"
HARD_LIMIT = 5


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_gzip(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_gzip(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def default_state() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "country": "ES",
        "source": "REVE",
        "integrationStatus": "PRE_INTEGRATION_ONLY",
        "nextTariffPage": 1,
        "nextStatusPage": 1,
        "tariffTotalPages": None,
        "statusTotalPages": None,
        "tariffTotalCount": None,
        "statusTotalCount": None,
        "tariffRowsStored": 0,
        "statusRowsStored": 0,
        "tariffPagesCollected": [],
        "statusPagesCollected": [],
        "complete": False,
        "cooldownUntil": None,
        "updatedAt": None,
    }


def tariff_key(row: dict[str, Any]) -> str | None:
    connector = row.get("connector_id")
    return str(connector) if connector else None


def status_key(row: dict[str, Any]) -> str | None:
    internal = row.get("id")
    public = row.get("evse_id")
    if internal:
        return "id:" + str(internal)
    if public:
        return "evse:" + str(public)
    return None


def merge_rows(store: dict[str, Any], rows: Any, key_fn) -> tuple[int, int]:
    new = updated = 0
    if not isinstance(rows, list):
        return new, updated
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = key_fn(row)
        if not key:
            continue
        if key not in store:
            store[key] = row
            new += 1
        elif store[key] != row:
            store[key] = row
            updated += 1
    return new, updated


def header_int(headers: dict[str, Any], key: str) -> int | None:
    value = headers.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def retry_after_seconds(value: str | None) -> int:
    if not value:
        return 3600
    try:
        return max(60, int(value))
    except ValueError:
        try:
            return max(60, int((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 3600


def api_get(api_key: str, endpoint: str, page: int) -> dict[str, Any]:
    url = BASE_URL + endpoint + "?" + urllib.parse.urlencode({"page": page, "limit": 100})
    with tempfile.TemporaryDirectory(prefix="reve-stream-") as tmp:
        hp = Path(tmp) / "headers"
        bp = Path(tmp) / "body"
        proc = subprocess.run([
            "curl", "-sS", "--max-time", "120", "-D", str(hp), "-o", str(bp),
            "-H", f"x-api-key: {api_key}", "-H", "Accept: application/json", url,
        ], capture_output=True, text=True, check=False)
        htext = hp.read_text(encoding="utf-8", errors="replace") if hp.exists() else ""
        btext = bp.read_text(encoding="utf-8", errors="replace") if bp.exists() else ""

    status = 0
    headers: dict[str, str] = {}
    lines = htext.splitlines()
    block = -1
    for i, line in enumerate(lines):
        if line.startswith("HTTP/"):
            block = i
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                status = int(parts[1])
    if block >= 0:
        for line in lines[block + 1:]:
            if not line.strip():
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
    payload = None
    if btext:
        try:
            payload = json.loads(btext)
        except json.JSONDecodeError:
            pass
    return {
        "status": status,
        "headers": {k: headers[k] for k in ("total-count", "total-pages", "retry-after") if k in headers},
        "payload": payload,
        "transportExitCode": proc.returncode,
        "stderrPreview": (proc.stderr or "")[:300] or None,
        "bodyPreview": None if payload is not None else btext[:300],
    }


def normalize_state(state: dict[str, Any], tariffs: dict[str, Any], statuses: dict[str, Any]) -> None:
    state["tariffRowsStored"] = len(tariffs)
    state["statusRowsStored"] = len(statuses)
    tp = state.get("tariffTotalPages")
    sp = state.get("statusTotalPages")
    tariff_done = isinstance(tp, int) and state.get("nextTariffPage", 1) > tp
    status_done = isinstance(sp, int) and state.get("nextStatusPage", 1) > sp
    state["complete"] = bool(tariff_done and status_done)
    state["updatedAt"] = now()


def seed_probe() -> int:
    probe = load_json(PROBE, {})
    if not probe.get("probeComplete"):
        raise SystemExit("Cannot seed: live probe is not complete")
    state = load_json(STATE, default_state())
    tariffs = load_gzip(TARIFF_STORE)
    statuses = load_gzip(STATUS_STORE)
    seeded = {"tariffs": {}, "operationalStatus": {}}
    for req in probe.get("requests", []):
        kind = req.get("kind")
        if kind == "tariffs_page":
            n, u = merge_rows(tariffs, req.get("payload"), tariff_key)
            headers = req.get("headers") or {}
            state["tariffTotalPages"] = header_int(headers, "total-pages") or state.get("tariffTotalPages")
            pages = set(state.get("tariffPagesCollected") or [])
            pages.add(1)
            state["tariffPagesCollected"] = sorted(pages)
            state["nextTariffPage"] = max(int(state.get("nextTariffPage") or 1), 2)
            seeded["tariffs"] = {"new": n, "updated": u}
        elif kind == "operational_status_page":
            n, u = merge_rows(statuses, req.get("payload"), status_key)
            headers = req.get("headers") or {}
            state["statusTotalPages"] = header_int(headers, "total-pages") or state.get("statusTotalPages")
            pages = set(state.get("statusPagesCollected") or [])
            pages.add(1)
            state["statusPagesCollected"] = sorted(pages)
            state["nextStatusPage"] = max(int(state.get("nextStatusPage") or 1), 2)
            seeded["operationalStatus"] = {"new": n, "updated": u}
    normalize_state(state, tariffs, statuses)
    save_gzip(TARIFF_STORE, tariffs)
    save_gzip(STATUS_STORE, statuses)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LAST_RUN.write_text(json.dumps({
        "mode": "seed-probe", "networkRequests": 0, "generatedAt": now(), "seeded": seeded,
        "stateAfter": state,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"networkRequests": 0, "seeded": seeded, "state": state}, indent=2))
    return 0


def build_plan(state: dict[str, Any]) -> list[tuple[str, int]]:
    plan: list[tuple[str, int]] = []
    tariff_page = int(state.get("nextTariffPage") or 1)
    status_page = int(state.get("nextStatusPage") or 1)
    tariff_total = state.get("tariffTotalPages")
    status_total = state.get("statusTotalPages")
    tariff_open = not isinstance(tariff_total, int) or tariff_page <= tariff_total
    status_open = not isinstance(status_total, int) or status_page <= status_total

    # Prefer 3 tariff + 2 status pages while both streams are open.
    if tariff_open and status_open:
        for i in range(3):
            if not isinstance(tariff_total, int) or tariff_page + i <= tariff_total:
                plan.append(("tariffs", tariff_page + i))
        for i in range(2):
            if not isinstance(status_total, int) or status_page + i <= status_total:
                plan.append(("status", status_page + i))
    elif tariff_open:
        for i in range(HARD_LIMIT):
            if not isinstance(tariff_total, int) or tariff_page + i <= tariff_total:
                plan.append(("tariffs", tariff_page + i))
    elif status_open:
        for i in range(HARD_LIMIT):
            if not isinstance(status_total, int) or status_page + i <= status_total:
                plan.append(("status", status_page + i))
    return plan[:HARD_LIMIT]


def validate_checkpoint(state: dict[str, Any], tariffs: dict[str, Any], statuses: dict[str, Any]) -> None:
    for stream, store in (("tariff", tariffs), ("status", statuses)):
        pages = state.get(f"{stream}PagesCollected") or []
        next_page = state.get(f"next{stream.title()}Page")
        if pages != list(range(1, next_page)):
            raise ValueError(f"REVE {stream} checkpoint has missing pages")
        if len(store) != state.get(f"{stream}RowsStored"):
            raise ValueError(f"REVE {stream} checkpoint row count differs from store")
        if pages and not store:
            raise ValueError(f"REVE {stream} checkpoint has no rows")
        total_pages = state.get(f"{stream}TotalPages")
        if total_pages is not None and (not isinstance(total_pages, int) or total_pages < 1):
            raise ValueError(f"REVE {stream} total pages invalid")
        if state.get("complete"):
            total_count = state.get(f"{stream}TotalCount")
            if not isinstance(total_count, int) or total_count < 1 or len(store) != total_count:
                raise ValueError(f"REVE {stream} complete count differs from supplier total")
    if state.get("complete") and not (tariffs and statuses):
        raise ValueError("REVE complete checkpoint has an empty stream")


def collect() -> int:
    api_key = os.getenv("REVE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("REVE_API_KEY is not configured")
    state = load_json(STATE, default_state())
    tariffs = load_gzip(TARIFF_STORE)
    statuses = load_gzip(STATUS_STORE)
    validate_checkpoint(state, tariffs, statuses)
    cooldown = state.get("cooldownUntil")
    waiting = bool(cooldown and datetime.fromisoformat(cooldown.replace("Z", "+00:00")) > datetime.now(timezone.utc))
    plan = [] if waiting else build_plan(state)
    report: dict[str, Any] = {
        "mode": "collect", "generatedAt": now(), "hardRequestLimit": HARD_LIMIT,
        "requestsAttempted": 0, "requestsSucceeded": 0, "requests": [], "plan": plan,
        "integrationStatus": "PRE_INTEGRATION_ONLY",
    }

    if not plan:
        normalize_state(state, tariffs, statuses)
        report["note"] = "Waiting for REVE Retry-After" if waiting else "Both streams already complete"
    for stream, page in plan:
        if report["requestsAttempted"] >= HARD_LIMIT:
            break
        endpoint = "/connectors/tariffs" if stream == "tariffs" else "/evses/operational_status"
        result = api_get(api_key, endpoint, page)
        report["requestsAttempted"] += 1
        entry = {"stream": stream, "page": page, "endpoint": endpoint, "status": result["status"], "headers": result["headers"]}
        report["requests"].append(entry)
        if result["status"] != 200 or not isinstance(result["payload"], list):
            if result["status"] == 429:
                delay = retry_after_seconds(result["headers"].get("retry-after"))
                state["cooldownUntil"] = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            entry["error"] = {"transportExitCode": result["transportExitCode"], "stderrPreview": result["stderrPreview"], "bodyPreview": result["bodyPreview"]}
            report["stoppedAfterError"] = True
            break
        if not result["payload"] and (not isinstance(state.get("tariffTotalPages" if stream == "tariffs" else "statusTotalPages"), int) or page <= state.get("tariffTotalPages" if stream == "tariffs" else "statusTotalPages")):
            entry["error"] = "empty page before known end"
            report["stoppedAfterError"] = True
            break
        keys = [tariff_key(row) if stream == "tariffs" else status_key(row) for row in result["payload"] if isinstance(row, dict)]
        if len(keys) != len(result["payload"]) or any(not key for key in keys):
            entry["error"] = "missing exact connector or EVSE identity"
            report["stoppedAfterError"] = True
            break
        report["requestsSucceeded"] += 1
        if stream == "tariffs":
            n, u = merge_rows(tariffs, result["payload"], tariff_key)
            state["tariffTotalPages"] = header_int(result["headers"], "total-pages") or state.get("tariffTotalPages")
            state["tariffTotalCount"] = header_int(result["headers"], "total-count") or state.get("tariffTotalCount")
            pages = set(state.get("tariffPagesCollected") or [])
            pages.add(page)
            state["tariffPagesCollected"] = sorted(pages)
            state["nextTariffPage"] = max(int(state.get("nextTariffPage") or 1), page + 1)
        else:
            n, u = merge_rows(statuses, result["payload"], status_key)
            state["statusTotalPages"] = header_int(result["headers"], "total-pages") or state.get("statusTotalPages")
            state["statusTotalCount"] = header_int(result["headers"], "total-count") or state.get("statusTotalCount")
            pages = set(state.get("statusPagesCollected") or [])
            pages.add(page)
            state["statusPagesCollected"] = sorted(pages)
            state["nextStatusPage"] = max(int(state.get("nextStatusPage") or 1), page + 1)
        entry["rowsReceived"] = len(result["payload"])
        entry["newRows"] = n
        entry["updatedRows"] = u

    normalize_state(state, tariffs, statuses)
    validate_checkpoint(state, tariffs, statuses)
    report["stateAfter"] = state
    DATA.mkdir(parents=True, exist_ok=True)
    save_gzip(TARIFF_STORE, tariffs)
    save_gzip(STATUS_STORE, statuses)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LAST_RUN.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"requestsAttempted": report["requestsAttempted"], "requestsSucceeded": report["requestsSucceeded"], "state": state}, indent=2))
    return 0 if report["requestsAttempted"] == report["requestsSucceeded"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed-probe", action="store_true")
    group.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    return seed_probe() if args.seed_probe else collect()


if __name__ == "__main__":
    raise SystemExit(main())
