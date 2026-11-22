#!/usr/bin/env python3
"""Attach validated Pfalzwerke direct tariff evidence to German staging catalog.

Input is the already validated direct-CPO staging catalogue (EWE Go, EnBW,
Wirelane + validated AFIR fallback). Pfalzwerke direct evidence takes precedence
on exact Pfalzwerke AG BNetzA sites. The model remains connector-class-specific
and incomplete for final-cost ranking because the CI source does not assert VAT
or blocking fees. Production pricing.rankable always remains false.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_gz(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo.json.gz"))
    ap.add_argument("--pfalzwerke", type=Path, default=Path("data/germany/pfalzwerke_direct_tariff.json"))
    ap.add_argument("--output", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo_pfalzwerke.json.gz"))
    ap.add_argument("--manifest", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo_pfalzwerke_manifest.json"))
    args = ap.parse_args()

    catalog = load_gz(args.catalog)
    pfalz = load_json(args.pfalzwerke)
    if catalog.get("dataset") != "germany-national-non-tesla-catalog-staging-direct-cpo":
        raise RuntimeError(f"unexpected input catalog dataset: {catalog.get('dataset')}")
    if pfalz.get("dataset") != "germany-pfalzwerke-direct-tariff":
        raise RuntimeError(f"unexpected Pfalzwerke dataset: {pfalz.get('dataset')}")
    if catalog.get("scope", {}).get("tariffsRankable") is not False:
        raise RuntimeError("input production-ranking guard changed")
    if pfalz.get("scope", {}).get("productionRankable") is not False:
        raise RuntimeError("Pfalzwerke production-ranking guard changed")

    ops = set(pfalz["operator"]["bnetzaExactOperators"])
    own = pfalz["directOwnNetwork"]
    tariffs = own["connectorClassTariffs"]
    if ops != {"Pfalzwerke AG"}:
        raise RuntimeError(f"unexpected Pfalzwerke exact operators: {ops}")
    if own.get("siteScalarPriceSafe") is not False:
        raise RuntimeError("Pfalzwerke site scalar unexpectedly marked safe")
    if own.get("completeCostModel") is not False:
        raise RuntimeError("Pfalzwerke complete-cost contract changed")
    if own.get("taxIncluded") is not None:
        raise RuntimeError("Pfalzwerke tax must remain unknown in reproducible artifact")
    if tariffs.get("AC", {}).get("eurPerKwh") != 0.58 or tariffs.get("DC", {}).get("eurPerKwh") != 0.79:
        raise RuntimeError("Pfalzwerke official energy prices changed")
    if own.get("blockingFee", {}).get("assumedZero") is not False:
        raise RuntimeError("Pfalzwerke blocking fee must not be assumed zero")

    applied = 0
    afir_overridden = 0
    afir_price_distribution = Counter()
    outside_exact = 0

    for site in catalog.get("sites") or []:
        pricing = site.setdefault("pricing", {})
        if pricing.get("rankable") is not False:
            raise RuntimeError(f"production ranking unexpectedly enabled: {site.get('id')}")
        if site.get("operator") not in ops:
            continue
        if pricing.get("directCpo") is not None:
            raise RuntimeError(f"Pfalzwerke site already has another direct CPO overlay: {site.get('id')}")

        prior_preferred = pricing.get("stagingPreferredTariff") or {}
        if prior_preferred.get("sourceType") == "afir":
            afir_overridden += 1
            price = prior_preferred.get("eurPerKwh")
            if price is not None:
                afir_price_distribution[round(float(price), 6)] += 1

        applied += 1
        direct = {
            "provider": "Pfalzwerke",
            "operatorExactMatch": site.get("operator"),
            "sourceDataset": pfalz["dataset"],
            "sourceUrl": (pfalz.get("source") or {}).get("url"),
            "sourceSha256": (pfalz.get("source") or {}).get("sha256"),
            "tariffModel": "connector_class",
            "accessMethod": own.get("accessMethod"),
            "currency": own.get("currency"),
            "monthlyFeeEur": own.get("monthlyFeeEur"),
            "connectorClassTariffs": tariffs,
            "taxIncluded": None,
            "taxEvidence": own.get("taxEvidence"),
            "blockingFee": own.get("blockingFee"),
            "scope": "operator-own-network",
            "requiresConnectorClass": True,
            "completeCostModel": False,
            "stagingEnergyPriceCandidate": True,
            "productionRankable": False,
        }
        pricing["directCpo"] = direct
        pricing["stagingPreferredTariff"] = {
            "sourceType": "direct_cpo",
            "provider": "Pfalzwerke",
            "selectionMode": "connector_class",
            "connectorClassTariffs": tariffs,
            "taxIncluded": None,
            "blockingFee": own.get("blockingFee"),
            "completeCostModel": False,
            "reason": "direct_cpo_energy_price_precedes_afir_but_cost_model_incomplete",
            "productionRankable": False,
        }

    for site in catalog.get("sites") or []:
        direct = (site.get("pricing") or {}).get("directCpo") or {}
        if direct.get("provider") == "Pfalzwerke" and site.get("operator") not in ops:
            outside_exact += 1

    stats = catalog.setdefault("stats", {})
    old_direct = int(stats.get("directCpoSites") or 0)
    old_overridden = int(stats.get("directCpoAfirCandidatesOverridden") or 0)
    old_fallback = int(stats.get("validatedAfirFallbackPreferredSites") or 0)
    old_no_afir = int(stats.get("directCpoSitesWithoutRankableAfirCandidate") or 0)
    providers = dict(stats.get("directCpoProviders") or {})
    if "Pfalzwerke" in providers:
        raise RuntimeError("Pfalzwerke already present in provider stats")
    providers["Pfalzwerke"] = applied

    stats["directCpoSites"] = old_direct + applied
    stats["directCpoProviders"] = providers
    stats["directCpoConnectorClassRequiredSites"] = int(stats.get("directCpoConnectorClassRequiredSites") or 0) + applied
    stats["directCpoAfirCandidatesOverridden"] = old_overridden + afir_overridden
    stats["validatedAfirFallbackPreferredSites"] = old_fallback - afir_overridden
    stats["directCpoSitesWithoutRankableAfirCandidate"] = old_no_afir + (applied - afir_overridden)
    stats["directCpoAppliedOutsideExactOperator"] = int(stats.get("directCpoAppliedOutsideExactOperator") or 0) + outside_exact
    stats["pfalzwerkeDirectSites"] = applied
    stats["pfalzwerkeAfirCandidatesOverridden"] = afir_overridden
    stats["pfalzwerkeOverriddenAfirPriceDistribution"] = [
        {"afirEurPerKwh": price, "sites": count}
        for price, count in afir_price_distribution.most_common()
    ]
    stats["pfalzwerkeCompleteCostModelSites"] = 0

    catalog["schemaVersion"] = "0.6.0"
    catalog["scope"]["pfalzwerkeDirectEnergyPricesIncluded"] = True
    catalog["scope"]["incompleteDirectCostModelsMayBePreferredEvidence"] = True
    catalog["scope"]["tariffsRankable"] = False
    catalog["scope"]["publishesToTcc"] = False
    catalog.setdefault("sources", {})["pfalzwerkeDirectTariff"] = {
        "generatedAt": pfalz.get("generatedAt"),
        "source": pfalz.get("source"),
        "ownNetwork": own,
    }

    save_gz(args.output, catalog)
    manifest = {
        "schemaVersion": catalog["schemaVersion"],
        "dataset": catalog["dataset"],
        "countryCode": "DE",
        "stagedOnly": True,
        "publishesToTcc": False,
        "productionRankingEnabled": False,
        "catalogFile": args.output.name,
        "stats": stats,
        "scope": catalog["scope"],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_GERMANY_PFALZWERKE_OVERLAY=" + json.dumps({
        "applied": applied,
        "afirOverridden": afir_overridden,
        "afirDistribution": stats["pfalzwerkeOverriddenAfirPriceDistribution"],
        "directCpoSites": stats["directCpoSites"],
        "providers": stats["directCpoProviders"],
        "connectorClassSites": stats["directCpoConnectorClassRequiredSites"],
        "afirFallbackSites": stats["validatedAfirFallbackPreferredSites"],
        "outsideExact": outside_exact,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
