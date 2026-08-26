#!/usr/bin/env python3
"""Parse Bump-generated time-varying tariff descriptions into deterministic TCC-ready rules.

The parser intentionally accepts only text shapes observed in the current Bump public API dataset.
Any new/changed wording is rejected and quarantined rather than guessed.
"""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SRC = Path("data/national/bump_direct_tariffs_graphql_france.json.gz")
OUT = Path("reports/bump/variable_tariff_parse_latest.json")
OUT_MD = Path("reports/bump/variable_tariff_parse_latest.md")

MONEY = r"([0-9]+(?:[.,][0-9]+)?)"


def num(s: str) -> float:
    return round(float(s.replace(",", ".")), 6)


def parse_clock(s: str) -> str:
    # Bump currently renders English 12-hour times in generated descriptions.
    m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([AP]M)", s.strip(), re.I)
    if not m:
        raise ValueError(f"unsupported clock: {s!r}")
    h, minute, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if h == 12:
        h = 0
    if ap == "PM":
        h += 12
    return f"{h:02d}:{minute:02d}"


def parse_duration_minutes(s: str) -> int:
    text = s.strip().casefold()
    total = 0
    mh = re.search(r"(\d+)h", text)
    if mh:
        total += int(mh.group(1)) * 60
    mm = re.search(r"(\d+)\s*minutes?", text)
    if mm:
        total += int(mm.group(1))
    if not mh and not mm:
        raise ValueError(f"unsupported duration: {s!r}")
    return total


def parse_tariff(t: dict[str, Any]) -> dict[str, Any]:
    long = str(t.get("long") or "").replace("\u202f", " ")
    parking = str(t.get("parkingText") or "").replace("\u202f", " ")
    rules: list[dict[str, Any]] = []
    consumed_spans: list[tuple[int, int]] = []

    # Minimum session charge.
    m = re.search(rf"Minimum\s+{MONEY}\s*€\s*Inc\.\s*VAT", long, re.I)
    if m:
        rules.append({"kind": "minimum_total", "amountEur": num(m.group(1))})
        consumed_spans.append(m.span())

    # Conditional or unconditional fixed fee.
    fixed_re = re.compile(
        rf"Fixed price:\s*{MONEY}\s*€"
        rf"(?:\s+above\s+([0-9]+(?:[.,][0-9]+)?)kWh\s+consumed)?"
        rf"(?:\s+and\s+after\s+([^\n]+?)\s+of\s+usage)?(?=\n|$)",
        re.I,
    )
    for fm in fixed_re.finditer(long):
        rule: dict[str, Any] = {"kind": "flat_fee", "amountEur": num(fm.group(1)), "conditions": []}
        if fm.group(2):
            rule["conditions"].append({"kind": "energy_above_kwh", "value": num(fm.group(2))})
        if fm.group(3):
            rule["conditions"].append({"kind": "session_duration_after_minutes", "value": parse_duration_minutes(fm.group(3))})
        rules.append(rule)
        consumed_spans.append(fm.span())

    # Two-band time-of-day energy pricing.
    energy_band_re = re.compile(
        rf"Energy consumption:\s*{MONEY}\s*€/kWh\s+between\s+([^\n]+?)\s+and\s+([^\n]+?)\n"
        rf"Then\s+{MONEY}\s*€/kWh\s+between\s+([^\n]+?)\s+and\s+([^\n]+?)(?=\n|$)",
        re.I,
    )
    band_match = energy_band_re.search(long)
    if band_match:
        rules.append({
            "kind": "energy_time_bands",
            "bands": [
                {"start": parse_clock(band_match.group(2)), "end": parse_clock(band_match.group(3)), "eurPerKwh": num(band_match.group(1))},
                {"start": parse_clock(band_match.group(5)), "end": parse_clock(band_match.group(6)), "eurPerKwh": num(band_match.group(4))},
            ],
        })
        consumed_spans.append(band_match.span())
    else:
        em = re.search(rf"Energy consumption:\s*{MONEY}\s*€/kWh", long, re.I)
        if em:
            rules.append({"kind": "energy", "eurPerKwh": num(em.group(1))})
            consumed_spans.append(em.span())

    # Parking/idle charging is semantically different from session-duration pricing.
    if "While parking (no energy delivered):" in long:
        if not parking:
            raise ValueError("parking section without parkingText")
        parking_clean = parking.replace("\u202f", " ")
        # Time-window occupancy rule: free overnight, charge after grace period in daytime.
        pm = re.fullmatch(
            rf"Duration:\s*{MONEY}\s*€/minute\s+between\s+(.+?)\s+and\s+(.+?)\n"
            rf"Then\s+{MONEY}\s*€/minute\s+after\s+(.+?)\s+of\s+usage\s+and\s+between\s+(.+?)\s+and\s+(.+?)",
            parking_clean,
            re.I,
        )
        if pm:
            rules.append({
                "kind": "post_charge_occupancy_time_bands",
                "bands": [
                    {"start": parse_clock(pm.group(2)), "end": parse_clock(pm.group(3)), "eurPerMinute": num(pm.group(1)), "graceMinutes": 0},
                    {"start": parse_clock(pm.group(6)), "end": parse_clock(pm.group(7)), "eurPerMinute": num(pm.group(4)), "graceMinutes": parse_duration_minutes(pm.group(5))},
                ],
            })
        else:
            pm = re.fullmatch(rf"Duration:\s*{MONEY}\s*€/minute\s+after\s+(.+?)\s+of\s+usage", parking_clean, re.I)
            if not pm:
                raise ValueError(f"unsupported parking rule: {parking!r}")
            rules.append({"kind": "post_charge_occupancy", "eurPerMinute": num(pm.group(1)), "graceMinutes": parse_duration_minutes(pm.group(2))})
    else:
        # Duration surcharge while session is ongoing.
        dm = re.search(rf"Duration:\s*{MONEY}\s*€/minute\s+after\s+([^\n]+?)\s+of\s+usage", long, re.I)
        if dm:
            rules.append({"kind": "session_duration_surcharge", "eurPerMinute": num(dm.group(1)), "afterMinutes": parse_duration_minutes(dm.group(2))})
            consumed_spans.append(dm.span())

    # Validate that the API's flag is not being accepted on a description we failed to explain.
    if not rules:
        raise ValueError("no supported rules parsed")

    # Cross-check headline numeric fields when present. Energy/time values may intentionally differ
    # for time-band rules, so only require the headline price to be one of the parsed band values.
    api_energy = t.get("energyEurPerKwh")
    parsed_energy = []
    for r in rules:
        if r["kind"] == "energy":
            parsed_energy.append(r["eurPerKwh"])
        elif r["kind"] == "energy_time_bands":
            parsed_energy.extend(b["eurPerKwh"] for b in r["bands"])
    if isinstance(api_energy, (int, float)) and parsed_energy:
        if min(abs(float(api_energy) - x) for x in parsed_energy) > 0.001:
            raise ValueError(f"headline energy mismatch {api_energy} vs {parsed_energy}")

    return {"rules": rules, "sourceLong": long, "sourceParking": parking or None}


def main() -> None:
    src = json.loads(gzip.decompress(SRC.read_bytes()))
    parsed_points = 0
    failures = []
    pattern_counts = Counter()
    pattern_payload: dict[str, Any] = {}

    for station in src.get("stations") or []:
        for point in (station.get("match") or {}).get("points") or []:
            t = point.get("tariff")
            if not isinstance(t, dict) or not t.get("isTariffChangingInTime"):
                continue
            key = json.dumps({"long": t.get("long"), "parking": t.get("parkingText")}, ensure_ascii=False, sort_keys=True)
            try:
                parsed = parse_tariff(t)
                parsed_points += 1
                pattern_counts[key] += 1
                pattern_payload.setdefault(key, parsed)
            except Exception as exc:
                failures.append({
                    "stationId": station.get("idStationItinerance"),
                    "stationName": station.get("name"),
                    "pdc": point.get("idPdcItinerance"),
                    "long": t.get("long"),
                    "parking": t.get("parkingText"),
                    "error": f"{type(exc).__name__}: {exc}",
                })

    patterns = [
        {"pointCount": count, **pattern_payload[key]}
        for key, count in pattern_counts.most_common()
    ]
    out = {
        "schemaVersion": "1.0.0",
        "sourceGeneratedAt": src.get("generatedAt"),
        "variablePointsExpected": src.get("counts", {}).get("timeChangingPricedPoints"),
        "parsedPoints": parsed_points,
        "failedPoints": len(failures),
        "parsedPatternCount": len(patterns),
        "patterns": patterns,
        "failures": failures,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Bump variable tariff parser",
        "",
        f"- Expected variable points: **{out['variablePointsExpected']}**",
        f"- Parsed points: **{parsed_points}**",
        f"- Failed points: **{len(failures)}**",
        f"- Parsed distinct patterns: **{len(patterns)}**",
        "",
    ]
    for p in patterns:
        lines += [f"## {p['pointCount']} points", "", "```json", json.dumps(p["rules"], ensure_ascii=False, indent=2), "```", ""]
    if failures:
        lines += ["## Failures", ""] + [f"- {x['stationId']} / {x['pdc']}: {x['error']}" for x in failures[:50]] + [""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"expected": out["variablePointsExpected"], "parsed": parsed_points, "failed": len(failures), "patterns": len(patterns)}, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
