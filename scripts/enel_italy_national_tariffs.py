#!/usr/bin/env python3
"""Build a national Enel X Way direct-tariff candidate joined to PUN Italy.

PUN is the authoritative national inventory. For each PUN ENX EVSE, its station
serial number is deterministically derived from the EVSE id and queried once
against Enel's public web-map station-detail endpoint. Enel currently returns
legacy EVO-prefixed EVSE ids; these are normalized to PUN's ENX prefix only when
the rest of the identifier is unchanged.

Safety / tariff rules:
- The public anonymous browser session is held only in process memory.
- No cookies, bearer values or raw response bodies are persisted.
- ``price`` is promoted only when currency=EUR and typePrice=KWH.
- ``directPaymenthPrice`` is retained as a separate candidate but is NOT made
  rankable until its consumer semantics are independently validated.
- penalty fields are retained raw but are NOT applied until their units and
  triggering rules are independently validated.
- Any unmatched or malformed EVSE fails closed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://d2jtbpdp94l0ts.cloudfront.net/?show_only_enel=true"
MAP_ENDPOINT = "https://emobility.enelx.com/api/emobility/v2/charging/station"
PUN_INPUT = Path("data/national/pun_italy_national.json.gz")
OUTPUT = Path("data/national/enel_direct_stations_italy.json.gz")
REPORT = Path("data/reports/enel_italy_national_tariffs_report.json")
USER_AGENT = "tesla-charge-companion-data-lab/enel-italy-national-1.0"
EVSE_RE = re.compile(r"^IT\*ENX\*E(.+)\*(\d+)$")
RETRY_CODES = {429, 500, 502, 503, 504}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite_number(value: Any) -> float | None:
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def cents_to_eur(value: Any) -> float | None:
    f = finite_number(value)
    if f is None or f < 0 or f > 1000:
        return None
    return round(f / 100.0, 6)


def canonical_enel_evse_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith("IT*EVO*"):
        return "IT*ENX*" + value[len("IT*EVO*"):]
    if value.startswith("IT*ENX*"):
        return value
    return None


def extract_serial(evse_id: str) -> str | None:
    match = EVSE_RE.match(evse_id)
    return match.group(1) if match else None


def extract_public_headers() -> dict[str, str]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(MAP_URL)
        time.sleep(12)
        requests_by_id: dict[str, dict[str, Any]] = {}
        extra_headers: dict[str, dict[str, str]] = {}
        for item in driver.get_log("performance"):
            try:
                msg = json.loads(item["message"])["message"]
            except Exception:
                continue
            method = msg.get("method")
            params = msg.get("params", {})
            rid = str(params.get("requestId") or "")
            if method == "Network.requestWillBeSent":
                requests_by_id[rid] = params.get("request", {})
            elif method == "Network.requestWillBeSentExtraInfo":
                extra_headers[rid] = {str(k): str(v) for k, v in (params.get("headers") or {}).items()}
        chosen_id = None
        chosen = None
        for rid, req in requests_by_id.items():
            url = str(req.get("url") or "")
            if url.startswith(MAP_ENDPOINT + "?") and str(req.get("method")) == "GET":
                chosen_id, chosen = rid, req
                break
        if not chosen:
            raise RuntimeError("Enel public map station request not observed")
        merged = {str(k): str(v) for k, v in (chosen.get("headers") or {}).items()}
        merged.update(extra_headers.get(chosen_id or "", {}))
        blocked = {
            "host", "content-length", "cookie", "referer", "origin",
            ":authority", ":method", ":path", ":scheme",
        }
        headers = {k: v for k, v in merged.items() if k.lower() not in blocked and not k.startswith(":")}
        headers["User-Agent"] = headers.get("User-Agent") or USER_AGENT
        return headers
    finally:
        driver.quit()


def get_detail(serial: str, headers: dict[str, str], attempts: int = 5) -> dict[str, Any]:
    url = MAP_ENDPOINT + "/" + quote(serial, safe="")
    last_error: str | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers=headers, timeout=35)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(8.0, 0.5 * (2 ** attempt)))
            continue
        if response.status_code in RETRY_CODES:
            last_error = f"HTTP {response.status_code}"
            time.sleep(min(8.0, 0.5 * (2 ** attempt)))
            continue
        if response.status_code != 200:
            return {"ok": False, "serial": serial, "httpStatus": response.status_code, "error": "http_error"}
        try:
            payload = response.json()
        except Exception:
            return {"ok": False, "serial": serial, "httpStatus": 200, "error": "non_json_response"}
        if not isinstance(payload, dict):
            return {"ok": False, "serial": serial, "httpStatus": 200, "error": "unexpected_json_type"}
        result = payload.get("result")
        if payload.get("code") != 200 or not isinstance(result, dict):
            return {
                "ok": False,
                "serial": serial,
                "httpStatus": 200,
                "businessCode": payload.get("code"),
                "businessMessage": payload.get("message"),
                "error": "empty_or_business_error",
            }
        return {"ok": True, "serial": serial, "result": result}
    return {"ok": False, "serial": serial, "error": last_error or "retry_exhausted"}


def normalize_plug(
    serial: str,
    station_result: dict[str, Any],
    evse: dict[str, Any],
    plug: dict[str, Any],
    pun_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw_evse_id = evse.get("evseId")
    pun_evse_id = canonical_enel_evse_id(raw_evse_id)
    if not pun_evse_id or pun_evse_id not in pun_index:
        return None, {
            "serial": serial,
            "rawEnelEvseId": raw_evse_id if isinstance(raw_evse_id, str) else None,
            "normalizedEvseId": pun_evse_id,
            "reason": "not_found_in_pun_enx",
        }
    pun = pun_index[pun_evse_id]
    currency = str(plug.get("currency") or "").upper() or None
    price_type = str(plug.get("typePrice") or "").upper() or None
    raw_price = finite_number(plug.get("price"))
    operator_eur_kwh = cents_to_eur(raw_price) if currency == "EUR" and price_type == "KWH" else None
    direct_type = str(plug.get("directPaymenthTypePrice") or "").upper() or None
    direct_eur_kwh = cents_to_eur(plug.get("directPaymenthPrice")) if currency == "EUR" and direct_type == "KWH" else None
    enel_power = finite_number(plug.get("maxPower"))
    pun_power = finite_number(pun.get("maxPowerKw"))
    power_delta = abs(enel_power - pun_power) if enel_power is not None and pun_power is not None else None
    return {
        "evseId": pun_evse_id,
        "rawEnelEvseId": raw_evse_id,
        "stationSerialNumber": serial,
        "enelStationId": station_result.get("csId"),
        "stationName": station_result.get("csName"),
        "operator": pun.get("operator"),
        "partyId": pun.get("partyId"),
        "coordinates": pun.get("coordinates"),
        "punStatus": pun.get("sourceStatus"),
        "punOperationalState": pun.get("operationalState"),
        "enelStationStatus": station_result.get("status"),
        "enelEvseStatus": evse.get("status"),
        "enelPlugStatus": plug.get("status"),
        "connector": {
            "plugId": plug.get("plugId"),
            "typology": plug.get("typology"),
            "maxPowerKw": enel_power,
        },
        "crossSource": {
            "evseIdExactAfterLegacyPrefixNormalization": True,
            "punMaxPowerKw": pun_power,
            "enelMaxPowerKw": enel_power,
            "powerDeltaKw": round(power_delta, 6) if power_delta is not None else None,
            "powerMatchesWithin0_1Kw": power_delta is not None and power_delta <= 0.1,
        },
        "directOperatorTariff": {
            "sourceField": "price",
            "rawValueCents": raw_price,
            "currency": currency,
            "type": price_type,
            "eurPerKwh": operator_eur_kwh,
            "rankable": operator_eur_kwh is not None,
            "rankableReason": "enel_public_detail_eur_kwh" if operator_eur_kwh is not None else "unsupported_or_missing_price_semantics",
            "snapshotNature": "current_price_returned_by_enel_station_detail",
        },
        "directPaymentCandidate": {
            "sourceField": "directPaymenthPrice",
            "rawValueCents": finite_number(plug.get("directPaymenthPrice")),
            "currency": currency,
            "type": direct_type,
            "eurPerKwhCandidate": direct_eur_kwh,
            "rankable": False,
            "rankableReason": "directPaymenthPrice_consumer_semantics_not_independently_validated",
        },
        "penaltyCandidate": {
            "rawPenaltyPrice": finite_number(plug.get("penaltyPrice")),
            "rawDirectPaymentPenaltyPrice": finite_number(plug.get("directPaymenthPenaltyPrice")),
            "rankable": False,
            "rankableReason": "penalty_unit_and_trigger_rules_not_independently_validated",
        },
    }, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--limit-stations", type=int, default=None)
    args = parser.parse_args()

    if not PUN_INPUT.exists():
        raise SystemExit(f"missing PUN input: {PUN_INPUT}")
    with gzip.open(PUN_INPUT, "rt", encoding="utf-8") as fh:
        pun = json.load(fh)
    pun_evses = [e for e in (pun.get("evses") or []) if isinstance(e, dict) and e.get("partyId") == "ENX"]
    pun_index = {str(e.get("evseId")): e for e in pun_evses if e.get("evseId")}
    serial_to_pun: dict[str, list[str]] = defaultdict(list)
    malformed_pun_ids: list[str] = []
    for evse_id in sorted(pun_index):
        serial = extract_serial(evse_id)
        if serial:
            serial_to_pun[serial].append(evse_id)
        else:
            malformed_pun_ids.append(evse_id)
    serials = sorted(serial_to_pun)
    if args.limit_stations is not None:
        serials = serials[: max(0, args.limit_stations)]

    headers = extract_public_headers()
    details: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(get_detail, serial, headers): serial for serial in serials}
        for idx, future in enumerate(as_completed(futures), 1):
            try:
                details.append(future.result())
            except Exception as exc:
                details.append({"ok": False, "serial": futures[future], "error": f"{type(exc).__name__}: {exc}"})
            if idx % 500 == 0 or idx == len(futures):
                ok = sum(1 for x in details if x.get("ok") is True)
                print(f"ENEL detail progress: {idx}/{len(futures)} successful={ok} failed={len(details)-ok}")

    records_by_evse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched: list[dict[str, Any]] = []
    detail_failures: list[dict[str, Any]] = []
    price_counter: Counter[str] = Counter()
    direct_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    for detail in details:
        if detail.get("ok") is not True:
            detail_failures.append({k: detail.get(k) for k in ("serial", "httpStatus", "businessCode", "businessMessage", "error")})
            continue
        serial = str(detail.get("serial"))
        result = detail.get("result")
        if not isinstance(result, dict):
            continue
        evses = result.get("evses")
        if not isinstance(evses, list):
            continue
        for evse in evses:
            if not isinstance(evse, dict):
                continue
            plugs = evse.get("plugs")
            if not isinstance(plugs, list):
                continue
            for plug in plugs:
                if not isinstance(plug, dict):
                    continue
                record, miss = normalize_plug(serial, result, evse, plug, pun_index)
                if miss:
                    unmatched.append(miss)
                    continue
                assert record is not None
                records_by_evse[record["evseId"]].append(record)
                tariff = record["directOperatorTariff"]
                if tariff.get("rankable"):
                    price_counter[f"{tariff.get('eurPerKwh'):.3f}"] += 1
                direct = record["directPaymentCandidate"].get("eurPerKwhCandidate")
                if direct is not None:
                    direct_counter[f"{direct:.3f}"] += 1
                status_counter[str(record.get("enelPlugStatus") or "UNKNOWN")] += 1

    output_records: list[dict[str, Any]] = []
    for evse_id in sorted(records_by_evse):
        rows = records_by_evse[evse_id]
        # Preserve every returned plug. In current ENEL data most EVSEs have one,
        # but no lossy assumption is made here.
        first = rows[0]
        output_records.append({
            "evseId": evse_id,
            "stationSerialNumber": first.get("stationSerialNumber"),
            "operator": first.get("operator"),
            "partyId": first.get("partyId"),
            "coordinates": first.get("coordinates"),
            "punStatus": first.get("punStatus"),
            "punOperationalState": first.get("punOperationalState"),
            "enelStationStatus": first.get("enelStationStatus"),
            "enelEvseStatus": first.get("enelEvseStatus"),
            "crossSource": first.get("crossSource"),
            "plugs": [
                {
                    "connector": row.get("connector"),
                    "enelPlugStatus": row.get("enelPlugStatus"),
                    "directOperatorTariff": row.get("directOperatorTariff"),
                    "directPaymentCandidate": row.get("directPaymentCandidate"),
                    "penaltyCandidate": row.get("penaltyCandidate"),
                }
                for row in rows
            ],
        })

    rankable_evse_count = sum(
        1 for row in output_records
        if any((plug.get("directOperatorTariff") or {}).get("rankable") for plug in row.get("plugs", []))
    )
    power_match_count = sum(
        1 for row in output_records
        if (row.get("crossSource") or {}).get("powerMatchesWithin0_1Kw") is True
    )
    generated = now_iso()
    counts = {
        "punEnxEvseCount": len(pun_evses),
        "punEnxStationSerialCount": len(serial_to_pun),
        "requestedStationSerialCount": len(serials),
        "successfulStationDetailCount": sum(1 for x in details if x.get("ok") is True),
        "failedStationDetailCount": len(detail_failures),
        "matchedEnelEvseCount": len(output_records),
        "unmatchedEnelPlugCount": len(unmatched),
        "rankableOperatorTariffEvseCount": rankable_evse_count,
        "rankableCoveragePctOfRequestedPunEnx": round(100.0 * rankable_evse_count / max(1, sum(len(serial_to_pun[s]) for s in serials)), 2),
        "powerMatchWithin0_1KwEvseCount": power_match_count,
        "malformedPunEnxEvseIdCount": len(malformed_pun_ids),
    }
    payload = {
        "schemaVersion": 1,
        "dataset": "enel_direct_stations_italy_candidate",
        "generatedAt": generated,
        "country": "IT",
        "source": {
            "inventory": "GSE PUN",
            "tariff": "Enel public station-detail API used by the public web map",
            "detailEndpoint": "/api/emobility/v2/charging/station/{serialNumber}",
        },
        "security": {
            "accountCredentialsUsed": False,
            "anonymousPublicWebSessionUsed": True,
            "authorizationMaterialPersisted": False,
            "cookiesPersisted": False,
            "rawResponseBodiesPersisted": False,
        },
        "tariffPolicy": {
            "rankableField": "price",
            "rankableOnlyWhen": "currency=EUR and typePrice=KWH and numeric price",
            "priceStorageUnitDetected": "integer euro-cents; normalized by /100",
            "directPaymenthPriceRankable": False,
            "penaltiesRankable": False,
            "important": "operator price is an observed current station-detail snapshot; time-slot schedule overlay must be validated separately before future-time simulation",
        },
        "counts": counts,
        "observedOperatorPriceEurPerKwh": dict(sorted(price_counter.items())),
        "observedDirectPaymentCandidateEurPerKwh": dict(sorted(direct_counter.items())),
        "observedPlugStatusCounts": dict(sorted(status_counter.items())),
        "quality": {
            "legacyEvoToEnxPrefixOnlyNormalization": True,
            "detailFailureSample": detail_failures[:100],
            "unmatchedSample": unmatched[:100],
            "malformedPunEvseIdSample": malformed_pun_ids[:100],
        },
        "evses": output_records,
    }
    report = {
        "generatedAt": generated,
        "counts": counts,
        "observedOperatorPriceEurPerKwh": payload["observedOperatorPriceEurPerKwh"],
        "observedDirectPaymentCandidateEurPerKwh": payload["observedDirectPaymentCandidateEurPerKwh"],
        "observedPlugStatusCounts": payload["observedPlugStatusCounts"],
        "detailFailureSample": detail_failures[:30],
        "unmatchedSample": unmatched[:30],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(gzip.compress((json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"), compresslevel=9))
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)[:30000])


if __name__ == "__main__":
    main()
