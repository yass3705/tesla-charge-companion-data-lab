#!/usr/bin/env python3
"""Stage BNetzA physical sites enriched with persistent AFIR service state.

Safety rules:
- BNetzA remains the national physical-site baseline.
- AFIR links are accepted only when the V2 matcher yields a non-ambiguous AFIR site.
- Ambiguous many-to-one AFIR matches are quarantined and never used for status.
- Missing dynamic state remains unknown; it is never interpreted as a failure.
- Busy states were already normalized upstream as operational.
- Site aggregation: any operational point => operational; all known mapped points
  out_of_service => out_of_service; otherwise => unknown.

This artifact is staging/QA only and does not publish to TCC.
"""
from __future__ import annotations

import argparse
import gzip
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import germany_afir_static_normalize as afir
import germany_bnetza_afir_match as base
import germany_bnetza_afir_match_v2 as match_v2
import germany_bnetza_catalog as bnetza
import germany_bnetza_live as bnetza_live  # noqa:F401 - patches live parser


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def save_gz(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))


def aggregate_service_state(rows: list[dict]):
    states = Counter((row.get("serviceState") or "unknown") for row in rows)
    if states["operational"]:
        service_state = "operational"
    elif states["out_of_service"] and not states["unknown"]:
        service_state = "out_of_service"
    else:
        service_state = "unknown"
    return service_state, dict(states)


def build(dynamic_path: Path, output: Path):
    dynamic = load_gz(dynamic_path)
    if dynamic.get("dataset") != "germany-afir-dynamic-persistent-state":
        raise RuntimeError(f"unexpected dynamic dataset: {dynamic.get('dataset')}")

    # Rebuild the two current static sources in the same run so every join is
    # measured against one coherent snapshot.
    base.physical_group_key = match_v2.physical_group_key_v2
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bresult = bnetza.build(None, root / "bnetza.json.gz", None)
        aresult = afir.build(root / "afir.json.gz")

    bsites = base.group_bnetza(bresult["stations"])
    matches, unmatched, conflicts, match_stats = base.match(bsites, aresult["sites"])
    quality, canonical, duplicates = match_v2.quality_stats(matches, len(aresult["sites"]))
    match_stats.update(quality)

    ambiguous_afir_ids = set(duplicates)
    safe_matches = [row for row in canonical if row["afirSiteId"] not in ambiguous_afir_ids]
    safe_by_afir = {row["afirSiteId"]: row for row in safe_matches}
    safe_by_bnetza = {row["bnetzaSiteId"]: row for row in safe_matches}

    ambiguous_bnetza_ids = {
        row["bnetzaSiteId"]
        for aid, rows in duplicates.items()
        for row in rows
    }

    dynamic_by_bnetza = defaultdict(list)
    provider_stats = defaultdict(lambda: {
        "knownDynamicPoints": 0,
        "mappedDynamicPoints": 0,
        "skippedAmbiguousPoints": 0,
        "pointsWithoutSafeBnetzaMatch": 0,
    })
    skipped_ambiguous = 0
    no_safe_match = 0

    for point in dynamic.get("points") or []:
        provider = point.get("provider") or "unknown"
        provider_stats[provider]["knownDynamicPoints"] += 1
        static_site_id = point.get("staticSiteId")
        if not static_site_id:
            no_safe_match += 1
            provider_stats[provider]["pointsWithoutSafeBnetzaMatch"] += 1
            continue
        afir_id = f"{provider}:{static_site_id}"
        if afir_id in ambiguous_afir_ids:
            skipped_ambiguous += 1
            provider_stats[provider]["skippedAmbiguousPoints"] += 1
            continue
        match = safe_by_afir.get(afir_id)
        if not match:
            no_safe_match += 1
            provider_stats[provider]["pointsWithoutSafeBnetzaMatch"] += 1
            continue
        dynamic_by_bnetza[match["bnetzaSiteId"]].append(point)
        provider_stats[provider]["mappedDynamicPoints"] += 1

    site_rows = []
    national_states = Counter()
    enriched_states = Counter()
    mapped_sites_by_provider = Counter()

    for site in bsites:
        bid = site["physicalSiteId"]
        safe_match = safe_by_bnetza.get(bid)
        dyn_rows = dynamic_by_bnetza.get(bid, [])
        service_state, point_states = aggregate_service_state(dyn_rows) if dyn_rows else ("unknown", {})
        national_states[service_state] += 1
        if dyn_rows:
            enriched_states[service_state] += 1
            for provider in {row.get("provider") for row in dyn_rows if row.get("provider")}:
                mapped_sites_by_provider[provider] += 1

        if safe_match:
            afir_match_status = "matched_safe"
            afir_link = {
                "afirSiteId": safe_match.get("afirSiteId"),
                "provider": safe_match.get("provider"),
                "method": safe_match.get("method"),
                "confidence": safe_match.get("confidence"),
                "distanceM": safe_match.get("distanceM"),
                "operatorSimilarity": safe_match.get("operatorSimilarity"),
            }
        elif bid in ambiguous_bnetza_ids:
            afir_match_status = "quarantined_ambiguous"
            afir_link = None
        else:
            afir_match_status = "unmatched"
            afir_link = None

        site_rows.append({
            "bnetzaSiteId": bid,
            "operator": site.get("operator"),
            "address": site.get("address"),
            "coordinates": site.get("coordinates"),
            "declaredChargePoints": site.get("declaredChargePoints"),
            "maxConnectionPowerKw": site.get("maxConnectionPowerKw"),
            "evseIds": site.get("evseIds") or [],
            "sourceStationIds": site.get("sourceStationIds") or [],
            "afirMatchStatus": afir_match_status,
            "afirLink": afir_link,
            "dynamicService": {
                "serviceState": service_state,
                "knownPointCount": len(dyn_rows),
                "pointStateDistribution": point_states,
                "providers": sorted({row.get("provider") for row in dyn_rows if row.get("provider")}),
                "sourcePointIds": sorted({row.get("sourcePointId") for row in dyn_rows if row.get("sourcePointId")}),
                "latestObservedAt": max(
                    [row.get("stateLastObservedAt") for row in dyn_rows if row.get("stateLastObservedAt")],
                    default=None,
                ),
            },
        })

    provider_report = {}
    for provider, stats in provider_stats.items():
        provider_report[provider] = {
            **stats,
            "mappedBnetzaSites": mapped_sites_by_provider.get(provider, 0),
        }

    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-bnetza-afir-dynamic-enrichment",
        "generatedAt": afir.utc_now(),
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "tariffsRankable": False,
            "bnetzaIsNationalBaseline": True,
            "dynamicStatusIncluded": True,
            "unknownIsNeverOutOfService": True,
            "ambiguousAfirMatchesAreQuarantined": True,
            "siteAggregation": "operational if any known point operational; out_of_service only if all known mapped points are out_of_service; otherwise unknown",
        },
        "sources": {
            "bnetza": bresult.get("source"),
            "afirFeeds": aresult.get("feeds"),
            "persistentDynamicGeneratedAt": dynamic.get("generatedAt"),
            "persistentDynamicProviderStats": dynamic.get("providerStats"),
        },
        "stats": {
            "bnetzaPhysicalSites": len(bsites),
            "afirSites": len(aresult["sites"]),
            "rawMatchedBnetzaPhysicalSites": match_stats.get("matchedPhysicalSites"),
            "canonicalAfirMatches": len(canonical),
            "safeCanonicalAfirMatches": len(safe_matches),
            "ambiguousAfirSitesQuarantined": len(ambiguous_afir_ids),
            "ambiguousBnetzaSitesQuarantined": len(ambiguous_bnetza_ids),
            "matcherConflicts": len(conflicts),
            "persistentDynamicPoints": len(dynamic.get("points") or []),
            "dynamicPointsMappedToSafeBnetza": sum(len(rows) for rows in dynamic_by_bnetza.values()),
            "dynamicPointsSkippedAmbiguous": skipped_ambiguous,
            "dynamicPointsWithoutSafeBnetzaMatch": no_safe_match,
            "bnetzaSitesWithActionableDynamicState": len(dynamic_by_bnetza),
            "nationalServiceStateDistribution": dict(national_states),
            "enrichedSiteServiceStateDistribution": dict(enriched_states),
            "providerCoverage": provider_report,
            "matchV2": match_stats,
        },
        "sites": site_rows,
    }
    save_gz(output, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dynamic",
        type=Path,
        default=Path("data/germany/afir_dynamic_state.json.gz"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/germany/bnetza_dynamic_enrichment.json.gz"),
    )
    args = parser.parse_args()
    result = build(args.dynamic, args.output)
    print("TCC_GERMANY_BNETZA_DYNAMIC_ENRICHMENT=" + json.dumps(result["stats"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
