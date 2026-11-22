#!/usr/bin/env python3
"""Attach validated AFIR tariff classifications to the staged German catalogue.

Production ranking remains disabled. Sites that pass the conservative AFIR
classifier are marked as staging candidates only.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


def load_gz(path: Path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        return json.load(f)


def save_gz(path: Path,data: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt",encoding="utf-8",compresslevel=9) as f:
        json.dump(data,f,ensure_ascii=False,separators=(",",":"))


def key(provider,site_id):
    return f"{provider}:{site_id}"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog",type=Path,default=Path("data/germany/germany_non_tesla_catalog_staging.json.gz"))
    ap.add_argument("--classification",type=Path,default=Path("data/germany/afir_tariff_classification.json.gz"))
    ap.add_argument("--output",type=Path,default=Path("data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz"))
    ap.add_argument("--manifest",type=Path,default=Path("data/germany/germany_non_tesla_catalog_staging_tariff_classified_manifest.json"))
    args=ap.parse_args()

    catalog=load_gz(args.catalog)
    cls=load_gz(args.classification)
    if catalog.get("dataset")!="germany-national-non-tesla-catalog-staging":
        raise RuntimeError("unexpected catalog dataset")
    if cls.get("dataset")!="germany-afir-tariff-classification":
        raise RuntimeError("unexpected classification dataset")

    by_key={key(s.get("provider"),s.get("sourceSiteId")):s for s in cls.get("sites") or []}
    class_counts=Counter(); provider_candidates=Counter(); candidate_prices=Counter()
    attached=0; missing=0; candidates=0

    for site in catalog.get("sites") or []:
        pricing=site.setdefault("pricing",{})
        pricing["rankable"]=False  # hard production gate remains closed
        pricing["stagingRankableCandidate"]=False
        pricing["stagingEffectiveEurPerKwh"]=None
        pricing["afirClassification"]=None

        afir=(site.get("afir") or {}).get("data")
        if not afir:
            continue
        c=by_key.get(key(afir.get("provider"),afir.get("sourceSiteId")))
        if c is None:
            missing += 1
            continue
        attached += 1
        class_counts[c.get("classification") or "unknown"] += 1
        pricing["afirClassification"]={
            "provider":c.get("provider"),
            "classification":c.get("classification"),
            "pricedRateCount":c.get("pricedRateCount"),
            "rateClassDistribution":c.get("rateClassDistribution") or {},
            "distinctSimpleKwhValues":c.get("distinctSimpleKwhValues") or [],
            "source":"mobilithek-afir-static",
        }
        if c.get("rankable"):
            # Candidate only: production rankable remains false until later gate.
            pricing["stagingRankableCandidate"]=True
            pricing["stagingEffectiveEurPerKwh"]=c.get("effectiveEurPerKwh")
            candidates += 1
            provider_candidates[c.get("provider") or "unknown"] += 1
            candidate_prices[round(float(c.get("effectiveEurPerKwh")),6)] += 1

    catalog["schemaVersion"]="0.2.0"
    catalog["dataset"]="germany-national-non-tesla-catalog-staging-tariff-classified"
    catalog["scope"]["tariffsRankable"]=False
    catalog["scope"]["safeAfirTariffCandidatesIncluded"]=True
    catalog["scope"]["safeAfirTariffCandidatesPublishToTcc"]=False
    catalog["scope"]["rankabilityRule"]=cls.get("scope",{}).get("rankabilityRule")
    catalog["stats"]["afirTariffClassificationAttachedSites"]=attached
    catalog["stats"]["afirTariffClassificationMissingForAttachedSite"]=missing
    catalog["stats"]["stagingRankableAfirCandidateSites"]=candidates
    catalog["stats"]["stagingRankableAfirCandidatesByProvider"]=dict(provider_candidates)
    catalog["stats"]["attachedAfirTariffClassificationDistribution"]=dict(class_counts)
    catalog["stats"]["topStagingCandidateEurPerKwh"]=[{"eurPerKwh":p,"sites":n} for p,n in candidate_prices.most_common(30)]
    catalog.setdefault("sources",{})["afirTariffClassificationProviderStats"]=cls.get("providerStats")

    save_gz(args.output,catalog)
    manifest={
        "schemaVersion":"0.2.0",
        "dataset":catalog["dataset"],
        "countryCode":"DE",
        "stagedOnly":True,
        "publishesToTcc":False,
        "productionRankingEnabled":False,
        "catalogFile":args.output.name,
        "stats":catalog["stats"],
        "scope":catalog["scope"],
    }
    args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TCC_GERMANY_TARIFF_OVERLAY="+json.dumps({
        "attached":attached,"missing":missing,"candidates":candidates,
        "providers":dict(provider_candidates),"classifications":dict(class_counts),
        "topPrices":manifest["stats"]["topStagingCandidateEurPerKwh"][:15]
    },sort_keys=True))

if __name__=="__main__": main()
