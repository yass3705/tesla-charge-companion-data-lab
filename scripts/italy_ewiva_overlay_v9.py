#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def save_gz(path: Path, payload: dict[str, Any]) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def rules(day: float, night: float) -> list[dict[str, Any]]:
    return [
        {"scope": "timeWindow", "start": "07:00", "end": "21:00", "pricePerKwh": day},
        {"scope": "timeWindow", "start": "21:00", "end": "07:00", "pricePerKwh": night},
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--consolidated", default="data/consolidation/italy_v9_candidate.json.gz")
    ap.add_argument("--ewiva", default="data/national/enel_ewiva_partner_italy.json.gz")
    ap.add_argument("--report", default="data/reports/italy_ewiva_v9_overlay_report.json")
    args = ap.parse_args()

    consolidated_path = Path(args.consolidated)
    d = load_gz(consolidated_path)
    ewiva = load_gz(Path(args.ewiva))
    policy = ewiva.get("tariffPolicy") or {}
    source_rows = {str(e.get("evseId")): e for e in ewiva.get("evses", []) if e.get("evseId")}

    counts = Counter()
    basic_by_class = Counter()
    subs_added = Counter()

    for evse in d.get("evses", []):
        evse_id = str(evse.get("evseId") or "")
        row = source_rows.get(evse_id)
        if not row:
            continue
        counts["ewiEvseMatched"] += 1

        # Ewiva physical identity must remain EWI. Enel is the commercial provider here,
        # therefore these tariffs are eMSP/subscription offers and never CPO-direct.
        if str(evse.get("partyId") or "").upper() != "EWI" or str(row.get("partyId") or "").upper() != "EWI":
            counts["partyMismatchBlocked"] += 1
            continue

        schedule = row.get("partnerTariffSchedule") or {}
        basic = schedule.get("pay_per_use_basic") or {}
        tariff_class = str(row.get("tariffClass") or "")
        day = basic.get("dayEurPerKwh")
        night = basic.get("nightEurPerKwh")
        if day is not None and night is not None:
            offer = {
                "channel": "emsp",
                "provider": "Enel On Your Way",
                "network": "Ewiva",
                "currency": "EUR",
                "pricingType": "rules",
                "pricingRules": rules(float(day), float(night)),
                "timeZone": policy.get("timezone") or "Europe/Rome",
                "priceSelectionBasis": policy.get("priceSelectionBasis") or "session_start_local_time",
                "tariffClass": tariff_class,
                "rankable": True,
                "mustNotOverwriteDirectOrSelectedSubscription": True,
                "postChargeFeeUnknown": True,
                "source": "Enel On Your Way live tariff cards + exact PUN EWI identity",
            }
            current = list(evse.get("tccV9EmspTariffs") or [])
            key = (offer["provider"], offer["network"])
            if not any((x.get("provider"), x.get("network")) == key for x in current):
                current.append(offer)
                counts["ewivaBasicEmspAdded"] += 1
                basic_by_class[tariff_class] += 1
            evse["tccV9EmspTariffs"] = current
            evse["tccV9HasRankableEmsp"] = bool(current)
        else:
            counts["ewivaBasicBlockedMissingSchedule"] += 1

        current_subs = list(evse.get("tccV9SubscriptionTariffs") or [])
        for source_plan, subscription_id in (
            ("plug_and_go_super", "enel_plug_and_go_super"),
            ("plug_and_go_explorer", "enel_plug_and_go_explorer"),
        ):
            plan = schedule.get(source_plan) or {}
            day = plan.get("dayEurPerKwh")
            night = plan.get("nightEurPerKwh")
            if day is None or night is None:
                counts[f"{subscription_id}BlockedMissingSchedule"] += 1
                continue
            offer = {
                "channel": "subscription",
                "provider": "Enel On Your Way",
                "subscriptionId": subscription_id,
                "network": "Ewiva",
                "currency": "EUR",
                "pricingType": "rules",
                "pricingRules": rules(float(day), float(night)),
                "timeZone": policy.get("timezone") or "Europe/Rome",
                "priceSelectionBasis": policy.get("priceSelectionBasis") or "session_start_local_time",
                "tariffClass": tariff_class,
                "monthlyFeeEur": plan.get("fixedFeeEur"),
                "rankableWhenSelected": True,
                "mustNotOverwriteDirectTariff": True,
                "postChargeFeeUnknown": True,
                "source": "Enel On Your Way live tariff cards + exact PUN EWI identity",
            }
            key = (offer["provider"], offer["subscriptionId"], offer["network"])
            if not any((x.get("provider"), x.get("subscriptionId"), x.get("network")) == key for x in current_subs):
                current_subs.append(offer)
                subs_added[subscription_id] += 1
        evse["tccV9SubscriptionTariffs"] = current_subs
        evse["tccV9HasRankableSelectedSubscription"] = bool(current_subs)

        # Ewiva's own 0.80 EUR/kWh contactless retail tariff is valid only at enabled
        # stations. The national candidate does not expose a reliable contactless flag,
        # so it intentionally remains blocked instead of being generalized nationally.
        counts["ewivaDirectContactlessBlockedNoStationCapabilityFlag"] += 1

    # Recompute station and global offer counters.
    evses_by_station: dict[str, list[dict[str, Any]]] = {}
    for evse in d.get("evses", []):
        evses_by_station.setdefault(str(evse.get("stationId") or ""), []).append(evse)
    for station in d.get("stations", []):
        rows = evses_by_station.get(str(station.get("stationId") or ""), [])
        station["evses"] = rows
        station["rankableSelectedSubscriptionEvseCount"] = sum(1 for e in rows if e.get("tccV9HasRankableSelectedSubscription"))
        station["hasRankableSelectedSubscription"] = station["rankableSelectedSubscriptionEvseCount"] > 0
        station["rankableEmspEvseCount"] = sum(1 for e in rows if e.get("tccV9HasRankableEmsp"))
        station["hasRankableEmsp"] = station["rankableEmspEvseCount"] > 0

    subscription_counts = Counter()
    emsp_counts = Counter()
    subscription_evse_total = emsp_evse_total = 0
    for evse in d.get("evses", []):
        subs = evse.get("tccV9SubscriptionTariffs") or []
        if subs:
            subscription_evse_total += 1
            for sub in subs:
                subscription_counts[f"{sub.get('subscriptionId')}:{sub.get('network')}"] += 1
        emsps = evse.get("tccV9EmspTariffs") or []
        if emsps:
            emsp_evse_total += 1
            for offer in emsps:
                emsp_counts[f"{offer.get('provider')}:{offer.get('network') or ''}"] += 1

    total = len(d.get("evses", []))
    c = d.setdefault("counts", {})
    c["rankableSelectedSubscriptionEvseCount"] = subscription_evse_total
    c["rankableSelectedSubscriptionCoveragePct"] = round(100 * subscription_evse_total / total, 2) if total else 0.0
    c["rankableSelectedSubscriptionByOffer"] = dict(sorted(subscription_counts.items()))
    c["rankableEmspEvseCount"] = emsp_evse_total
    c["rankableEmspCoveragePct"] = round(100 * emsp_evse_total / total, 2) if total else 0.0
    c["rankableEmspByProvider"] = dict(sorted(emsp_counts.items()))

    d.setdefault("rules", {})["enelEwivaOffersAreCommercialLayersNotCpoDirect"] = True
    d["rules"]["ewivaDirectContactlessRequiresStationCapabilityEvidence"] = True
    d.setdefault("subscriptions", {}).setdefault("enel_plug_and_go_super", {}).update({"networkCoverage": ["Enel X Way", "Ewiva"]})
    d.setdefault("subscriptions", {}).setdefault("enel_plug_and_go_explorer", {}).update({"networkCoverage": ["Enel X Way", "Ewiva"]})
    d.setdefault("emspProviders", {})["enel_on_your_way_ewiva"] = {
        "provider": "Enel On Your Way",
        "network": "Ewiva",
        "commercialLayer": "emsp",
        "rankable": True,
        "notCpoDirect": True,
    }

    save_gz(consolidated_path, d)
    report = {
        "schemaVersion": "1.0.0",
        "counts": dict(sorted(counts.items())),
        "basicAddedByTariffClass": dict(sorted(basic_by_class.items())),
        "subscriptionsAdded": dict(sorted(subs_added.items())),
        "ewivaPunEvseCount": (ewiva.get("counts") or {}).get("punEwiEvseCount"),
        "ewivaPartnerScheduleCoveragePct": (ewiva.get("counts") or {}).get("partnerScheduleCoveragePct"),
        "policy": {
            "basicIsEnelEmspNotEwivaDirect": True,
            "plugAndGoRequiresSelection": True,
            "directContactless080BlockedWithoutStationCapabilityFlag": True,
            "unknownPostChargeFeeFailsClosed": True,
        },
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
