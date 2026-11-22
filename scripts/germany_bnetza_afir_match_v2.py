#!/usr/bin/env python3
"""Second-pass BNetzA ↔ AFIR matcher with improved physical-site consolidation.

Changes vs v1:
- rows sharing operator + complete postal/street/house address are grouped even
  when BNetzA coordinates differ by a few metres;
- many-to-one AFIR matches are reported explicitly;
- one canonical accepted match is selected per AFIR site for QA metrics, while
  preserving all BNetzA fragments for later physical consolidation.

Still staging/QA only: no TCC publication, dynamic status, or rankable tariffs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import germany_bnetza_afir_match as base
import germany_bnetza_catalog as bnetza
import germany_bnetza_live as bnetza_live  # noqa:F401 - patches live parser
import germany_afir_static_normalize as afir


def physical_group_key_v2(row: dict):
    op = base.operator_norm(row.get("operator"))
    parts = base.addr_parts(row.get("address"))
    complete = bool(parts["postal"] and parts["street"] and parts["house"])
    c = row.get("coordinates") or {}
    lat, lon = c.get("latitude"), c.get("longitude")
    coord = ""
    if lat is not None and lon is not None:
        coord = f"{round(float(lat), 4):.4f}|{round(float(lon), 4):.4f}"
    if complete:
        raw = "addr-complete|" + "|".join(
            (op, parts["postal"], parts["city"], parts["street"], parts["house"])
        )
    elif parts["postal"] and parts["street"]:
        raw = "addr-partial|" + "|".join(
            (op, parts["postal"], parts["city"], parts["street"], parts["house"], coord)
        )
    else:
        raw = f"geo|{op}|{coord}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def choose_canonical(matches: list[dict]):
    method_rank = {"evse_exact": 3, "address_operator": 2, "geo_operator": 1}
    return max(
        matches,
        key=lambda m: (
            method_rank.get(m.get("method"), 0),
            m.get("confidence") or 0,
            m.get("operatorSimilarity") or 0,
            -(m.get("distanceM") if m.get("distanceM") is not None else 10**9),
        ),
    )


def quality_stats(match_rows: list[dict], afir_site_count: int):
    by_afir = defaultdict(list)
    for row in match_rows:
        by_afir[row["afirSiteId"]].append(row)
    duplicates = {aid: rows for aid, rows in by_afir.items() if len(rows) > 1}
    canonical = [choose_canonical(rows) for rows in by_afir.values()]
    method_counts = Counter(x["method"] for x in canonical)
    provider_counts = Counter(x["provider"] for x in canonical)
    duplicate_method_patterns = Counter(
        "+".join(sorted(x["method"] for x in rows)) for rows in duplicates.values()
    )
    exact_distances = [
        x["distanceM"] for x in canonical
        if x.get("method") == "evse_exact" and x.get("distanceM") is not None
    ]
    fallback_distances = [
        x["distanceM"] for x in canonical
        if x.get("method") != "evse_exact" and x.get("distanceM") is not None
    ]
    return {
        "uniqueAfirSitesMatched": len(by_afir),
        "afirCoveragePct": round(100 * len(by_afir) / max(1, afir_site_count), 2),
        "acceptedCanonicalMatches": len(canonical),
        "canonicalMatchesByMethod": dict(method_counts),
        "canonicalMatchesByProvider": dict(provider_counts),
        "canonicalMatchedWithTariff": sum(bool(x.get("afirHasTariff")) for x in canonical),
        "afirSitesMatchedByMultipleBnetzaGroups": len(duplicates),
        "excessManyToOneMatches": sum(len(rows) - 1 for rows in duplicates.values()),
        "maxBnetzaGroupsPerAfirSite": max((len(rows) for rows in by_afir.values()), default=0),
        "duplicateMethodPatternsTop": dict(duplicate_method_patterns.most_common(12)),
        "exactEvseDistanceOver100m": sum(x > 100 for x in exact_distances),
        "exactEvseDistanceOver500m": sum(x > 500 for x in exact_distances),
        "fallbackDistanceMaxM": round(max(fallback_distances), 1) if fallback_distances else None,
    }, canonical, duplicates


def build(output: Path):
    base.physical_group_key = physical_group_key_v2
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bresult = bnetza.build(None, root / "bnetza.json.gz", None)
        aresult = afir.build(root / "afir.json.gz")

    bsites = base.group_bnetza(bresult["stations"])
    matches, unmatched, conflicts, stats = base.match(bsites, aresult["sites"])
    quality, canonical, duplicates = quality_stats(matches, len(aresult["sites"]))
    stats.update(quality)

    result = {
        "schemaVersion": "0.2.0",
        "dataset": "germany-bnetza-afir-match-report-v2",
        "generatedAt": afir.utc_now(),
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "dynamicStatusIncluded": False,
            "tariffsRankable": False,
            "oneCanonicalMatchPerAfirSite": True,
            "note": "QA report. Canonical selection is for coverage measurement; duplicate BNetzA fragments remain reviewable.",
        },
        "sources": {"bnetza": bresult["source"], "afirFeeds": aresult["feeds"]},
        "stats": stats,
        "canonicalMatches": canonical,
        "allMatches": matches,
        "conflicts": conflicts,
        "duplicateAfirMatches": [
            {
                "afirSiteId": aid,
                "bnetzaMatches": rows,
            }
            for aid, rows in list(duplicates.items())[:2000]
        ],
        "unmatchedSample": [
            {
                "bnetzaSiteId": x["physicalSiteId"],
                "operator": x.get("operator"),
                "address": x.get("address"),
                "coordinates": x.get("coordinates"),
                "declaredChargePoints": x.get("declaredChargePoints"),
                "evseIds": x.get("evseIds"),
            }
            for x in unmatched[:1000]
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(output, "wb", compresslevel=9) as f:
        f.write(raw)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/germany/bnetza_afir_match_report_v2.json.gz"))
    args = parser.parse_args()
    result = build(args.output)
    print("TCC_GERMANY_MATCH_V2=" + json.dumps(result["stats"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
