#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DATA = Path("data/national/pun_italy_national.json.gz")
OUT = Path("data/reports/pun_italy_cpo_gap_report.json")
OUT_MD = Path("data/reports/pun_italy_cpo_gap_report.md")
TESLA_PARTY_IDS = {"TSL"}


def pct(a: int, b: int) -> float:
    return round(100.0 * a / b, 2) if b else 0.0


def main() -> None:
    payload = json.loads(gzip.decompress(DATA.read_bytes()))
    evses = payload.get("evses") or []
    stations = payload.get("stations") or []

    by_party: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "operatorNames": Counter(),
        "evseCount": 0,
        "stationIds": set(),
        "realTimeEvseCount": 0,
        "punTariffBlockEvseCount": 0,
        "numericPunTariffEvseCount": 0,
        "operationalEvseCount": 0,
    })

    for evse in evses:
        party = str(evse.get("partyId") or "UNKNOWN").strip() or "UNKNOWN"
        row = by_party[party]
        row["operatorNames"][str(evse.get("operator") or "UNKNOWN")] += 1
        row["evseCount"] += 1
        row["stationIds"].add(str(evse.get("stationId") or evse.get("evseId") or "UNKNOWN"))
        row["realTimeEvseCount"] += int(bool(evse.get("realTime")))
        row["punTariffBlockEvseCount"] += int(bool(evse.get("punTariffBlockPresent")))
        row["numericPunTariffEvseCount"] += int(bool(evse.get("punTariffNumericValuePresent")))
        row["operationalEvseCount"] += int(evse.get("operationalState") == "operational")

    parties = []
    for party, row in by_party.items():
        evse_count = row["evseCount"]
        names = row["operatorNames"].most_common()
        parties.append({
            "partyId": party,
            "primaryOperatorName": names[0][0] if names else "UNKNOWN",
            "operatorAliases": [{"name": name, "evseCount": count} for name, count in names],
            "evseCount": evse_count,
            "stationCount": len(row["stationIds"]),
            "realTimeEvseCount": row["realTimeEvseCount"],
            "realTimeCoveragePct": pct(row["realTimeEvseCount"], evse_count),
            "punTariffBlockEvseCount": row["punTariffBlockEvseCount"],
            "punTariffBlockCoveragePct": pct(row["punTariffBlockEvseCount"], evse_count),
            "numericPunTariffEvseCount": row["numericPunTariffEvseCount"],
            "numericPunTariffCoveragePct": pct(row["numericPunTariffEvseCount"], evse_count),
            "rankableDirectTariffEvseCount": 0,
            "rankableDirectTariffGapEvseCount": evse_count,
            "nonTeslaEnrichmentPriority": party not in TESLA_PARTY_IDS,
        })

    parties.sort(key=lambda x: (not x["nonTeslaEnrichmentPriority"], -x["rankableDirectTariffGapEvseCount"], x["partyId"]))
    non_tesla = [p for p in parties if p["nonTeslaEnrichmentPriority"]]
    top10_gap = sum(p["evseCount"] for p in non_tesla[:10])
    non_tesla_total = sum(p["evseCount"] for p in non_tesla)

    report = {
        "generatedAt": payload.get("generatedAt"),
        "sourceDataset": payload.get("dataset"),
        "country": "IT",
        "method": "Group PUN EVSEs by official OCPI partyId so operator aliases/rebrands are not double-counted; Tesla is excluded from non-Tesla enrichment priority.",
        "counts": {
            "evseCount": len(evses),
            "stationCount": len(stations),
            "partyIdCount": len(parties),
            "nonTeslaEvseCount": non_tesla_total,
            "top10PriorityEvseCount": top10_gap,
            "top10PriorityCoveragePctOfNonTesla": pct(top10_gap, non_tesla_total),
        },
        "priority": non_tesla,
        "allParties": parties,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Italy PUN CPO tariff gap analysis",
        "",
        f"- Non-Tesla EVSE: **{non_tesla_total:,}**",
        f"- Top 10 CPO partyIds cover **{top10_gap:,} EVSE ({pct(top10_gap, non_tesla_total):.2f}%)** of the non-Tesla inventory.",
        "- Priority is based on official `partyId`, not display name, to merge aliases/rebrands correctly.",
        "",
        "| Rank | partyId | Main name | EVSE | Stations | Numeric PUN tariff | Real-time |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for i, row in enumerate(non_tesla[:25], 1):
        lines.append(
            f"| {i} | {row['partyId']} | {row['primaryOperatorName']} | {row['evseCount']:,} | {row['stationCount']:,} | "
            f"{row['numericPunTariffEvseCount']:,} ({row['numericPunTariffCoveragePct']:.2f}%) | {row['realTimeCoveragePct']:.2f}% |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(non_tesla[:15], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
