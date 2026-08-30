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


def pricing_rules(prices: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"scope": "timeWindow", "start": "07:00", "end": "21:00", "pricePerKwh": prices["day"]},
        {"scope": "timeWindow", "start": "21:00", "end": "07:00", "pricePerKwh": prices["night"]},
    ]


def direct_offer(evse: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any] | None:
    tariff_class = str(evse.get("tariffClass") or "")
    prices = (policy.get("basicEurPerKwh") or {}).get(tariff_class)
    if evse.get("futureTariffRankable") is not True or not isinstance(prices, dict):
        return None
    if prices.get("day") is None or prices.get("night") is None:
        return None
    return {
        "channel": "operator_direct",
        "operator": "Enel X Way",
        "pricingType": "rules",
        "pricingRules": pricing_rules(prices),
        "timeZone": policy.get("timezone") or "Europe/Rome",
        "priceSelectionBasis": "session_start_local_time",
        "tariffClass": tariff_class,
        "source": "Enel On Your Way / Enel public tariff cards",
        "policyId": policy.get("policyId"),
        "rankable": True,
    }


def subscription_offer(evse: dict[str, Any], policy: dict[str, Any], plan_id: str, evidence_key: str) -> dict[str, Any] | None:
    tariff_class = str(evse.get("tariffClass") or "")
    live = policy.get("liveRenderedCardEvidence") or {}
    prices = (live.get(evidence_key) or {}).get(tariff_class)
    plan = (policy.get("plans") or {}).get(plan_id) or {}
    if not isinstance(prices, dict) or prices.get("day") is None or prices.get("night") is None:
        return None
    return {
        "channel": "subscription",
        "provider": "Enel On Your Way",
        "subscriptionId": plan_id,
        "network": "Enel X Way",
        "pricingType": "rules",
        "pricingRules": pricing_rules(prices),
        "timeZone": policy.get("timezone") or "Europe/Rome",
        "priceSelectionBasis": "session_start_local_time",
        "tariffClass": tariff_class,
        "monthlyFeeEur": plan.get("fixedFeeEur"),
        "rankableWhenSelected": True,
        "mustNotOverwriteDirectTariff": True,
        "source": "Enel live rendered tariff cards",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--consolidated", default="data/consolidation/italy_v9_candidate.json.gz")
    ap.add_argument("--enel", default="data/national/enel_direct_stations_italy_final_candidate.json.gz")
    ap.add_argument("--report", default="data/reports/italy_enel_v9_overlay_report.json")
    args = ap.parse_args()

    consolidated_path = Path(args.consolidated)
    consolidated = load_gz(consolidated_path)
    enel = load_gz(Path(args.enel))
    policy = enel.get("operatorTariffPolicy") or {}
    enx = {str(e.get("evseId")): e for e in enel.get("evses", []) if e.get("evseId")}

    counts = Counter()
    direct_classes = Counter()
    sub_counts = Counter()
    conflicts = []

    for evse in consolidated.get("evses", []):
        evse_id = str(evse.get("evseId") or "")
        row = enx.get(evse_id)
        if not row:
            continue
        counts["enxEvseMatched"] += 1
        existing = evse.get("tccV9DirectTariff")
        if existing and existing.get("operator") not in (None, "Enel X Way"):
            conflicts.append({"evseId": evse_id, "existingOperator": existing.get("operator")})
            counts["crossOperatorConflict"] += 1
            continue

        direct = direct_offer(row, policy)
        if direct:
            evse["tccV9DirectTariff"] = direct
            evse["tccV9RankableDirect"] = True
            counts["enxDirectRankable"] += 1
            direct_classes[direct["tariffClass"]] += 1
        else:
            counts["enxDirectBlocked"] += 1

        current = list(evse.get("tccV9SubscriptionTariffs") or [])
        for plan_id, evidence_key in (
            ("enel_plug_and_go_super", "plugAndGoSuperEurPerKwh"),
            ("enel_plug_and_go_explorer", "plugAndGoExplorerEurPerKwh"),
        ):
            offer = subscription_offer(row, policy, plan_id.replace("enel_", ""), evidence_key)
            if not offer:
                continue
            offer["subscriptionId"] = plan_id
            key = (offer["provider"], offer["subscriptionId"], offer["network"])
            if not any((x.get("provider"), x.get("subscriptionId"), x.get("network")) == key for x in current):
                current.append(offer)
                sub_counts[plan_id] += 1
        evse["tccV9SubscriptionTariffs"] = current
        evse["tccV9HasRankableSelectedSubscription"] = bool(current)

    if conflicts:
        raise RuntimeError(f"Enel cross-operator conflicts: {len(conflicts)}")

    # Recompute station summaries and global counters after Enel enrichment.
    evses_by_station: dict[str, list[dict[str, Any]]] = {}
    for evse in consolidated.get("evses", []):
        evses_by_station.setdefault(str(evse.get("stationId") or ""), []).append(evse)
    for station in consolidated.get("stations", []):
        rows = evses_by_station.get(str(station.get("stationId") or ""), [])
        station["evses"] = rows
        station["rankableDirectEvseCount"] = sum(1 for e in rows if e.get("tccV9RankableDirect"))
        station["rankableDirect"] = station["rankableDirectEvseCount"] > 0
        station["rankableSelectedSubscriptionEvseCount"] = sum(1 for e in rows if e.get("tccV9HasRankableSelectedSubscription"))
        station["hasRankableSelectedSubscription"] = station["rankableSelectedSubscriptionEvseCount"] > 0

    operator_counts = Counter()
    subscription_counts = Counter()
    direct_total = subscription_evse_total = 0
    for evse in consolidated.get("evses", []):
        if evse.get("tccV9RankableDirect"):
            direct_total += 1
            operator_counts[str((evse.get("tccV9DirectTariff") or {}).get("operator") or "UNKNOWN")] += 1
        subs = evse.get("tccV9SubscriptionTariffs") or []
        if subs:
            subscription_evse_total += 1
            for sub in subs:
                subscription_counts[f"{sub.get('subscriptionId')}:{sub.get('network')}"] += 1

    total = len(consolidated.get("evses", []))
    consolidated["schemaVersion"] = "1.4.0"
    consolidated.setdefault("rules", {})["sessionStartDeterminesEnelTariffForWholeSession"] = True
    c = consolidated.setdefault("counts", {})
    c["rankableDirectEvseCount"] = direct_total
    c["rankableDirectCoveragePct"] = round(100 * direct_total / total, 2) if total else 0.0
    c["rankableDirectByOperator"] = dict(sorted(operator_counts.items()))
    c["rankableSelectedSubscriptionEvseCount"] = subscription_evse_total
    c["rankableSelectedSubscriptionCoveragePct"] = round(100 * subscription_evse_total / total, 2) if total else 0.0
    c["rankableSelectedSubscriptionByOffer"] = dict(sorted(subscription_counts.items()))
    consolidated.setdefault("subscriptions", {}).update({
        "enel_plug_and_go_super": {
            "provider": "Enel On Your Way",
            "monthlyFeeEur": (policy.get("plans") or {}).get("plug_and_go_super", {}).get("fixedFeeEur"),
            "rankableOnlyWhenSelected": True,
            "network": "Enel X Way",
        },
        "enel_plug_and_go_explorer": {
            "provider": "Enel On Your Way",
            "monthlyFeeEur": (policy.get("plans") or {}).get("plug_and_go_explorer", {}).get("fixedFeeEur"),
            "rankableOnlyWhenSelected": True,
            "network": "Enel X Way",
        },
    })

    save_gz(consolidated_path, consolidated)
    report = {
        "schemaVersion": "1.0.0",
        "sourcePolicyId": policy.get("policyId"),
        "counts": dict(sorted(counts.items())),
        "directByTariffClass": dict(sorted(direct_classes.items())),
        "subscriptionsAdded": dict(sorted(sub_counts.items())),
        "consolidatedDirectByOperator": c["rankableDirectByOperator"],
        "consolidatedDirectEvseCount": c["rankableDirectEvseCount"],
        "consolidatedSubscriptionEvseCount": c["rankableSelectedSubscriptionEvseCount"],
        "ewivaPolicy": "fail_closed_until_exact_eMSP_EVSE_coverage_is_validated",
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
