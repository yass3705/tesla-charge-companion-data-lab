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
    ap.add_argument("--out", default="data/consolidation/italy_v9_candidate.json.gz")
    ap.add_argument("--report", default="data/reports/italy_v9_consolidation_report.json")
    args = ap.parse_args()

    pun = load_gz(Path(args.pun))
    plenitude = load_gz(Path(args.plenitude))
    a2a = load_gz(Path(args.a2a))

    direct_by_evse = {}
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
        if e.get("rankableDirect") and e.get("directEnergyEurPerKwh") is not None:
            candidate = {
                "channel": "operator_direct",
                "operator": "A2A e-moving",
                "eurPerKwh": e.get("directEnergyEurPerKwh"),
                "occupancyFee": e.get("occupancyFeePolicy"),
                "source": "A2A public e-moving station detail",
                "rankable": True,
            }
            previous = direct_by_evse.get(evse_id)
            if previous and previous.get("operator") != candidate.get("operator"):
                blocked["cross_operator_evse_conflict"] += 1
                direct_by_evse.pop(evse_id, None)
            else:
                direct_by_evse[evse_id] = candidate
        else:
            blocked[f"a2a:{e.get('blockingReason') or 'not_rankable'}"] += 1

    merged_evses = []
    operator_counts = Counter()
    rankable_count = 0
    for e in pun.get("evses", []):
        out = dict(e)
        evse_id = str(out.get("evseId") or "")
        tariff = direct_by_evse.get(evse_id)
        out["tccV9DirectTariff"] = tariff
        out["tccV9RankableDirect"] = bool(tariff and tariff.get("rankable"))
        if out["tccV9RankableDirect"]:
            rankable_count += 1
            operator_counts[tariff.get("operator") or "UNKNOWN"] += 1
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
        merged_stations.append(out)

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "italy-v9-consolidated-candidate",
        "generatedAt": now_iso(),
        "country": "IT",
        "backbone": "GSE PUN",
        "pricingPrecedence": ["operator_direct", "emsp", "pun_fallback"],
        "rules": {
            "punIsPhysicalInventoryMaster": True,
            "operatorTariffsRequireExactOrValidatedJoin": True,
            "crossOperatorEvseConflictFailsClosed": True,
            "punTariffNotRankableUntilSemanticsValidated": True,
            "teslaHandledByDedicatedTeslaSourceAtPublishLayer": True,
        },
        "counts": {
            "punEvseCount": len(merged_evses),
            "punStationCount": len(merged_stations),
            "rankableDirectEvseCount": rankable_count,
            "rankableDirectCoveragePct": round(100 * rankable_count / len(merged_evses), 2) if merged_evses else 0.0,
            "rankableDirectByOperator": dict(sorted(operator_counts.items())),
            "blockedReasons": dict(sorted(blocked.items())),
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
    report.write_text(json.dumps({"generatedAt": payload["generatedAt"], "counts": payload["counts"], "rules": payload["rules"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
