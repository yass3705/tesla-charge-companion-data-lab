#!/usr/bin/env python3
"""Conservatively classify German AFIR ad-hoc tariffs for TCC staging.

A site becomes rankable only when every priced rate is the same simple EUR/kWh
price, VAT is explicitly included, and there are no flat/base/minute/time/cap
components. This intentionally leaves many valid but complex tariffs unrankable.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

import germany_afir_static_normalize as afir


def scalar(value):
    if isinstance(value, dict):
        return value.get("value") or value.get("extendedValueG")
    return value


def iter_priced_rates(site: dict):
    containers=[("site", site, site.get("idG"))]
    for station in afir.as_list(site.get("energyInfrastructureStation")):
        if not isinstance(station, dict):
            continue
        containers.append(("station", station, station.get("idG")))
        for refill in afir.as_list(station.get("refillPoint")):
            if not isinstance(refill, dict):
                continue
            point=refill.get("aegiElectricChargingPoint")
            if isinstance(point, dict):
                containers.append(("chargingPoint", point, point.get("idG")))
    for scope,container,object_id in containers:
        for energy in afir.as_list(container.get("electricEnergy")):
            if not isinstance(energy, dict):
                continue
            for rate in afir.as_list(energy.get("energyRate")):
                if not isinstance(rate, dict):
                    continue
                components=[]
                for p in afir.as_list(rate.get("energyPrice")):
                    if not isinstance(p, dict):
                        continue
                    value=afir.safe_float(p.get("value"))
                    if value is None:
                        continue
                    components.append({
                        "priceType": scalar(p.get("priceType")),
                        "value": value,
                        "priceCap": afir.safe_float(p.get("priceCap")),
                        "taxIncluded": p.get("taxIncluded"),
                        "hasTimeBasedApplicability": bool(p.get("timeBasedApplicability")),
                        "hasOverallPeriod": bool(p.get("overallPeriod")),
                    })
                if components:
                    yield {
                        "scope":scope,
                        "sourceObjectId":object_id,
                        "rateId":rate.get("idG"),
                        "lastUpdated":rate.get("lastUpdated"),
                        "ratePolicy":scalar(rate.get("ratePolicy")),
                        "currency":[str(x) for x in afir.as_list(rate.get("applicableCurrency")) if x],
                        "components":components,
                    }


def classify_rate(rate: dict):
    if rate.get("ratePolicy") != "adHoc":
        return "non_adhoc"
    if rate.get("currency") != ["EUR"]:
        return "non_eur_or_ambiguous_currency"
    components=rate.get("components") or []
    if len(components) != 1:
        return "compound"
    p=components[0]
    if p.get("priceType") != "pricePerKWh":
        return "non_kwh_component"
    value=p.get("value")
    if value is None or value < 0 or value > 5:
        return "invalid_or_implausible_value"
    if p.get("priceCap") is not None or p.get("hasTimeBasedApplicability") or p.get("hasOverallPeriod"):
        return "conditional"
    if p.get("taxIncluded") is True:
        return "simple_kwh_tax_included"
    if p.get("taxIncluded") is False:
        return "simple_kwh_tax_excluded"
    return "simple_kwh_tax_unknown"


def classify_site(provider: str, site: dict):
    rates=list(iter_priced_rates(site))
    for rate in rates:
        rate["classification"]=classify_rate(rate)
    classes=Counter(r["classification"] for r in rates)
    simple=[r for r in rates if r["classification"].startswith("simple_kwh_")]
    values=sorted({round(r["components"][0]["value"],6) for r in simple})

    if not rates:
        classification="no_price"
        rankable=False
        unit_price=None
    elif classes == Counter({"simple_kwh_tax_included": len(rates)}) and len(values)==1:
        classification="uniform_simple_kwh_rankable"
        rankable=True
        unit_price=values[0]
    elif classes == Counter({"simple_kwh_tax_unknown": len(rates)}) and len(values)==1:
        classification="uniform_simple_kwh_tax_unknown"
        rankable=False
        unit_price=None
    elif len(simple)==len(rates) and len(values)>1:
        classification="simple_kwh_varies_by_rate"
        rankable=False
        unit_price=None
    elif simple and len(simple)==len(rates):
        classification="simple_kwh_mixed_tax_semantics"
        rankable=False
        unit_price=None
    else:
        classification="compound_or_conditional"
        rankable=False
        unit_price=None

    return {
        "provider":provider,
        "sourceSiteId":site.get("idG"),
        "classification":classification,
        "rankable":rankable,
        "effectiveEurPerKwh":unit_price,
        "pricedRateCount":len(rates),
        "rateClassDistribution":dict(classes),
        "distinctSimpleKwhValues":values,
        "rates":rates,
    }


def main():
    site_rows=[]; provider_stats={}
    for provider,meta in afir.OFFERS.items():
        payload,_=afir.fetch_offer(meta["offerId"])
        sites,_=afir.get_sites(payload)
        rows=[classify_site(provider,s) for s in sites]
        site_rows.extend(rows)
        class_counts=Counter(r["classification"] for r in rows)
        provider_stats[provider]={
            "sites":len(rows),
            "sitesWithPrice":sum(r["pricedRateCount"]>0 for r in rows),
            "rankableSites":sum(r["rankable"] for r in rows),
            "classificationDistribution":dict(class_counts),
        }
    result={
        "schemaVersion":"0.1.0",
        "dataset":"germany-afir-tariff-classification",
        "countryCode":"DE",
        "scope":{
            "stagedOnly":True,"publishesToTcc":False,
            "rankabilityRule":"all priced rates identical simple EUR/kWh, adHoc, VAT explicitly included, no time/period/cap/other components",
            "chargecloudTaxUnknownRemainsUnrankable":True,
        },
        "providerStats":provider_stats,
        "sites":site_rows,
    }
    out=Path("data/germany/afir_tariff_classification.json.gz")
    out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",compresslevel=9) as f:
        json.dump(result,f,ensure_ascii=False,separators=(",",":"))
    print("TCC_AFIR_TARIFF_CLASSIFICATION="+json.dumps(provider_stats,sort_keys=True))

if __name__=="__main__": main()
