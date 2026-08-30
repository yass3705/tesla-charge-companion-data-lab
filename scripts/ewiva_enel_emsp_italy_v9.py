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

SOURCE_PDF = "https://www.enel.it/content/dam/asset/documenti/enel-x-way/tariffe-abbonamenti/enel-x-piani-di-ricarica.pdf"
SOURCE_PAGE = "https://www.enel.it/it-it/mobilita-elettrica/tariffe-abbonamenti"
TIME_ZONE = "Europe/Rome"

BASIC = {
    "AC": {"day": 0.67, "night": 0.58},
    "DC": {"day": 0.75, "night": 0.64},
    "HPC": {"allDay": 0.86},
}
SUPER_DISCOUNT = 0.05
PENALTY_EUR_PER_MIN = {"AC": 0.10, "DC": 0.20, "HPC": 0.30}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise RuntimeError("expected object payload")
    return data


def finite(v: Any) -> float | None:
    try:
        n = float(v)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def is_ewiva(evse: dict[str, Any]) -> bool:
    return "ewiva" in str(evse.get("operator") or "").casefold()


def tariff_class(evse: dict[str, Any]) -> str | None:
    connectors = [c for c in (evse.get("connectors") or []) if isinstance(c, dict)]
    power_types = {str(c.get("powerType") or "").upper() for c in connectors}
    if any(t.startswith("AC") for t in power_types):
        return "AC"
    powers = [finite(c.get("maxPowerKw")) for c in connectors]
    powers = [p for p in powers if p is not None]
    max_power = max(powers) if powers else finite(evse.get("maxPowerKw"))
    if max_power is not None and max_power > 99:
        return "HPC"
    if any(t.startswith("DC") for t in power_types) or max_power is not None:
        return "DC"
    return None


def pricing_rules(cls: str, discount: float = 0.0) -> list[dict[str, Any]]:
    if cls == "HPC":
        return [{"scope": "allDay", "pricePerKwh": round(BASIC[cls]["allDay"] - discount, 2)}]
    return [
        {"scope": "timeWindow", "start": "07:00", "end": "21:00", "pricePerKwh": round(BASIC[cls]["day"] - discount, 2)},
        {"scope": "timeWindow", "start": "21:00", "end": "07:00", "pricePerKwh": round(BASIC[cls]["night"] - discount, 2)},
    ]


def post_charge_fee(cls: str) -> dict[str, Any]:
    fee: dict[str, Any] = {
        "eurPerMinute": PENALTY_EUR_PER_MIN[cls],
        "graceMinutes": 0,
        "policy": "Enel On Your Way post-charge penalty; applied after charging ends when operator applicability window is active",
    }
    # Enel PDF: for AC on non-Enel operators in the app, penalty applies 07:00-23:00.
    # V9 models the inverse as an exempt local window and fails closed if the
    # post-charge start timestamp is unavailable.
    if cls == "AC":
        fee["exemptLocalWindows"] = [{"start": "23:00", "end": "07:00"}]
    return fee


def offer_pricing(cls: str, discount: float = 0.0) -> dict[str, Any]:
    return {
        "type": "rules",
        "timeZone": TIME_ZONE,
        "priceSelectionBasis": "session_start_local_time",
        "rules": pricing_rules(cls, discount),
        "postChargeFee": post_charge_fee(cls),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pun", default="data/national/pun_italy_national.json.gz")
    ap.add_argument("--out", default="data/national/ewiva_enel_emsp_italy_candidate.json.gz")
    ap.add_argument("--report", default="data/reports/ewiva_enel_emsp_italy_report.json")
    args = ap.parse_args()

    pun = load_gz(Path(args.pun))
    all_evses = [e for e in pun.get("evses", []) if isinstance(e, dict)]
    matched = [e for e in all_evses if is_ewiva(e)]
    if not matched:
        raise RuntimeError("no Ewiva EVSE found in PUN")

    classes = Counter()
    parties = Counter()
    operators = Counter()
    blocked = Counter()
    entries: list[dict[str, Any]] = []

    for e in matched:
        eid = str(e.get("evseId") or "").strip()
        cls = tariff_class(e)
        parties[str(e.get("partyId") or "UNKNOWN")] += 1
        operators[str(e.get("operator") or "UNKNOWN")] += 1
        if not eid:
            blocked["missing_evse_id"] += 1
            continue
        if cls not in BASIC:
            blocked["technology_class_unresolved"] += 1
            entries.append({"evseId": eid, "stationId": e.get("stationId"), "rankable": False, "blockingReason": "technology_class_unresolved"})
            continue
        classes[cls] += 1
        entries.append({
            "evseId": eid,
            "stationId": e.get("stationId"),
            "operator": e.get("operator"),
            "partyId": e.get("partyId"),
            "tariffClass": cls,
            "enelOnYourWayBasic": {
                "channel": "emsp",
                "provider": "Enel On Your Way",
                "billedBy": "Enel X S.r.l.",
                "rankable": True,
                "notCpoDirect": True,
                "pricing": offer_pricing(cls, 0.0),
                "source": SOURCE_PDF,
            },
            "subscriptions": [
                {
                    "subscriptionId": "enel_plug_and_go_super",
                    "provider": "Enel On Your Way",
                    "monthlyFeeEur": 4.0,
                    "rankableWhenSelected": True,
                    "pricing": offer_pricing(cls, SUPER_DISCOUNT),
                    "source": SOURCE_PDF,
                    "validThrough": "2027-01-14",
                }
            ],
        })

    rankable = sum(1 for x in entries if (x.get("enelOnYourWayBasic") or {}).get("rankable") is True)
    station_count = len({str(e.get("stationId")) for e in matched if e.get("stationId")})
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "ewiva-enel-on-your-way-italy-candidate",
        "generatedAt": now_iso(),
        "country": "IT",
        "operator": "Ewiva",
        "inventorySource": "GSE PUN",
        "commercialLayer": "Enel On Your Way eMSP",
        "sources": [SOURCE_PDF, SOURCE_PAGE],
        "rules": {
            "exactPunEwivaEvseOnly": True,
            "basicIsEmspNotCpoDirect": True,
            "sessionStartSelectsTariffForWholeSession": True,
            "timeZone": TIME_ZONE,
            "plugAndGoSuperRankableOnlyWhenSelected": True,
            "explorerFailClosed": True,
            "explorerBlockingReason": "current Enel public sources disagree on the applicable HPC base/discounted value; do not rank Ewiva Explorer until reconciled",
            "postChargePenaltyIncluded": True,
            "postChargeAcApplicability": "07:00-23:00 local for non-Enel operators shown in app",
            "postChargeDcHpcApplicability": "all day",
        },
        "tariffs": {
            "basic": BASIC,
            "plugAndGoSuperDiscountEurPerKwh": SUPER_DISCOUNT,
            "postChargeEurPerMin": PENALTY_EUR_PER_MIN,
        },
        "counts": {
            "punTotalEvse": len(all_evses),
            "ewivaStations": station_count,
            "ewivaEvse": len(matched),
            "rankableBasicEmspEvse": rankable,
            "rankablePlugAndGoSuperEvse": rankable,
            "byTariffClass": dict(sorted(classes.items())),
            "partyIds": dict(sorted(parties.items())),
            "operatorLabels": dict(sorted(operators.items())),
            "blockedReasons": dict(sorted(blocked.items())),
        },
        "entries": entries,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    out.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({k: payload[k] for k in ("generatedAt", "commercialLayer", "rules", "tariffs", "counts")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
