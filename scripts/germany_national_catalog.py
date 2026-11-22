#!/usr/bin/env python3
"""Build the staged German national non-Tesla charging catalogue.

Inputs:
- BNetzA physical-site + safe AFIR dynamic enrichment artifact.
- Current normalized AFIR static feed for optional technical/tariff evidence.

Rules:
- BNetzA is the national physical baseline.
- Tesla sites are excluded from this non-Tesla catalogue.
- Only AFIR links already marked matched_safe may enrich a BNetzA site.
- Dynamic service state is copied exactly from the validated enrichment layer.
- Missing dynamic state stays unknown.
- AFIR tariffs are preserved as raw evidence only and are NOT rankable.
- No subscription/eMSP precedence is decided here.

This output is staging-only and must not be published to TCC production paths.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def save_gz(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))


def clean_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("ß", "ss")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def is_tesla_operator(value):
    return "tesla" in clean_text(value).split()


def afir_id(site: dict):
    return f"{site.get('provider')}:{site.get('sourceSiteId')}"


def flatten_raw_tariffs(site: dict):
    out = []
    for tariff in site.get("tariffs") or []:
        out.append({"level": "site", "sourceObjectId": site.get("sourceSiteId"), **tariff})
    for station in site.get("stations") or []:
        for tariff in station.get("tariffs") or []:
            out.append({"level": "station", "sourceObjectId": station.get("sourceStationId"), **tariff})
        for point in station.get("points") or []:
            for tariff in point.get("tariffs") or []:
                out.append({"level": "point", "sourceObjectId": point.get("sourcePointId"), **tariff})
    return out


def compact_afir(site: dict):
    tariffs = flatten_raw_tariffs(site)
    return {
        "provider": site.get("provider"),
        "offerId": site.get("offerId"),
        "sourceSiteId": site.get("sourceSiteId"),
        "lastUpdated": site.get("lastUpdated"),
        "name": site.get("name"),
        "operator": site.get("operator"),
        "typeOfSite": site.get("typeOfSite"),
        "stationCount": site.get("stationCount"),
        "chargePointCount": site.get("chargePointCount"),
        "maxConnectorPowerKw": site.get("maxConnectorPowerKw"),
        "evseIds": site.get("evseIds") or [],
        "rawTariffs": tariffs,
        "hasRawTariff": bool(tariffs),
    }


def build(enrichment_path: Path, afir_path: Path, output: Path, manifest_path: Path):
    enrichment = load_gz(enrichment_path)
    afir = load_gz(afir_path)
    if enrichment.get("dataset") != "germany-bnetza-afir-dynamic-enrichment":
        raise RuntimeError(f"unexpected enrichment dataset: {enrichment.get('dataset')}")
    if afir.get("dataset") != "germany-afir-open-static-normalized":
        raise RuntimeError(f"unexpected AFIR dataset: {afir.get('dataset')}")

    afir_by_id = {afir_id(site): site for site in afir.get("sites") or []}
    status_counts = Counter()
    match_counts = Counter()
    provider_counts = Counter()
    excluded_tesla = []
    rows = []
    safe_links_missing_current_afir = 0
    raw_tariff_sites = 0

    for source in enrichment.get("sites") or []:
        operator = source.get("operator")
        if is_tesla_operator(operator):
            excluded_tesla.append({
                "bnetzaSiteId": source.get("bnetzaSiteId"),
                "operator": operator,
                "address": source.get("address"),
            })
            continue

        status = (source.get("dynamicService") or {}).get("serviceState") or "unknown"
        status_counts[status] += 1
        match_status = source.get("afirMatchStatus") or "unmatched"
        match_counts[match_status] += 1

        link = source.get("afirLink") if match_status == "matched_safe" else None
        afir_site = None
        afir_compact = None
        if link:
            linked_id = link.get("afirSiteId")
            afir_site = afir_by_id.get(linked_id)
            if afir_site is None:
                safe_links_missing_current_afir += 1
            else:
                afir_compact = compact_afir(afir_site)
                provider_counts[afir_site.get("provider") or "unknown"] += 1
                if afir_compact["hasRawTariff"]:
                    raw_tariff_sites += 1

        dyn = source.get("dynamicService") or {}
        rows.append({
            "id": source.get("bnetzaSiteId"),
            "countryCode": "DE",
            "operator": operator,
            "address": source.get("address"),
            "coordinates": source.get("coordinates"),
            "declaredChargePoints": source.get("declaredChargePoints"),
            "maxConnectionPowerKw": source.get("maxConnectionPowerKw"),
            "evseIds": source.get("evseIds") or [],
            "sourceStationIds": source.get("sourceStationIds") or [],
            "service": {
                "state": status,
                "source": "afir-dynamic" if dyn.get("knownPointCount", 0) else None,
                "knownDynamicPointCount": dyn.get("knownPointCount", 0),
                "pointStateDistribution": dyn.get("pointStateDistribution") or {},
                "providers": dyn.get("providers") or [],
                "latestObservedAt": dyn.get("latestObservedAt"),
            },
            "afir": {
                "matchStatus": match_status,
                "match": link,
                "data": afir_compact,
            },
            "pricing": {
                "rankable": False,
                "rawAfirTariffs": (afir_compact or {}).get("rawTariffs") or [],
                "directCpo": None,
                "subscriptions": [],
                "emspFallback": [],
            },
        })

    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-national-non-tesla-catalog-staging",
        "generatedAt": utc_now(),
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "nonTeslaOnly": True,
            "bnetzaIsNationalBaseline": True,
            "dynamicStatusIncludedWhereKnown": True,
            "unknownIsNeverOutOfService": True,
            "ambiguousAfirMatchesAreQuarantined": True,
            "rawAfirTariffsIncluded": True,
            "tariffsRankable": False,
            "directCpoTariffsIncluded": False,
            "subscriptionsIncluded": False,
            "emspFallbackIncluded": False,
        },
        "sources": {
            "bnetzaDynamicEnrichmentGeneratedAt": enrichment.get("generatedAt"),
            "bnetza": (enrichment.get("sources") or {}).get("bnetza"),
            "persistentDynamicGeneratedAt": (enrichment.get("sources") or {}).get("persistentDynamicGeneratedAt"),
            "afirStaticGeneratedAt": afir.get("generatedAt"),
            "afirFeeds": afir.get("feeds"),
        },
        "stats": {
            "bnetzaPhysicalSitesInput": len(enrichment.get("sites") or []),
            "teslaSitesExcluded": len(excluded_tesla),
            "nonTeslaSites": len(rows),
            "serviceStateDistribution": dict(status_counts),
            "afirMatchStatusDistribution": dict(match_counts),
            "safeAfirSitesAttached": sum(1 for row in rows if (row.get("afir") or {}).get("data")),
            "safeLinksMissingCurrentAfirSnapshot": safe_links_missing_current_afir,
            "safeAfirSitesWithRawTariff": raw_tariff_sites,
            "attachedAfirProviders": dict(provider_counts),
        },
        "sites": rows,
        "excludedTeslaSample": excluded_tesla[:100],
    }
    save_gz(output, result)

    manifest = {
        "schemaVersion": "0.1.0",
        "dataset": result["dataset"],
        "generatedAt": result["generatedAt"],
        "countryCode": "DE",
        "stagedOnly": True,
        "publishesToTcc": False,
        "catalogFile": output.name,
        "stats": result["stats"],
        "scope": result["scope"],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--enrichment", type=Path, default=Path("data/germany/bnetza_dynamic_enrichment.json.gz"))
    parser.add_argument("--afir", type=Path, default=Path("data/germany/afir_open_static_normalized.json.gz"))
    parser.add_argument("--output", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging.json.gz"))
    parser.add_argument("--manifest", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_manifest.json"))
    args = parser.parse_args()
    result = build(args.enrichment, args.afir, args.output, args.manifest)
    print("TCC_GERMANY_NATIONAL_CATALOG=" + json.dumps(result["stats"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
