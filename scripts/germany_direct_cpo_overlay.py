#!/usr/bin/env python3
"""Apply validated direct-CPO tariff evidence to the staged German catalog.

Current direct source: EWE Go own network. Direct CPO evidence takes precedence
only in the staging preferred-tariff view. Production pricing.rankable remains
false until the full precedence/QA gate is explicitly opened.
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
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz"))
    ap.add_argument("--ewe", type=Path, default=Path("data/germany/ewe_go_direct_tariff.json"))
    ap.add_argument("--output", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo.json.gz"))
    ap.add_argument("--manifest", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo_manifest.json"))
    args=ap.parse_args()

    catalog=load_gz(args.catalog)
    ewe=load_json(args.ewe)
    if catalog.get("dataset") != "germany-national-non-tesla-catalog-staging-tariff-classified":
        raise RuntimeError(f"unexpected catalog dataset: {catalog.get('dataset')}")
    if ewe.get("dataset") != "germany-ewe-go-direct-tariff":
        raise RuntimeError(f"unexpected EWE dataset: {ewe.get('dataset')}")

    exact_ops=set(ewe.get("operator",{}).get("bnetzaExactOperators") or [])
    own=ewe.get("directOwnNetwork") or {}
    if not exact_ops or own.get("rankableCandidate") is not True:
        raise RuntimeError("EWE direct tariff not eligible for staging overlay")

    direct_applied=0
    afir_candidates_overridden=0
    direct_only=0
    afir_deltas=Counter()
    afir_price_pairs=Counter()
    non_ewe_direct=0

    for site in catalog.get("sites") or []:
        pricing=site.setdefault("pricing", {})
        pricing["rankable"] = False
        pricing["stagingPreferredTariff"] = None
        pricing["directCpo"] = None

        if site.get("operator") not in exact_ops:
            continue

        direct_applied += 1
        direct={
            "provider":"EWE Go",
            "operatorExactMatch":site.get("operator"),
            "sourceDataset":ewe.get("dataset"),
            "sourceUrl":(ewe.get("source") or {}).get("url"),
            "sourceSha256":(ewe.get("source") or {}).get("sha256"),
            "currency":own.get("currency"),
            "eurPerKwh":own.get("eurPerKwh"),
            "taxIncluded":own.get("taxIncluded"),
            "monthlyFeeEur":own.get("monthlyFeeEur"),
            "blockingFee":own.get("blockingFee"),
            "acDcSamePrice":own.get("acDcSamePrice"),
            "scope":"operator-own-network",
            "stagingRankableCandidate":True,
        }
        pricing["directCpo"] = direct
        pricing["stagingPreferredTariff"]={
            "sourceType":"direct_cpo",
            "provider":"EWE Go",
            "currency":"EUR",
            "eurPerKwh":own.get("eurPerKwh"),
            "taxIncluded":True,
            "reason":"direct_cpo_precedes_afir",
            "productionRankable":False,
        }

        afir_candidate=bool(pricing.get("stagingRankableCandidate"))
        afir_price=pricing.get("stagingEffectiveEurPerKwh")
        if afir_candidate and afir_price is not None:
            afir_candidates_overridden += 1
            delta=round(float(afir_price)-float(own.get("eurPerKwh")),6)
            afir_deltas[delta]+=1
            afir_price_pairs[(round(float(afir_price),6),round(float(own.get("eurPerKwh")),6))]+=1
            pricing["directVsAfir"]={
                "afirEurPerKwh":afir_price,
                "directEurPerKwh":own.get("eurPerKwh"),
                "afirMinusDirectEurPerKwh":delta,
                "preferred":"direct_cpo",
            }
        else:
            direct_only += 1

    # Strong contamination guard.
    for site in catalog.get("sites") or []:
        if (site.get("pricing") or {}).get("directCpo") and site.get("operator") not in exact_ops:
            non_ewe_direct += 1

    catalog["schemaVersion"]="0.3.0"
    catalog["dataset"]="germany-national-non-tesla-catalog-staging-direct-cpo"
    catalog["scope"]["directCpoTariffsIncluded"] = True
    catalog["scope"]["directCpoPrecedesAfirInStaging"] = True
    catalog["scope"]["tariffsRankable"] = False
    catalog["scope"]["publishesToTcc"] = False
    catalog["stats"]["directCpoSites"] = direct_applied
    catalog["stats"]["directCpoProviders"] = {"EWE Go": direct_applied}
    catalog["stats"]["directCpoAfirCandidatesOverridden"] = afir_candidates_overridden
    catalog["stats"]["directCpoSitesWithoutRankableAfirCandidate"] = direct_only
    catalog["stats"]["directCpoAppliedOutsideExactOperator"] = non_ewe_direct
    catalog["stats"]["eweGoDirectVsAfirDeltaDistribution"]=[
        {"afirMinusDirectEurPerKwh":d,"sites":n} for d,n in afir_deltas.most_common()
    ]
    catalog["stats"]["eweGoAfirDirectPricePairs"]=[
        {"afirEurPerKwh":pair[0],"directEurPerKwh":pair[1],"sites":n}
        for pair,n in afir_price_pairs.most_common()
    ]
    catalog.setdefault("sources",{})["eweGoDirectTariff"]={
        "generatedAt":ewe.get("generatedAt"),"source":ewe.get("source"),
        "ownNetwork":own,"roamingPartnerStoredNotApplied":ewe.get("roamingPartner")
    }

    save_gz(args.output,catalog)
    manifest={
        "schemaVersion":"0.3.0","dataset":catalog["dataset"],"countryCode":"DE",
        "stagedOnly":True,"publishesToTcc":False,"productionRankingEnabled":False,
        "catalogFile":args.output.name,"stats":catalog["stats"],"scope":catalog["scope"]
    }
    args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TCC_GERMANY_DIRECT_CPO_OVERLAY="+json.dumps({
        "directCpoSites":direct_applied,"afirCandidatesOverridden":afir_candidates_overridden,
        "directOnly":direct_only,"outsideExactOperator":non_ewe_direct,
        "pricePairs":catalog["stats"]["eweGoAfirDirectPricePairs"][:20],
        "deltas":catalog["stats"]["eweGoDirectVsAfirDeltaDistribution"][:20]
    },ensure_ascii=False,sort_keys=True))

if __name__=="__main__": main()
