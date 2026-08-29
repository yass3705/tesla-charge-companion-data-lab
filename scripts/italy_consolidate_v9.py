#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pun", default="data/national/pun_italy_national.json.gz")
    ap.add_argument("--plenitude", default="data/national/plenitude_direct_stations_italy.json.gz")
    ap.add_argument("--a2a", default="data/national/a2a_direct_stations_italy.json.gz")
    ap.add_argument("--atlante", default="data/national/atlante_go_italy_overlay.json.gz")
    ap.add_argument("--atlante-chargeleague", default="data/national/atlante_go_chargeleague_italy_overlay.json.gz")
    ap.add_argument("--ges-nextcharge", default="data/national/nextcharge_ges_italy_candidate.json.gz")
    ap.add_argument("--out", default="data/consolidation/italy_v9_candidate.json.gz")
    ap.add_argument("--report", default="data/reports/italy_v9_consolidation_report.json")
    args = ap.parse_args()

    pun = load_gz(Path(args.pun))
    plenitude = load_gz(Path(args.plenitude))
    a2a = load_gz(Path(args.a2a))
    atlante = load_gz(Path(args.atlante))
    atlante_chargeleague = load_gz(Path(args.atlante_chargeleague))
    ges_nextcharge = load_gz(Path(args.ges_nextcharge))

    direct_by_evse = {}
    subscriptions_by_evse = {}
    emsp_by_evse = {}
    blocked = Counter()

    for e in plenitude.get("evses", []):
        evse_id = str(e.get("evseId") or "")
        if not evse_id:
            continue
        if e.get("rankableDirect") and e.get("directEurPerKwh") is not None:
            direct_by_evse[evse_id] = {
                "channel": "operator_direct",
                "operator": "Plenitude On The Road",
                "eurPerKwh": e.get("directEurPerKwh"),
                "tariffClass": e.get("directTariffClass"),
                "feePolicy": e.get("feePolicy"),
                "validFrom": e.get("directTariffValidFrom"),
                "validThrough": e.get("directTariffValidThrough"),
                "source": e.get("tariffSource"),
                "rankable": True,
            }
        else:
            blocked[f"plenitude:{e.get('blockingReason') or 'not_rankable'}"] += 1

    for e in a2a.get("evses", []):
        evse_id = str(e.get("evseId") or "")
        if not evse_id:
            continue
        direct = e.get("directTariff") if isinstance(e.get("directTariff"), dict) else {}
        if e.get("rankableDirectTariff") is True and direct.get("energyEurPerKwh") is not None:
            candidate = {
                "channel": "operator_direct",
                "operator": "A2A e-moving",
                "eurPerKwh": direct.get("energyEurPerKwh"),
                "occupancyEurPerMin": direct.get("occupancyEurPerMin"),
                "occupancyPolicy": direct.get("occupancyPolicy"),
                "source": direct.get("source") or "A2A public e-moving station detail",
                "rankable": True,
            }
            previous = direct_by_evse.get(evse_id)
            if previous and previous.get("operator") != candidate.get("operator"):
                blocked["cross_operator_evse_conflict"] += 1
                direct_by_evse.pop(evse_id, None)
            else:
                direct_by_evse[evse_id] = candidate
        else:
            blocked["a2a:not_rankable"] += 1

    for layer_name, layer in (("atlante_own", atlante), ("atlante_chargeleague", atlante_chargeleague)):
        for e in layer.get("evses", []):
            evse_id = str(e.get("evseId") or "")
            if not evse_id:
                continue
            for tariff in e.get("subscriptionTariffs", []):
                if tariff.get("rankableWhenSubscriptionSelected") is not True:
                    blocked[f"{layer_name}:subscription_not_rankable"] += 1
                    continue
                if tariff.get("energyEurPerKwh") is None:
                    blocked[f"{layer_name}:missing_energy_price"] += 1
                    continue
                normalized = {
                    "channel": "subscription",
                    "provider": tariff.get("provider") or "Atlante",
                    "subscriptionId": tariff.get("subscriptionId") or "atlante_go",
                    "network": tariff.get("network") or tariff.get("serviceNetwork") or "Atlante",
                    "eurPerKwh": tariff.get("energyEurPerKwh"),
                    "rankableWhenSelected": True,
                    "mustNotOverwriteDirectTariff": bool(tariff.get("mustNotOverwriteCpoDirectTariff", True)),
                }
                current = subscriptions_by_evse.setdefault(evse_id, [])
                key = (normalized["provider"], normalized["subscriptionId"], normalized["network"])
                if any((x.get("provider"), x.get("subscriptionId"), x.get("network")) == key for x in current):
                    blocked[f"{layer_name}:duplicate_subscription_tariff"] += 1
                    continue
                current.append(normalized)

    # NextCharge is validated as a consumer/eMSP tariff layer, never as GES CPO-direct pricing.
    for e in ges_nextcharge.get("entries", []):
        evse_id = str(e.get("evseId") or "").upper()
        if not evse_id:
            continue
        if e.get("rankableAsCpoDirectTariff") is True:
            blocked["ges_nextcharge:unexpected_cpo_direct_flag"] += 1
            continue
        if e.get("rankableAsNextChargeEmspTariff") is not True:
            blocked["ges_nextcharge:not_rankable_emsp"] += 1
            continue
        snap = e.get("tariffSnapshot") if isinstance(e.get("tariffSnapshot"), dict) else {}
        prices = snap.get("prices") if isinstance(snap.get("prices"), dict) else {}
        if str(snap.get("currency") or "").upper() != "EUR" or not prices:
            blocked["ges_nextcharge:invalid_tariff_snapshot"] += 1
            continue
        normalized = {
            "channel": "emsp",
            "provider": "NextCharge",
            "billedBy": "Go Electric Stations S.r.l.s.",
            "currency": "EUR",
            "prices": {k: prices[k] for k in ("energy", "time", "parking", "session") if k in prices},
            "restrictions": snap.get("restrictions") or {},
            "source": "NextCharge public web app",
            "rankable": True,
            "mustNotOverwriteDirectOrSelectedSubscription": True,
        }
        emsp_by_evse.setdefault(evse_id, []).append(normalized)

    merged_evses = []
    operator_counts = Counter()
    subscription_counts = Counter()
    emsp_counts = Counter()
    rankable_count = 0
    subscription_evse_count = 0
    emsp_evse_count = 0
    for e in pun.get("evses", []):
        out = dict(e)
        evse_id = str(out.get("evseId") or "")
        tariff = direct_by_evse.get(evse_id)
        subscription_tariffs = subscriptions_by_evse.get(evse_id, [])
        emsp_tariffs = emsp_by_evse.get(evse_id.upper(), [])
        out["tccV9DirectTariff"] = tariff
        out["tccV9RankableDirect"] = bool(tariff and tariff.get("rankable"))
        out["tccV9SubscriptionTariffs"] = subscription_tariffs
        out["tccV9HasRankableSelectedSubscription"] = bool(subscription_tariffs)
        out["tccV9EmspTariffs"] = emsp_tariffs
        out["tccV9HasRankableEmsp"] = bool(emsp_tariffs)
        if out["tccV9RankableDirect"]:
            rankable_count += 1
            operator_counts[tariff.get("operator") or "UNKNOWN"] += 1
        if subscription_tariffs:
            subscription_evse_count += 1
            for st in subscription_tariffs:
                subscription_counts[f"{st.get('subscriptionId')}:{st.get('network')}"] += 1
        if emsp_tariffs:
            emsp_evse_count += 1
            for et in emsp_tariffs:
                emsp_counts[et.get("provider") or "UNKNOWN"] += 1
        merged_evses.append(out)

    evse_by_station = {}
    for e in merged_evses:
        evse_by_station.setdefault(str(e.get("stationId") or ""), []).append(e)

    merged_stations = []
    for s in pun.get("stations", []):
        out = {k: v for k, v in s.items() if k != "evses"}
        rows = evse_by_station.get(str(s.get("stationId") or ""), [])
        out["evses"] = rows
        out["rankableDirectEvseCount"] = sum(1 for e in rows if e.get("tccV9RankableDirect"))
        out["rankableDirect"] = out["rankableDirectEvseCount"] > 0
        out["rankableSelectedSubscriptionEvseCount"] = sum(1 for e in rows if e.get("tccV9HasRankableSelectedSubscription"))
        out["hasRankableSelectedSubscription"] = out["rankableSelectedSubscriptionEvseCount"] > 0
        out["rankableEmspEvseCount"] = sum(1 for e in rows if e.get("tccV9HasRankableEmsp"))
        out["hasRankableEmsp"] = out["rankableEmspEvseCount"] > 0
        merged_stations.append(out)

    payload = {
        "schemaVersion": "1.2.0",
        "dataset": "italy-v9-consolidated-candidate",
        "generatedAt": now_iso(),
        "country": "IT",
        "backbone": "GSE PUN",
        "pricingPrecedence": ["operator_direct", "selected_subscription", "emsp", "pun_fallback"],
        "rules": {
            "punIsPhysicalInventoryMaster": True,
            "operatorTariffsRequireExactOrValidatedJoin": True,
            "crossOperatorEvseConflictFailsClosed": True,
            "punTariffNotRankableUntilSemanticsValidated": True,
            "subscriptionTariffsRankableOnlyWhenSelected": True,
            "subscriptionTariffsNeverOverwriteDirectTariff": True,
            "emspTariffsNeverMasqueradeAsCpoDirect": True,
            "emspTariffsDoNotOverwriteDirectOrSelectedSubscription": True,
            "teslaHandledByDedicatedTeslaSourceAtPublishLayer": True,
        },
        "counts": {
            "punEvseCount": len(merged_evses),
            "punStationCount": len(merged_stations),
            "rankableDirectEvseCount": rankable_count,
            "rankableDirectCoveragePct": round(100 * rankable_count / len(merged_evses), 2) if merged_evses else 0.0,
            "rankableDirectByOperator": dict(sorted(operator_counts.items())),
            "rankableSelectedSubscriptionEvseCount": subscription_evse_count,
            "rankableSelectedSubscriptionCoveragePct": round(100 * subscription_evse_count / len(merged_evses), 2) if merged_evses else 0.0,
            "rankableSelectedSubscriptionByOffer": dict(sorted(subscription_counts.items())),
            "rankableEmspEvseCount": emsp_evse_count,
            "rankableEmspCoveragePct": round(100 * emsp_evse_count / len(merged_evses), 2) if merged_evses else 0.0,
            "rankableEmspByProvider": dict(sorted(emsp_counts.items())),
            "blockedReasons": dict(sorted(blocked.items())),
        },
        "subscriptions": {
            "atlante_go": {
                "provider": "Atlante",
                "monthlyFeeEur": atlante.get("subscription", {}).get("monthlyFeeEur"),
                "rankableOnlyWhenSelected": True,
                "italyAtlanteEurPerKwh": atlante.get("subscription", {}).get("energyEurPerKwh"),
                "italyChargeLeagueEurPerKwh": atlante_chargeleague.get("energyEurPerKwh"),
            }
        },
        "emspProviders": {
            "nextcharge": {
                "provider": "NextCharge",
                "billedBy": ges_nextcharge.get("billedBy") or "Go Electric Stations S.r.l.s.",
                "commercialLayer": "emsp",
                "rankable": True,
                "notCpoDirect": True,
            }
        },
        "stations": merged_stations,
        "evses": merged_evses,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    out.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))

    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"generatedAt": payload["generatedAt"], "counts": payload["counts"], "rules": payload["rules"], "subscriptions": payload["subscriptions"], "emspProviders": payload["emspProviders"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
