#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRICING_SOURCE = "https://mobility.dufercoenergia.com/prices-and-subscriptions"
TERMS_SOURCE = "https://mobility.dufercoenergia.com/terms-and-conditions"
TIME_ZONE = "Europe/Rome"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise RuntimeError("PUN payload must be an object")
    return data


def finite(value: Any) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def is_duferco(evse: dict[str, Any]) -> bool:
    return "duferco" in str(evse.get("operator") or "").casefold()


def rules(normal: float, discounted: float) -> list[dict[str, Any]]:
    common = {"mustEndSameLocalDay": True}
    weekdays = [1, 2, 3, 4, 5, 6]
    return [
        {"scope": "allDay", "holidayOnly": True, "pricePerKwh": discounted, **common},
        {"scope": "allDay", "daysOfWeek": [0], "excludeHolidays": True, "pricePerKwh": discounted, **common},
        {"scope": "timeWindow", "daysOfWeek": weekdays, "excludeHolidays": True, "start": "08:00", "end": "12:00", "pricePerKwh": normal, **common},
        {"scope": "timeWindow", "daysOfWeek": weekdays, "excludeHolidays": True, "start": "12:00", "end": "15:00", "pricePerKwh": discounted, **common},
        {"scope": "timeWindow", "daysOfWeek": weekdays, "excludeHolidays": True, "start": "15:00", "end": "22:00", "pricePerKwh": normal, **common},
        {"scope": "timeWindow", "daysOfWeek": weekdays, "excludeHolidays": True, "start": "22:00", "end": "08:00", "pricePerKwh": discounted, **common},
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pun", default="data/national/pun_italy_national.json.gz")
    ap.add_argument("--out", default="data/national/duferco_direct_stations_italy.json.gz")
    ap.add_argument("--report", default="data/reports/duferco_italy_pun_direct_report.json")
    args = ap.parse_args()

    pun = load_gz(Path(args.pun))
    pun_evses = [e for e in pun.get("evses", []) if isinstance(e, dict)]
    matched = [e for e in pun_evses if is_duferco(e)]
    if not matched:
        raise RuntimeError("No Duferco EVSE found in PUN")

    party_ids = Counter(str(e.get("partyId") or "UNKNOWN") for e in matched)
    operator_labels = Counter(str(e.get("operator") or "UNKNOWN") for e in matched)
    station_ids = {str(e.get("stationId") or "") for e in matched if e.get("stationId")}
    blocked = Counter()
    rows: list[dict[str, Any]] = []
    class_counts = Counter()

    for e in matched:
        evse_id = str(e.get("evseId") or "").strip()
        power = finite(e.get("maxPowerKw"))
        if not evse_id:
            blocked["missing_evse_id"] += 1
            continue
        if power is None or power <= 0:
            blocked["missing_or_invalid_max_power"] += 1
            rows.append({
                "evseId": evse_id,
                "stationId": e.get("stationId"),
                "operator": e.get("operator"),
                "partyId": e.get("partyId"),
                "maxPowerKw": power,
                "rankableDirectTariff": False,
                "blockingReason": "missing_or_invalid_max_power",
            })
            continue

        if power <= 100:
            tariff_class = "quick_fast_le_100kw"
            normal, discounted = 0.74, 0.52
        else:
            tariff_class = "ultra_fast_gt_100kw"
            normal, discounted = 0.79, 0.74
        class_counts[tariff_class] += 1

        rows.append({
            "evseId": evse_id,
            "stationId": e.get("stationId"),
            "operator": e.get("operator"),
            "partyId": e.get("partyId"),
            "maxPowerKw": power,
            "directTariffClass": tariff_class,
            "rankableDirectTariff": True,
            "directTariff": {
                "currency": "EUR",
                "pricingType": "rules",
                "timeZone": TIME_ZONE,
                "holidayCalendar": "IT",
                "rules": rules(normal, discounted),
                "postChargeFeeUnknown": True,
                "postChargeFeePolicy": "station_specific_amount_shown_in_station_detail; fail_closed_when_post_charge_dwell_is_positive",
                "source": PRICING_SOURCE,
                "termsSource": TERMS_SOURCE,
            },
        })

    rankable = sum(1 for e in rows if e.get("rankableDirectTariff") is True)
    power_coverage = 100 * rankable / len(matched) if matched else 0.0
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "duferco-italy-pun-direct-candidate",
        "generatedAt": now_iso(),
        "country": "IT",
        "operator": "Duferco Mobility",
        "inventorySource": "GSE PUN",
        "pricingSource": PRICING_SOURCE,
        "termsSource": TERMS_SOURCE,
        "rules": {
            "exactPunEvseOnly": True,
            "powerClassFromPunMaxPower": True,
            "quickFastThresholdKw": 100,
            "ultraFastThreshold": ">100",
            "scheduleUsesEuropeRome": True,
            "italianPublicHolidaysUseDiscountedRate": True,
            "sessionMustStartAndEndInSameEligibleBandOrDay": True,
            "unknownStationSpecificPostChargeFeeFailsClosedWhenApplicable": True,
        },
        "counts": {
            "punEvseTotal": len(pun_evses),
            "dufercoPunStations": len(station_ids),
            "dufercoPunEvse": len(matched),
            "rankableDirectEvse": rankable,
            "powerCoveragePct": round(power_coverage, 4),
            "byTariffClass": dict(sorted(class_counts.items())),
            "partyIds": dict(sorted(party_ids.items())),
            "operatorLabels": dict(sorted(operator_labels.items())),
            "blockedReasons": dict(sorted(blocked.items())),
        },
        "evses": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(gzip.compress((json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(), compresslevel=9, mtime=0))
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({k: payload[k] for k in ("generatedAt", "operator", "rules", "counts")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
