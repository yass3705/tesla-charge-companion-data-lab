#!/usr/bin/env python3
"""Build a PDC-level Allego direct-status enrichment for canonical France IRVE.

Physical inventory remains national IRVE static. Allego DXP is queried only to
attach operational state to PDCs that already exist in the current IRVE source.
The only accepted identity mapping is:

    normalized id_pdc_itinerance == DXP chargePointId + EVSE visualId

Anything else is reported unmatched and never creates a station/PDC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from france_irve_canonical import IRVE_STATIC_URL, iter_csv_rows, norm_id, text

SPA = "https://app.allego.eu/price/FRALLEGO8001301"
API = "https://p-dxp-api-acg8edbwd7g2eheg.a01.azurefd.net/api/dxp/poi/chargepoints/"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", text(value).upper())


def normalize_allego_status(value: Any) -> str:
    raw = re.sub(r"[^a-z0-9]", "", text(value).lower())
    if raw in {
        "available",
        "occupied",
        "charging",
        "reserved",
        "preparing",
        "finishing",
    }:
        return "in_service"
    if raw in {
        "unavailable",
        "outofservice",
        "faulted",
        "offline",
        "inoperative",
    }:
        return "out_of_service"
    return "unknown"


def capture_public_client_key() -> str:
    # Selenium is imported lazily so unit tests for parsing/matching do not need it.
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    key = None
    try:
        driver.get(SPA)
        time.sleep(6)
        for item in driver.get_log("performance"):
            try:
                msg = json.loads(item["message"])["message"]
            except Exception:
                continue
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            req = msg.get("params", {}).get("request", {})
            if "p-dxp-api-" not in req.get("url", ""):
                continue
            for name, value in (req.get("headers") or {}).items():
                if name.lower() == "ocp-apim-subscription-key":
                    key = str(value)
                    break
            if key:
                break
    finally:
        driver.quit()
    if not key:
        raise RuntimeError("Allego public DXP client key was not observed")
    print("DXP public client configuration captured; sha256=" + hashlib.sha256(key.encode()).hexdigest())
    return key


def call_dxp(chargepoint_id: str, key: str) -> tuple[int, dict[str, Any] | None]:
    req = urllib.request.Request(
        API + chargepoint_id,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://app.allego.eu",
            "Referer": "https://app.allego.eu/",
            "Ocp-Apim-Subscription-Key": key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
            return response.status, payload if isinstance(payload, dict) else None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def collect_irve_allego_map(static_source: str) -> tuple[dict[str, dict[int, str]], Counter]:
    """Return chargePointId -> visualId -> exact canonical IRVE PDC id."""
    grouped: dict[str, dict[int, str]] = defaultdict(dict)
    stats = Counter()
    for row in iter_csv_rows(static_source):
        pdc = norm_id(row.get("id_pdc_itinerance"))
        compact = compact_id(pdc)
        if not compact.startswith("FRALLEGO"):
            continue
        stats["allego_irve_rows"] += 1
        if not re.fullmatch(r"FRALLEGO[A-Z0-9]+\d", compact):
            stats["invalid_pdc_pattern"] += 1
            continue
        chargepoint_id = compact[:-1]
        visual_id = int(compact[-1])
        if visual_id in grouped[chargepoint_id] and grouped[chargepoint_id][visual_id] != pdc:
            stats["identity_collision"] += 1
            continue
        grouped[chargepoint_id][visual_id] = pdc
        stats["mapped_irve_rows"] += 1
    stats["chargepoints"] = len(grouped)
    return dict(grouped), stats


def records_from_dxp(
    chargepoint_id: str,
    expected: dict[int, str],
    payload: dict[str, Any],
    observed_at: str,
) -> tuple[list[dict[str, Any]], Counter]:
    records: list[dict[str, Any]] = []
    stats = Counter()
    returned_cp = compact_id(payload.get("chargePointId"))
    if returned_cp != chargepoint_id:
        stats["chargepoint_id_mismatch"] += 1
        return records, stats

    evses = payload.get("evses")
    if not isinstance(evses, list):
        stats["missing_evses"] += 1
        return records, stats

    seen: set[int] = set()
    for evse in evses:
        if not isinstance(evse, dict):
            stats["invalid_evse"] += 1
            continue
        try:
            visual_id = int(evse.get("visualId"))
        except (TypeError, ValueError):
            stats["missing_visual_id"] += 1
            continue
        if visual_id in seen:
            stats["duplicate_visual_id"] += 1
            continue
        seen.add(visual_id)

        pdc_id = expected.get(visual_id)
        if not pdc_id:
            stats["dxp_evse_not_in_current_irve"] += 1
            continue

        raw_status = text(evse.get("status")) or text(payload.get("chargePointStatus")) or "Unknown"
        normalized = normalize_allego_status(raw_status)
        records.append(
            {
                "idPdcItinerance": pdc_id,
                "status": normalized,
                "rawStatus": raw_status,
                "asOf": observed_at,
                "sourceRecordId": f"{chargepoint_id}:{visual_id}",
                "matchMethod": "exact_chargepoint_visualid_to_irve_pdc",
                "matchConfidence": "exact",
                "offers": [],
            }
        )
        stats["records"] += 1
        stats[f"status_{normalized}"] += 1

    for visual_id in expected:
        if visual_id not in seen:
            stats["irve_pdc_missing_from_dxp_payload"] += 1
    return records, stats


def build(static_source: str, workers: int = 16, key: str | None = None) -> dict[str, Any]:
    mapping, stats = collect_irve_allego_map(static_source)
    if stats["identity_collision"]:
        raise RuntimeError("Allego identity collision in current IRVE source")
    if not mapping:
        raise RuntimeError("No Allego PDC found in current IRVE source")

    client_key = key or capture_public_client_key()
    observed_at = now_iso()
    records: list[dict[str, Any]] = []
    aggregate = Counter(stats)

    def fetch_one(cp: str):
        status, payload = call_dxp(cp, client_key)
        return cp, status, payload

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(fetch_one, cp) for cp in mapping]
        for future in as_completed(futures):
            cp, http_status, payload = future.result()
            aggregate["dxp_requests"] += 1
            aggregate[f"dxp_http_{http_status}"] += 1
            if http_status != 200 or not isinstance(payload, dict):
                aggregate["dxp_unresolved_chargepoints"] += 1
                continue
            recs, local = records_from_dxp(cp, mapping[cp], payload, observed_at)
            records.extend(recs)
            aggregate.update(local)

    records.sort(key=lambda r: r["idPdcItinerance"])
    return {
        "schemaVersion": "1.0.0",
        "sourceKind": "cpo_direct",
        "provider": "Allego",
        "generatedAt": observed_at,
        "scope": "france_current_irve_pdc_only",
        "identityRule": "IRVE id_pdc_itinerance == DXP chargePointId + EVSE visualId",
        "occupancyUsed": False,
        "records": records,
        "summary": dict(aggregate),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--static", default=IRVE_STATIC_URL)
    ap.add_argument("--out", default="out/france_irve_status_allego.json")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    payload = build(args.static, workers=args.workers)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
