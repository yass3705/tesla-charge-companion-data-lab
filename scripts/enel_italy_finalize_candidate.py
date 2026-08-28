#!/usr/bin/env python3
"""Finalize the Italy-wide Enel X tariff candidate for TCC research.

This second pass deliberately reuses the national PUN inventory and the first-pass
Enel candidate. It retries only station serials with no matched Enel detail, then
adds a future-time tariff policy built from Enel's current public tariff pages.

Important modelling rules:
- PUN remains the inventory / status reference.
- Enel station detail remains the highest-priority station-specific price snapshot.
- Future-time simulation uses the official Enel tariff schedule, selected by the
  local Europe/Rome *session start time* (Enel states that the start time fixes
  the tariff for the session).
- The schedule is cross-checked against station-detail prices observed in the
  same run. A mismatch is reported; it is never silently overwritten.
- Missing station-detail responses may receive an official-policy fallback only
  when PUN identifies an ENX EVSE and its technology class can be determined.
- Flat monthly plans are metadata only: they are not rankable without the user's
  remaining monthly quota state.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import enel_italy_national_tariffs as base

PUN_INPUT = Path("data/national/pun_italy_national.json.gz")
ENEL_INPUT = Path("data/national/enel_direct_stations_italy.json.gz")
OUTPUT = Path("data/national/enel_direct_stations_italy_final_candidate.json.gz")
REPORT = Path("data/reports/enel_italy_finalization_report.json")
ROME = ZoneInfo("Europe/Rome")

# Current official public tariff evidence checked 2026-08-29.
# Current tariff page exposes the night prices and confirms day/night pricing.
# Enel's current plan overview gives the Basic day prices. Station-detail API
# values observed during the night matched 0.58 / 0.64 / 0.82 exactly.
TARIFF_POLICY = {
    "policyId": "enel-it-ppu-2026-08-29",
    "country": "IT",
    "timezone": "Europe/Rome",
    "priceSelectionBasis": "session_start_local_time",
    "dayWindow": {"start": "07:00", "endExclusive": "21:00"},
    "nightWindow": {"start": "21:00", "endExclusive": "07:00"},
    "basicEurPerKwh": {
        "AC": {"day": 0.67, "night": 0.58},
        "DC": {"day": 0.75, "night": 0.64},
        "HPC": {"day": 0.83, "night": 0.82},
    },
    "plans": {
        "pay_per_use_basic": {
            "label": "Pay Per Use Basic",
            "fixedFeeEur": 0.0,
            "fixedFeePeriod": None,
            "discountFromBasicEurPerKwh": 0.0,
            "rankable": True,
        },
        "pay_per_use_premium": {
            "label": "Pay Per Use Premium",
            "fixedFeeEur": 25.0,
            "fixedFeePeriod": "year",
            "discountFromBasicEurPerKwh": 0.0,
            "unlimitedReservations": True,
            "rankable": True,
        },
        "plug_and_go_super": {
            "label": "Plug&Go Super",
            "fixedFeeEur": 4.0,
            "fixedFeePeriod": "month",
            "discountFromBasicEurPerKwh": 0.05,
            "unlimitedReservations": True,
            "rankable": True,
        },
        "plug_and_go_explorer": {
            "label": "Plug&Go Explorer",
            "fixedFeeEur": 12.0,
            "fixedFeePeriod": "month",
            "discountFromBasicEurPerKwh": 0.10,
            "unlimitedReservations": True,
            "rankable": True,
        },
        "flat_urban": {
            "label": "Flat Urban",
            "fixedFeeEur": 49.0,
            "fixedFeePeriod": "month",
            "includedKwh": 72.0,
            "includedClasses": ["AC", "DC"],
            "overageAndHpc": "pay_per_use_basic",
            "validThrough": "2026-10-31",
            "rankable": False,
            "rankableReason": "remaining_monthly_quota_required",
        },
        "flat_traveler": {
            "label": "Flat Traveler",
            "fixedFeeEur": 79.0,
            "fixedFeePeriod": "month",
            "includedKwh": 120.0,
            "includedClasses": ["AC", "DC"],
            "overageAndHpc": "pay_per_use_basic",
            "validThrough": "2026-10-31",
            "rankable": False,
            "rankableReason": "remaining_monthly_quota_required",
        },
        "flat_explorer": {
            "label": "Flat Explorer",
            "fixedFeeEur": 129.0,
            "fixedFeePeriod": "month",
            "includedKwh": 195.0,
            "includedClasses": ["AC", "DC"],
            "overageAndHpc": "pay_per_use_basic",
            "validThrough": "2026-10-31",
            "rankable": False,
            "rankableReason": "remaining_monthly_quota_required",
        },
    },
    "sources": [
        {
            "kind": "current_tariff_page",
            "url": "https://www.enel.it/it-it/mobilita-elettrica/tariffe-abbonamenti",
            "evidence": "current night prices, subscription fees/discounts, flat plans, session-start pricing rule",
        },
        {
            "kind": "current_plan_overview",
            "url": "https://www.enel.it/it-it/blog/storie/tariffe-ricarica-elettrica",
            "evidence": "Basic day prices AC 0.67, DC 0.75, HPC 0.83",
        },
        {
            "kind": "secondary_pdf",
            "url": "https://www.enel.it/content/dam/asset/documenti/enel-x-way/tariffe-abbonamenti/enel-x-piani-di-ricarica.pdf",
            "evidence": "secondary control only; page/API take precedence when newer values differ",
        },
    ],
}


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def dump_gzip_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9))


def parse_generated_at(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def tariff_slot(dt_utc: datetime) -> str:
    local = dt_utc.astimezone(ROME)
    return "night" if local.hour >= 21 or local.hour < 7 else "day"


def plan_price(tariff_class: str, slot: str, plan_id: str) -> float | None:
    basic = (TARIFF_POLICY["basicEurPerKwh"].get(tariff_class) or {}).get(slot)
    if basic is None:
        return None
    plan = TARIFF_POLICY["plans"].get(plan_id) or {}
    discount = float(plan.get("discountFromBasicEurPerKwh") or 0.0)
    return round(max(0.0, float(basic) - discount), 6)


def class_from_direct_row(row: dict[str, Any]) -> str | None:
    typologies = set()
    powers = []
    for plug in row.get("plugs") or []:
        connector = plug.get("connector") if isinstance(plug, dict) else None
        if not isinstance(connector, dict):
            continue
        typ = str(connector.get("typology") or "").upper()
        if typ:
            typologies.add(typ)
        power = base.finite_number(connector.get("maxPowerKw"))
        if power is not None:
            powers.append(power)
    if any("TYPE_2" in t or "TYPE2" in t or "TYPE_3" in t for t in typologies):
        return "AC"
    max_power = max(powers) if powers else None
    if max_power is not None and max_power > 99:
        return "HPC"
    if typologies or max_power is not None:
        return "DC"
    return None


def class_from_pun(evse: dict[str, Any]) -> str | None:
    connectors = [c for c in (evse.get("connectors") or []) if isinstance(c, dict)]
    power_types = {str(c.get("powerType") or "").upper() for c in connectors}
    if any(t.startswith("AC") for t in power_types):
        return "AC"
    powers = [base.finite_number(c.get("maxPowerKw")) for c in connectors]
    powers = [p for p in powers if p is not None]
    max_power = max(powers) if powers else base.finite_number(evse.get("maxPowerKw"))
    if max_power is not None and max_power > 99:
        return "HPC"
    if any(t.startswith("DC") for t in power_types) or max_power is not None:
        return "DC"
    return None


def collapse_retry_rows(records: list[dict[str, Any]]) -> dict[str, Any]:
    first = records[0]
    return {
        "evseId": first.get("evseId"),
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
                "connector": rec.get("connector"),
                "enelPlugStatus": rec.get("enelPlugStatus"),
                "directOperatorTariff": rec.get("directOperatorTariff"),
                "directPaymentCandidate": rec.get("directPaymentCandidate"),
                "penaltyCandidate": rec.get("penaltyCandidate"),
            }
            for rec in records
        ],
    }


def retry_missing_serials(
    serials: list[str],
    pun_index: dict[str, dict[str, Any]],
    workers: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not serials:
        return {}, [], []
    headers = base.extract_public_headers()
    details: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(base.get_detail, serial, headers): serial for serial in serials}
        for idx, future in enumerate(as_completed(futures), 1):
            try:
                details.append(future.result())
            except Exception as exc:
                details.append({"ok": False, "serial": futures[future], "error": f"{type(exc).__name__}: {exc}"})
            if idx % 100 == 0 or idx == len(futures):
                ok = sum(1 for d in details if d.get("ok") is True)
                print(f"ENEL retry progress: {idx}/{len(futures)} successful={ok} failed={len(details)-ok}")

    by_evse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failures: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
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
                record, miss = base.normalize_plug(serial, result, evse, plug, pun_index)
                if miss:
                    unmatched.append(miss)
                elif record:
                    by_evse[str(record["evseId"])].append(record)
    collapsed = {evse_id: collapse_retry_rows(rows) for evse_id, rows in by_evse.items() if rows}
    return collapsed, failures, unmatched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-workers", type=int, default=4)
    parser.add_argument("--skip-retry", action="store_true")
    args = parser.parse_args()

    if not PUN_INPUT.exists() or not ENEL_INPUT.exists():
        raise SystemExit("PUN and first-pass Enel candidate are required")
    pun = load_gzip_json(PUN_INPUT)
    first = load_gzip_json(ENEL_INPUT)

    pun_evses = [e for e in (pun.get("evses") or []) if isinstance(e, dict) and e.get("partyId") == "ENX"]
    pun_index = {str(e.get("evseId")): e for e in pun_evses if e.get("evseId")}
    serial_to_pun: dict[str, list[str]] = defaultdict(list)
    for evse_id in sorted(pun_index):
        serial = base.extract_serial(evse_id)
        if serial:
            serial_to_pun[serial].append(evse_id)

    direct_by_evse = {str(e.get("evseId")): e for e in (first.get("evses") or []) if isinstance(e, dict) and e.get("evseId")}
    successful_serials = {str(e.get("stationSerialNumber")) for e in direct_by_evse.values() if e.get("stationSerialNumber")}
    missing_serials_before = sorted(set(serial_to_pun) - successful_serials)

    before_missing_evses = [pun_index[eid] for s in missing_serials_before for eid in serial_to_pun.get(s, []) if eid in pun_index]
    before_status = Counter(str(e.get("sourceStatus") or "UNKNOWN") for e in before_missing_evses)
    before_operational = Counter(str(e.get("operationalState") or "unknown") for e in before_missing_evses)
    before_class = Counter(class_from_pun(e) or "UNKNOWN" for e in before_missing_evses)

    retry_rows: dict[str, dict[str, Any]] = {}
    retry_failures: list[dict[str, Any]] = []
    retry_unmatched: list[dict[str, Any]] = []
    if missing_serials_before and not args.skip_retry:
        retry_rows, retry_failures, retry_unmatched = retry_missing_serials(missing_serials_before, pun_index, args.retry_workers)
        direct_by_evse.update(retry_rows)

    successful_serials_after = {str(e.get("stationSerialNumber")) for e in direct_by_evse.values() if e.get("stationSerialNumber")}
    missing_serials_after = sorted(set(serial_to_pun) - successful_serials_after)
    missing_evse_ids_after = sorted(set(pun_index) - set(direct_by_evse))
    missing_evses_after = [pun_index[eid] for eid in missing_evse_ids_after]

    generated_at = parse_generated_at(first.get("generatedAt"))
    observed_slot = tariff_slot(generated_at)
    observed_matches = 0
    observed_mismatches = 0
    observed_unknown_class = 0

    final_evses: list[dict[str, Any]] = []
    for evse_id in sorted(pun_index):
        pun_evse = pun_index[evse_id]
        direct = direct_by_evse.get(evse_id)
        tariff_class = class_from_direct_row(direct) if direct else class_from_pun(pun_evse)
        schedule_rankable = tariff_class in {"AC", "DC", "HPC"}

        if direct:
            row = dict(direct)
            row["stationDetailCoverage"] = "direct_station_detail"
            # Cross-check the observed Basic price against the expected tariff for
            # the local slot in which the national extraction ran.
            expected = plan_price(tariff_class, observed_slot, "pay_per_use_basic") if tariff_class else None
            for plug in row.get("plugs") or []:
                tariff = (plug.get("directOperatorTariff") or {}) if isinstance(plug, dict) else {}
                observed = base.finite_number(tariff.get("eurPerKwh"))
                if observed is None or expected is None:
                    continue
                if abs(observed - expected) <= 0.000001:
                    observed_matches += 1
                else:
                    observed_mismatches += 1
            if not tariff_class:
                observed_unknown_class += 1
        else:
            row = {
                "evseId": evse_id,
                "stationSerialNumber": base.extract_serial(evse_id),
                "operator": pun_evse.get("operator"),
                "partyId": pun_evse.get("partyId"),
                "coordinates": pun_evse.get("coordinates"),
                "punStatus": pun_evse.get("sourceStatus"),
                "punOperationalState": pun_evse.get("operationalState"),
                "enelStationStatus": None,
                "enelEvseStatus": None,
                "crossSource": None,
                "punConnectors": pun_evse.get("connectors") or [],
                "plugs": [],
                "stationDetailCoverage": "official_policy_fallback",
            }
        row["tariffClass"] = tariff_class
        row["futureTariffPolicyRef"] = TARIFF_POLICY["policyId"] if schedule_rankable else None
        row["futureTariffRankable"] = schedule_rankable
        row["futureTariffRankableReason"] = "official_enel_policy_by_class_and_session_start" if schedule_rankable else "technology_class_not_determined"
        final_evses.append(row)

    after_status = Counter(str(e.get("sourceStatus") or "UNKNOWN") for e in missing_evses_after)
    after_operational = Counter(str(e.get("operationalState") or "unknown") for e in missing_evses_after)
    after_class = Counter(class_from_pun(e) or "UNKNOWN" for e in missing_evses_after)
    schedule_coverage = sum(1 for e in final_evses if e.get("futureTariffRankable") is True)
    direct_rankable = sum(
        1 for e in final_evses
        if e.get("stationDetailCoverage") == "direct_station_detail"
        and any((p.get("directOperatorTariff") or {}).get("rankable") for p in e.get("plugs") or [])
    )

    counts = {
        "punEnxEvseCount": len(pun_evses),
        "punEnxStationSerialCount": len(serial_to_pun),
        "directEvseBeforeRetryCount": len(first.get("evses") or []),
        "missingStationSerialBeforeRetryCount": len(missing_serials_before),
        "missingEvseBeforeRetryCount": len(set(pun_index) - set(str(e.get("evseId")) for e in (first.get("evses") or []) if isinstance(e, dict))),
        "retryRecoveredEvseCount": len(retry_rows),
        "retryFailureStationCount": len(retry_failures),
        "remainingStationSerialWithoutDetailCount": len(missing_serials_after),
        "remainingEvseWithoutDetailCount": len(missing_evse_ids_after),
        "directRankableTariffEvseCount": direct_rankable,
        "officialFutureScheduleRankableEvseCount": schedule_coverage,
        "officialFutureScheduleCoveragePct": round(100.0 * schedule_coverage / max(1, len(pun_evses)), 2),
        "observedSnapshotPriceMatchCount": observed_matches,
        "observedSnapshotPriceMismatchCount": observed_mismatches,
        "observedDirectRowsUnknownTariffClassCount": observed_unknown_class,
    }

    payload = {
        "schemaVersion": 2,
        "dataset": "enel_direct_stations_italy_final_candidate",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "country": "IT",
        "sourceCandidateGeneratedAt": first.get("generatedAt"),
        "operatorTariffPolicy": TARIFF_POLICY,
        "tariffValidation": {
            "stationDetailObservedSlot": observed_slot,
            "stationDetailObservedAtUtc": first.get("generatedAt"),
            "stationDetailObservedAtRome": generated_at.astimezone(ROME).isoformat(),
            "mismatchPolicy": "do_not_overwrite_station_detail; report discrepancy",
        },
        "counts": counts,
        "gapDiagnostics": {
            "beforeRetry": {
                "sourceStatusCounts": dict(sorted(before_status.items())),
                "operationalStateCounts": dict(sorted(before_operational.items())),
                "tariffClassCounts": dict(sorted(before_class.items())),
            },
            "afterRetry": {
                "sourceStatusCounts": dict(sorted(after_status.items())),
                "operationalStateCounts": dict(sorted(after_operational.items())),
                "tariffClassCounts": dict(sorted(after_class.items())),
            },
            "retryFailureSample": retry_failures[:100],
            "retryUnmatchedSample": retry_unmatched[:100],
            "remainingMissingSerialSample": missing_serials_after[:100],
        },
        "security": first.get("security"),
        "evses": final_evses,
    }

    report = {
        "generatedAt": payload["generatedAt"],
        "counts": counts,
        "tariffValidation": payload["tariffValidation"],
        "gapDiagnostics": payload["gapDiagnostics"],
        "plans": TARIFF_POLICY["plans"],
        "basicEurPerKwh": TARIFF_POLICY["basicEurPerKwh"],
    }
    dump_gzip_json(OUTPUT, payload)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)[:30000])


if __name__ == "__main__":
    main()
