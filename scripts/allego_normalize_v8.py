#!/usr/bin/env python3
"""Normalize Allego DXP output into an exact TCC v8 tariff model.

The upstream extractor intentionally stays generic and records every rate/fee token
returned by Allego DXP. This post-processor resolves only cases for which the
commercial semantics are independently known and machine-modelable:

* Burger King / Allego: EUR 0.45/kWh standard direct tariff; EUR 0.30/kWh is a
  Kingdom loyalty Happy Hours benefit (14:30-18:30 every day), never the default.
* Allego HPC idle fee: exact DXP rate, only after charging has stopped and never
  before minute 45 of the charging session.
* Allego regular overstay fee: exact DXP rate after 5 h from session start,
  applied 07:00-23:00 and until minute 960 (16 h from session start).

Unknown/ambiguous semantics still fail closed. Country defaults remain diagnostic
only and roaming/MSP prices are never promoted to direct CPO prices.
"""
from __future__ import annotations

import gzip
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DATA = Path("data/national/allego_direct_stations_france.json.gz")
REPORT = Path("data/reports/allego_station_tariffs_report.json")

ALLEG0_PRICING_URL = "https://www.allego.eu/fr/tarifs/"
ALLEG0_OVERSTAY_URL = "https://www.allego.eu/fr/overstay-fee/"
BK_PRESS_URL = "https://www.burgerking.fr/page/communiques-presse"


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def normalized_fee_rates_per_minute(fees: list[dict[str, Any]] | None) -> list[float]:
    rates: list[float] = []
    for fee in fees or []:
        value = num(fee.get("value"))
        unit = norm(fee.get("unit"))
        if value is None:
            continue
        if unit in {"minute", "min"}:
            rates.append(value)
        elif unit in {"heure", "hour"}:
            rates.append(value / 60.0)
    return sorted({round(rate, 9) for rate in rates if 0 <= rate <= 10})


def is_burger_king(row: dict[str, Any]) -> bool:
    haystack = " ".join([
        str(row.get("stationName") or ""),
        str(row.get("address") or ""),
        str((row.get("dxpAddress") or {}).get("street") or ""),
    ])
    return "burger king" in norm(haystack)


def kingdom_offer() -> dict[str, Any]:
    return {
        "id": "burger-king-kingdom-happy-hours",
        "selectionId": "burger-king-kingdom",
        "provider": "Burger King Kingdom",
        "offerType": "loyalty_direct",
        "requiresSelection": True,
        "directOperatorOnly": True,
        "pricePerKwhEur": 0.30,
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": "14:30",
        "end": "18:30",
        "activation": "Link the Burger King Kingdom account in the Allego app",
        "source": BK_PRESS_URL,
    }


def resolve_energy_rate(row: dict[str, Any]) -> tuple[float | None, list[dict[str, Any]], str | None]:
    candidates = sorted({round(float(v), 6) for v in row.get("allDirectRateCandidatesEurPerKwh") or []})
    if len(candidates) == 1:
        return candidates[0], [], None
    if is_burger_king(row) and candidates == [0.30, 0.45]:
        return 0.45, [kingdom_offer()], "burger_king_kingdom_split"
    return None, [], None


def resolve_fee_policy(row: dict[str, Any], power_kw: float | None) -> tuple[dict[str, Any] | None, str | None]:
    fee_rates = normalized_fee_rates_per_minute(row.get("feeCandidates"))
    if not fee_rates:
        return None, None
    if len(fee_rates) != 1:
        return None, "unparsed_time_or_blocking_fee"
    rate = fee_rates[0]
    power = power_kw or 0.0

    # Allego France HPC idle fee. The official policy states that no fee is due
    # while charging and that it can start only once the session is 45 min old.
    if power > 22.5 and abs(rate - 0.248) <= 0.002:
        return {
            "type": "idle_after_charging",
            "ratePerMinuteEur": rate,
            "notBeforeSessionMinute": 45,
            "onlyAfterChargingStops": True,
            "source": ALLEG0_OVERSTAY_URL,
        }, None

    # Regular charging overstay fee. DXP may expose 2.98 EUR/hour or 0.05
    # EUR/min; retain the exact DXP-derived per-minute value.
    if power <= 22.5 and 0.045 <= rate <= 0.055:
        return {
            "type": "connection_overstay",
            "ratePerMinuteEur": rate,
            "startAfterSessionMinutes": 300,
            "endAfterSessionMinutes": 960,
            "activeTimeWindows": [{"start": "07:00", "end": "23:00"}],
            "source": ALLEG0_OVERSTAY_URL,
        }, None

    return None, "unparsed_time_or_blocking_fee"


def normalize_evse(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    dxp_power = num(out.get("maxPowerKw"))
    published_power = num(out.get("powerKwPublished")) or num(out.get("powerKw"))
    power = dxp_power if dxp_power and dxp_power > 0 else published_power
    if power and power > 0:
        out["powerKw"] = power
        out["kind"] = "DC" if power > 22.5 else "AC"
        out["powerSource"] = "allego-dxp" if dxp_power and dxp_power > 0 else "allego-data-gouv"

    direct, conditional_offers, energy_resolution = resolve_energy_rate(out)
    fee_policy, fee_error = resolve_fee_policy(out, power)
    own = out.get("isOwnNetwork")

    if own is False:
        blocking = "not_allego_own_network"
    elif direct is None:
        blocking = "ambiguous_or_missing_direct_kwh_rate"
    elif fee_error:
        blocking = fee_error
    else:
        blocking = None

    rankable = blocking is None
    out.update({
        "directEurPerKwh": direct if rankable else None,
        "parsedEnergyRateEurPerKwh": direct,
        "energyResolution": energy_resolution or ("single_direct_dxp_rate" if direct is not None else None),
        "conditionalOffers": conditional_offers,
        "feePolicy": fee_policy,
        "feeModelExact": fee_error is None,
        "rankableDirect": rankable,
        "blockingReason": blocking,
    })
    return out


def rebuild_stations(stations: list[dict[str, Any]], evses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("evseId")): row for row in evses}
    rebuilt: list[dict[str, Any]] = []
    for station in stations:
        out = dict(station)
        rows = [by_id.get(str(row.get("evseId")), row) for row in station.get("evses") or []]
        rows = [row for row in rows if row]
        rankable_count = sum(1 for row in rows if row.get("rankableDirect"))
        out["evses"] = rows
        out["rankableEvseCount"] = rankable_count
        out["evseCount"] = len(rows)
        out["rankableDirect"] = rankable_count > 0
        out["pricingStatus"] = (
            "exact_official_evse" if rows and rankable_count == len(rows)
            else "exact_official_station_partial" if rankable_count
            else "lookup_required"
        )
        rebuilt.append(out)
    return rebuilt


def main() -> None:
    payload = json.loads(gzip.decompress(DATA.read_bytes()))
    evses = [normalize_evse(row) for row in payload.get("evses") or []]
    stations = rebuild_stations(payload.get("stations") or [], evses)

    rankable = [row for row in evses if row.get("rankableDirect")]
    blocked = [row for row in evses if not row.get("rankableDirect")]
    rates = Counter(f"{float(row['directEurPerKwh']):.3f}" for row in rankable)
    kingdom_evses = [row for row in evses if row.get("conditionalOffers")]
    structured_fee_evses = [row for row in evses if row.get("feePolicy")]

    payload["schemaVersion"] = "3.1.0"
    payload["stations"] = stations
    payload["evses"] = evses
    payload.setdefault("scope", {}).update({
        "operatorDirectOnly": True,
        "roamingIncluded": False,
        "countryDefaultsAreRankable": False,
        "exactDirectPricesFromDxp": True,
        "structuredTimeFeesAreRankable": True,
        "conditionalOffersRequireSelection": True,
    })
    payload.setdefault("sources", {}).update({
        "officialPricing": ALLEG0_PRICING_URL,
        "officialFeePolicy": ALLEG0_OVERSTAY_URL,
        "burgerKingKingdom": BK_PRESS_URL,
    })
    payload["matchPolicy"] = {
        "exactEvseIdFirst": True,
        "operatorMustBeAllego": True,
        "ambiguousOrDefaultOnlyFailsClosed": True,
        "structuredTimeFeesOnly": True,
        "conditionalOffersNeverReplaceDefault": True,
    }
    payload["counts"] = {
        **{k: v for k, v in (payload.get("counts") or {}).items() if k in {"officialRows", "franceStationCount", "stationsWithCoordinates", "irveLinkedEvseCount"}},
        "franceEvseCount": len(evses),
        "rankableEvseCount": len(rankable),
        "blockedEvseCount": len(blocked),
        "structuredFeeEvseCount": len(structured_fee_evses),
        "kingdomEligibleEvseCount": len(kingdom_evses),
        "coveragePct": round(100 * len(rankable) / len(evses), 2) if evses else 0,
        "rankableStationCount": sum(1 for station in stations if station.get("rankableDirect")),
        "distinctDirectRatesEurPerKwh": dict(sorted(rates.items())),
    }

    rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    DATA.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))

    reason_counts = Counter(row.get("blockingReason") or "none" for row in blocked)
    report = {
        "generatedAt": payload.get("generatedAt"),
        "counts": payload["counts"],
        "publicationReadyEvseCount": len(rankable),
        "publicationReadyStationCount": payload["counts"]["rankableStationCount"],
        "blockedEvseCount": len(blocked),
        "blockedReasonCounts": dict(reason_counts),
        "kingdomEligibleEvseCount": len(kingdom_evses),
        "structuredFeeEvseCount": len(structured_fee_evses),
        "blockedSample": [
            {
                "evseId": row.get("evseId"),
                "stationName": row.get("stationName"),
                "reason": row.get("blockingReason"),
                "status": row.get("dxpStatus"),
                "rateCandidates": row.get("allDirectRateCandidatesEurPerKwh"),
                "feeCandidates": row.get("feeCandidates"),
            }
            for row in blocked[:200]
        ],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
