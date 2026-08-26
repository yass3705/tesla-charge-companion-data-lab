#!/usr/bin/env python3
"""Classify harvested Bump direct tariffs for safe TCC integration.

This analysis is deliberately conservative: static explicit tariffs are marked rankable; tariffs
flagged by Bump as changing in time are grouped by their exact driver-facing descriptions and remain
non-rankable until their temporal rules are parsed without ambiguity.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SRC = Path("data/national/bump_direct_tariffs_graphql_france.json.gz")
OUT_JSON = Path("reports/bump/tariff_readiness_latest.json")
OUT_MD = Path("reports/bump/tariff_readiness_latest.md")


def rounded(v: Any) -> float | None:
    return round(float(v), 6) if isinstance(v, (int, float)) else None


def signature(t: dict[str, Any]) -> tuple[Any, ...]:
    return (
        rounded(t.get("energyEurPerKwh")),
        rounded(t.get("timeEurPerHour")),
        rounded(t.get("flatFeeEur")),
        rounded(t.get("minPriceEur")),
        bool(t.get("isTariffChangingInTime")),
        str(t.get("parkingText") or ""),
        str(t.get("quick") or ""),
        str(t.get("short") or ""),
        str(t.get("long") or ""),
    )


def main() -> None:
    payload = json.loads(gzip.decompress(SRC.read_bytes()))
    category_counts = Counter()
    category_stations: dict[str, set[str]] = defaultdict(set)
    variable = Counter()
    variable_examples: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    static_patterns = Counter()
    static_examples: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    unpriced_points = 0

    for station in payload.get("stations", []):
        sid = station.get("idStationItinerance") or station.get("stationKey")
        match = station.get("match") or {}
        if match.get("status") != "matched":
            category_stations["station_unmatched"].add(str(sid))
            continue
        for point in match.get("points") or []:
            t = point.get("tariff")
            if not isinstance(t, dict):
                unpriced_points += 1
                category_counts["unpriced_point"] += 1
                category_stations["unpriced_point"].add(str(sid))
                continue

            has_numeric = any(isinstance(t.get(k), (int, float)) for k in ("energyEurPerKwh", "timeEurPerHour", "flatFeeEur"))
            changing = bool(t.get("isTariffChangingInTime"))
            sig = signature(t)
            ex = {
                "stationId": sid,
                "stationName": station.get("name"),
                "powerKw": point.get("powerKw"),
                "idPdcItinerance": point.get("idPdcItinerance"),
                "tariffGroupId": point.get("tariffGroupId"),
            }

            if changing:
                cat = "variable_time_requires_rule_parse"
                variable[sig] += 1
                if len(variable_examples[sig]) < 5:
                    variable_examples[sig].append(ex)
            elif has_numeric:
                cat = "static_rankable"
                static_patterns[sig] += 1
                if len(static_examples[sig]) < 3:
                    static_examples[sig].append(ex)
            else:
                cat = "priced_object_without_numeric_component"

            category_counts[cat] += 1
            category_stations[cat].add(str(sid))

    variable_rows = []
    for sig, count in variable.most_common():
        variable_rows.append({
            "pointCount": count,
            "energyEurPerKwh": sig[0],
            "timeEurPerHour": sig[1],
            "flatFeeEur": sig[2],
            "minPriceEur": sig[3],
            "parkingText": sig[5] or None,
            "quick": sig[6] or None,
            "short": sig[7] or None,
            "long": sig[8] or None,
            "examples": variable_examples[sig],
        })

    static_rows = []
    for sig, count in static_patterns.most_common():
        static_rows.append({
            "pointCount": count,
            "energyEurPerKwh": sig[0],
            "timeEurPerHour": sig[1],
            "flatFeeEur": sig[2],
            "minPriceEur": sig[3],
            "parkingText": sig[5] or None,
            "quick": sig[6] or None,
            "short": sig[7] or None,
            "long": sig[8] or None,
            "examples": static_examples[sig],
        })

    out = {
        "schemaVersion": "1.0.0",
        "sourceGeneratedAt": payload.get("generatedAt"),
        "sourceCounts": payload.get("counts"),
        "decisionRule": {
            "staticRankable": "Bump says tariff is not changing in time and at least one numeric energy/time/flat component is explicit.",
            "variableNotYetRankable": "Bump flags tariff as changing in time; exact generated descriptions are retained for deterministic temporal parsing.",
            "ambiguousNeverPriced": True,
        },
        "pointCategoryCounts": dict(category_counts),
        "stationCategoryCounts": {k: len(v) for k, v in category_stations.items()},
        "variablePatternCount": len(variable_rows),
        "staticPatternCount": len(static_rows),
        "variablePatterns": variable_rows,
        "staticPatterns": static_rows,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Bump tariff readiness for TCC",
        "",
        f"Source generated: `{payload.get('generatedAt')}`",
        "",
        "## Point classification",
        "",
    ]
    for k, v in category_counts.most_common():
        lines.append(f"- {k}: **{v} points** / **{len(category_stations[k])} stations**")
    lines += [
        "",
        f"- Unique static tariff descriptions: **{len(static_rows)}**",
        f"- Unique time-varying tariff descriptions: **{len(variable_rows)}**",
        "",
        "## Largest time-varying patterns",
        "",
    ]
    for row in variable_rows[:25]:
        lines.append(f"### {row['pointCount']} points")
        lines.append("")
        lines.append(f"- quick: `{row.get('quick')}`")
        lines.append(f"- short: `{row.get('short')}`")
        lines.append(f"- long: `{row.get('long')}`")
        lines.append(f"- parking: `{row.get('parkingText')}`")
        lines.append("")
    lines += [
        "## Integration rule",
        "",
        "Static explicit tariffs can be promoted to a TCC candidate layer. Time-varying tariffs remain quarantined until each distinct generated rule is parsed and tested against concrete timestamps.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "pointCategoryCounts": dict(category_counts),
        "stationCategoryCounts": {k: len(v) for k, v in category_stations.items()},
        "staticPatternCount": len(static_rows),
        "variablePatternCount": len(variable_rows),
    }, indent=2))


if __name__ == "__main__":
    main()
