#!/usr/bin/env python3
"""Overlay deer GmbH's validated official ad-hoc tariff onto Germany staging.

This is deliberately a narrow post-processing step over the existing direct-CPO
staging overlay. It applies only when the BNetzA operator name matches the exact
operator scope published by the deer tariff extractor. No tariff is inferred for
other operators or roaming partners.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


def load_gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_gz(path: Path, data: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--catalog",
        type=Path,
        default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo.json.gz"),
    )
    ap.add_argument(
        "--deer",
        type=Path,
        default=Path("data/germany/deer_direct_tariff.json"),
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo_manifest.json"),
    )
    args = ap.parse_args()

    catalog = load_gz(args.catalog)
    deer = load_json(args.deer)
    manifest = load_json(args.manifest)

    if catalog.get("dataset") != "germany-national-non-tesla-catalog-staging-direct-cpo":
        raise RuntimeError("unexpected direct-CPO catalog dataset")
    if deer.get("dataset") != "germany-deer-direct-tariff":
        raise RuntimeError("unexpected deer tariff dataset")
    if deer.get("scope", {}).get("siteScalarPriceSafe") is not True:
        raise RuntimeError("deer scalar safety contract changed")
    if deer.get("scope", {}).get("operatorOwnNetworkOnly") is not True:
        raise RuntimeError("deer operator scope contract changed")

    deer_ops = set(deer["operator"]["bnetzaExactOperators"])
    if not deer_ops:
        raise RuntimeError("deer exact operator set is empty")
    own = deer["directOwnNetwork"]
    if own.get("rankableCandidate") is not True:
        raise RuntimeError("deer tariff is not eligible for staging")
    if own.get("blockingFee") is None:
        raise RuntimeError("deer blocking-fee evidence unexpectedly missing")

    deer_sites = 0
    afir_overridden = 0
    direct_without_afir = 0

    for site in catalog.get("sites") or []:
        if site.get("operator") not in deer_ops:
            continue

        pricing = site.setdefault("pricing", {})
        existing = pricing.get("directCpo")
        if existing and existing.get("provider") != "deer":
            raise RuntimeError(
                f"conflicting direct-CPO overlay for deer site {site.get('id')}: {existing.get('provider')}"
            )

        afir_candidate = bool(
            pricing.get("stagingRankableCandidate")
            and pricing.get("stagingEffectiveEurPerKwh") is not None
        )

        pricing["directCpo"] = {
            "provider": "deer",
            "operatorExactMatch": site.get("operator"),
            "sourceDataset": deer["dataset"],
            "sourceUrl": deer["source"]["url"],
            "sourceSha256": deer["source"]["sha256"],
            "tariffModel": "site_scalar_with_blocking_fee",
            "currency": own["currency"],
            "eurPerKwh": own["eurPerKwh"],
            "blockingFee": own["blockingFee"],
            "acDcSamePrice": own["acDcSamePrice"],
            "accessMethod": own["accessMethod"],
            "registrationRequired": own["registrationRequired"],
            "scope": "operator-own-network-ad-hoc",
            "stagingRankableCandidate": True,
            "requiresConnectorClass": False,
            "requiresEvseSelection": False,
        }
        pricing["stagingPreferredTariff"] = {
            "sourceType": "direct_cpo",
            "provider": "deer",
            "selectionMode": "site_scalar",
            "currency": own["currency"],
            "eurPerKwh": own["eurPerKwh"],
            "blockingFee": own["blockingFee"],
            "reason": "direct_cpo_precedes_afir_exact_operator_scope",
            "productionRankable": False,
        }

        deer_sites += 1
        if afir_candidate:
            afir_overridden += 1
            pricing["directVsAfir"] = {
                "afirEurPerKwh": pricing["stagingEffectiveEurPerKwh"],
                "directEurPerKwh": own["eurPerKwh"],
                "afirMinusDirectEurPerKwh": round(
                    float(pricing["stagingEffectiveEurPerKwh"]) - float(own["eurPerKwh"]), 6
                ),
                "preferred": "direct_cpo",
            }
        else:
            direct_without_afir += 1

    if deer_sites == 0:
        raise RuntimeError("no exact deer GmbH site found in national catalog")

    catalog["schemaVersion"] = "0.6.0"
    catalog.setdefault("scope", {}).update(
        {
            "directCpoTariffsIncluded": True,
            "directCpoPrecedesAfirInStaging": True,
            "timeCappedBlockingFeesSupported": True,
            "tariffsRankable": False,
            "publishesToTcc": False,
        }
    )
    stats = catalog.setdefault("stats", {})
    providers = dict(stats.get("directCpoProviders") or {})
    providers["deer"] = deer_sites
    stats["directCpoProviders"] = providers
    stats["directCpoSites"] = int(stats.get("directCpoSites") or 0) + deer_sites
    stats["directCpoSiteScalarSites"] = int(stats.get("directCpoSiteScalarSites") or 0) + deer_sites
    stats["directCpoAfirCandidatesOverridden"] = int(
        stats.get("directCpoAfirCandidatesOverridden") or 0
    ) + afir_overridden
    stats["validatedAfirFallbackPreferredSites"] = int(
        stats.get("validatedAfirFallbackPreferredSites") or 0
    ) - afir_overridden
    stats["directCpoSitesWithoutRankableAfirCandidate"] = int(
        stats.get("directCpoSitesWithoutRankableAfirCandidate") or 0
    ) + direct_without_afir
    stats["deerDirectSites"] = deer_sites
    stats["deerAfirCandidatesOverridden"] = afir_overridden

    catalog.setdefault("sources", {})["deerDirectTariff"] = {
        "generatedAt": deer.get("generatedAt"),
        "source": deer.get("source"),
        "ownNetwork": own,
        "exactOperators": sorted(deer_ops),
    }

    manifest["schemaVersion"] = "0.6.0"
    manifest["stats"] = stats
    manifest["scope"] = catalog["scope"]

    save_gz(args.catalog, catalog)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        "TCC_GERMANY_DEER_DIRECT_OVERLAY="
        + json.dumps(
            {
                "deerSites": deer_sites,
                "afirCandidatesOverridden": afir_overridden,
                "directWithoutAfir": direct_without_afir,
                "eurPerKwh": own["eurPerKwh"],
                "blockingFee": own["blockingFee"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
