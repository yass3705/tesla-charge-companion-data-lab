#!/usr/bin/env python3
"""Build an Italy-wide Ewiva tariff layer using PUN + Enel public station detail.

TCC modelling:
- PUN party EWI is the authoritative inventory/status source.
- Enel's public station-detail API is queried by serial extracted from the PUN EVSE ID.
- Exact station-detail ``price`` is retained as the direct Enel On Your Way price snapshot.
- Current Enel Basic/Super/Explorer schedules are attached for future-time simulation.
- If station detail is unavailable, the official Enel tariff policy can be used as a
  partner fallback only when the PUN connector technology class is known.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import enel_italy_national_tariffs as enel

PUN_INPUT = Path("data/national/pun_italy_national.json.gz")
OUTPUT = Path("data/national/enel_ewiva_partner_italy.json.gz")
REPORT = Path("data/reports/enel_ewiva_partner_italy_report.json")
EVSE_RE = re.compile(r"^IT\*EWI\*E(.+)\*(\d+)$")

BASIC = {
    "AC": {"day": 0.67, "night": 0.58},
    "DC": {"day": 0.75, "night": 0.64},
    "HPC": {"day": 0.82, "night": 0.82},
}
PLANS = {
    "pay_per_use_basic": {"fixedFeeEur": 0.0, "period": None, "discountEurPerKwh": 0.0},
    "pay_per_use_premium": {"fixedFeeEur": 25.0, "period": "year", "discountEurPerKwh": 0.0},
    "plug_and_go_super": {"fixedFeeEur": 4.0, "period": "month", "discountEurPerKwh": 0.05},
    "plug_and_go_explorer": {"fixedFeeEur": 12.0, "period": "month", "discountEurPerKwh": 0.10},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def extract_serial(evse_id: str) -> str | None:
    m = EVSE_RE.match(evse_id)
    return m.group(1) if m else None


def cents_to_eur(value: Any) -> float | None:
    return enel.cents_to_eur(value)


def class_from_pun(evse: dict[str, Any]) -> str | None:
    connectors = [c for c in (evse.get("connectors") or []) if isinstance(c, dict)]
    power_types = {str(c.get("powerType") or "").upper() for c in connectors}
    if any(x.startswith("AC") for x in power_types):
        return "AC"
    powers = [enel.finite_number(c.get("maxPowerKw")) for c in connectors]
    powers = [p for p in powers if p is not None]
    max_power = max(powers) if powers else enel.finite_number(evse.get("maxPowerKw"))
    if max_power is not None and max_power > 99:
        return "HPC"
    if any(x.startswith("DC") for x in power_types) or max_power is not None:
        return "DC"
    return None


def plan_schedule(tariff_class: str | None) -> dict[str, Any] | None:
    if tariff_class not in BASIC:
        return None
    result: dict[str, Any] = {}
    for plan_id, plan in PLANS.items():
        discount = float(plan["discountEurPerKwh"])
        result[plan_id] = {
            "fixedFeeEur": plan["fixedFeeEur"],
            "fixedFeePeriod": plan["period"],
            "dayEurPerKwh": round(BASIC[tariff_class]["day"] - discount, 2),
            "nightEurPerKwh": round(BASIC[tariff_class]["night"] - discount, 2),
        }
    return result


def normalize_detail(
    serial: str,
    result: dict[str, Any],
    evse: dict[str, Any],
    plug: dict[str, Any],
    pun_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw_id = evse.get("evseId")
    if not isinstance(raw_id, str) or not raw_id.startswith("IT*EWI*") or raw_id not in pun_index:
        return None, {
            "serial": serial,
            "rawEnelEvseId": raw_id if isinstance(raw_id, str) else None,
            "reason": "not_found_in_pun_ewi",
        }
    pun = pun_index[raw_id]
    currency = str(plug.get("currency") or "").upper() or None
    price_type = str(plug.get("typePrice") or "").upper() or None
    price = cents_to_eur(plug.get("price")) if currency == "EUR" and price_type == "KWH" else None
    enel_power = enel.finite_number(plug.get("maxPower"))
    pun_power = enel.finite_number(pun.get("maxPowerKw"))
    delta = abs(enel_power - pun_power) if enel_power is not None and pun_power is not None else None
    tariff_class = class_from_pun(pun)
    return {
        "evseId": raw_id,
        "stationSerialNumber": serial,
        "stationName": result.get("csName"),
        "operator": pun.get("operator"),
        "partyId": "EWI",
        "coordinates": pun.get("coordinates"),
        "punStatus": pun.get("sourceStatus"),
        "punOperationalState": pun.get("operationalState"),
        "enelStationStatus": result.get("status"),
        "enelEvseStatus": evse.get("status"),
        "enelPlugStatus": plug.get("status"),
        "tariffClass": tariff_class,
        "connector": {
            "plugId": plug.get("plugId"),
            "typology": plug.get("typology"),
            "maxPowerKw": enel_power,
        },
        "crossSource": {
            "evseIdExact": True,
            "punMaxPowerKw": pun_power,
            "enelMaxPowerKw": enel_power,
            "powerDeltaKw": round(delta, 6) if delta is not None else None,
            "powerMatchesWithin0_1Kw": delta is not None and delta <= 0.1,
        },
        "directOperatorTariff": {
            "source": "enel_public_station_detail",
            "rawValueCents": enel.finite_number(plug.get("price")),
            "currency": currency,
            "type": price_type,
            "eurPerKwh": price,
            "rankable": price is not None,
        },
        "partnerTariffSchedule": plan_schedule(tariff_class),
        "penaltyCandidate": {
            "rawPenaltyPrice": enel.finite_number(plug.get("penaltyPrice")),
            "rankable": False,
            "reason": "unit_and_trigger_not_yet_independently_validated",
        },
    }, None


def collapse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0]
    plugs = []
    for row in rows:
        plugs.append({
            "connector": row.get("connector"),
            "enelPlugStatus": row.get("enelPlugStatus"),
            "directOperatorTariff": row.get("directOperatorTariff"),
            "penaltyCandidate": row.get("penaltyCandidate"),
        })
    return {
        "evseId": first.get("evseId"),
        "stationSerialNumber": first.get("stationSerialNumber"),
        "stationName": first.get("stationName"),
        "operator": first.get("operator"),
        "partyId": "EWI",
        "coordinates": first.get("coordinates"),
        "punStatus": first.get("punStatus"),
        "punOperationalState": first.get("punOperationalState"),
        "enelStationStatus": first.get("enelStationStatus"),
        "enelEvseStatus": first.get("enelEvseStatus"),
        "tariffClass": first.get("tariffClass"),
        "partnerTariffSchedule": first.get("partnerTariffSchedule"),
        "crossSource": first.get("crossSource"),
        "plugs": plugs,
        "stationDetailCoverage": "direct_station_detail",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit-stations", type=int, default=None)
    args = parser.parse_args()

    with gzip.open(PUN_INPUT, "rt", encoding="utf-8") as fh:
        pun = json.load(fh)
    pun_evses = [e for e in (pun.get("evses") or []) if isinstance(e, dict) and e.get("partyId") == "EWI"]
    pun_index = {str(e.get("evseId")): e for e in pun_evses if e.get("evseId")}
    serial_to_ids: dict[str, list[str]] = defaultdict(list)
    malformed = []
    for evse_id in sorted(pun_index):
        serial = extract_serial(evse_id)
        if serial:
            serial_to_ids[serial].append(evse_id)
        else:
            malformed.append(evse_id)
    serials = sorted(serial_to_ids)
    if args.limit_stations is not None:
        serials = serials[: max(0, args.limit_stations)]

    headers = enel.extract_public_headers()
    details: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(enel.get_detail, serial, headers): serial for serial in serials}
        for idx, future in enumerate(as_completed(futures), 1):
            try:
                details.append(future.result())
            except Exception as exc:
                details.append({"ok": False, "serial": futures[future], "error": f"{type(exc).__name__}: {exc}"})
            if idx % 250 == 0 or idx == len(futures):
                ok = sum(1 for x in details if x.get("ok") is True)
                print(f"EWIVA detail progress: {idx}/{len(futures)} successful={ok} failed={len(details)-ok}")

    by_evse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failures = []
    unmatched = []
    price_counter: Counter[str] = Counter()
    for detail in details:
        if detail.get("ok") is not True:
            failures.append({k: detail.get(k) for k in ("serial", "httpStatus", "businessCode", "businessMessage", "error")})
            continue
        serial = str(detail.get("serial"))
        result = detail.get("result")
        if not isinstance(result, dict):
            continue
        for evse in result.get("evses") or []:
            if not isinstance(evse, dict):
                continue
            for plug in evse.get("plugs") or []:
                if not isinstance(plug, dict):
                    continue
                row, miss = normalize_detail(serial, result, evse, plug, pun_index)
                if miss:
                    unmatched.append(miss)
                elif row:
                    by_evse[str(row["evseId"])].append(row)
                    p = (row.get("directOperatorTariff") or {}).get("eurPerKwh")
                    if p is not None:
                        price_counter[f"{float(p):.3f}"] += 1

    direct = {eid: collapse(rows) for eid, rows in by_evse.items() if rows}
    final = []
    for evse_id in sorted(pun_index):
        if evse_id in direct:
            final.append(direct[evse_id])
            continue
        p = pun_index[evse_id]
        tariff_class = class_from_pun(p)
        final.append({
            "evseId": evse_id,
            "stationSerialNumber": extract_serial(evse_id),
            "stationName": None,
            "operator": p.get("operator"),
            "partyId": "EWI",
            "coordinates": p.get("coordinates"),
            "punStatus": p.get("sourceStatus"),
            "punOperationalState": p.get("operationalState"),
            "enelStationStatus": None,
            "enelEvseStatus": None,
            "tariffClass": tariff_class,
            "partnerTariffSchedule": plan_schedule(tariff_class),
            "punConnectors": p.get("connectors") or [],
            "plugs": [],
            "stationDetailCoverage": "official_partner_policy_fallback",
        })

    direct_rankable = sum(1 for e in final if any((p.get("directOperatorTariff") or {}).get("rankable") for p in e.get("plugs") or []))
    schedule_rankable = sum(1 for e in final if e.get("partnerTariffSchedule"))
    detail_evse = len(direct)
    power_match = sum(1 for e in direct.values() if (e.get("crossSource") or {}).get("powerMatchesWithin0_1Kw") is True)
    status_missing = Counter(str(pun_index[eid].get("sourceStatus") or "UNKNOWN") for eid in sorted(set(pun_index) - set(direct)))
    class_counts = Counter(class_from_pun(e) or "UNKNOWN" for e in pun_evses)

    counts = {
        "punEwiEvseCount": len(pun_evses),
        "punEwiStationSerialCount": len(serial_to_ids),
        "requestedStationSerialCount": len(serials),
        "successfulStationDetailCount": sum(1 for d in details if d.get("ok") is True),
        "failedStationDetailCount": len(failures),
        "matchedEwivaEvseCount": detail_evse,
        "directRankableTariffEvseCount": direct_rankable,
        "directCoveragePct": round(100.0 * direct_rankable / max(1, len(pun_evses)), 2),
        "partnerScheduleRankableEvseCount": schedule_rankable,
        "partnerScheduleCoveragePct": round(100.0 * schedule_rankable / max(1, len(pun_evses)), 2),
        "powerMatchWithin0_1KwEvseCount": power_match,
        "unmatchedEnelPlugCount": len(unmatched),
        "malformedPunEwiEvseIdCount": len(malformed),
    }
    payload = {
        "schemaVersion": 1,
        "dataset": "enel_ewiva_partner_italy",
        "generatedAt": now_iso(),
        "country": "IT",
        "operatorPartyId": "EWI",
        "commercialProvider": "Enel On Your Way",
        "scope": "Ewiva stations covered by current Enel public charging tariffs",
        "tariffPolicy": {
            "timezone": "Europe/Rome",
            "priceSelectionBasis": "session_start_local_time",
            "dayWindow": {"start": "07:00", "endExclusive": "21:00"},
            "nightWindow": {"start": "21:00", "endExclusive": "07:00"},
            "basicEurPerKwh": BASIC,
            "plans": PLANS,
            "stationDetailPrecedence": "direct_price_then_official_partner_schedule",
        },
        "counts": counts,
        "observedDirectPriceEurPerKwh": dict(sorted(price_counter.items())),
        "punTariffClassCounts": dict(sorted(class_counts.items())),
        "missingDirectDetailPunStatusCounts": dict(sorted(status_missing.items())),
        "failureSample": failures[:100],
        "unmatchedSample": unmatched[:100],
        "security": {"accountCredentialsUsed": False, "authorizationMaterialPersisted": False},
        "evses": final,
    }
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(gzip.compress(raw, compresslevel=9))
    report = {k: payload[k] for k in ("generatedAt", "counts", "observedDirectPriceEurPerKwh", "punTariffClassCounts", "missingDirectDetailPunStatusCounts", "failureSample", "unmatchedSample")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)[:30000])


if __name__ == "__main__":
    main()
