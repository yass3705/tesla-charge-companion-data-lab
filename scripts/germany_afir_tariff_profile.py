#!/usr/bin/env python3
"""Profile German AFIR tariff semantics before making prices rankable.

QA/staging only. This script inspects raw DATEX II tariff fields from the three
anonymous Mobilithek feeds and records distributions of ratePolicy, priceType,
currency, payment, scope, component combinations and time applicability.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import germany_afir_static_normalize as afir


def scalar(value):
    if isinstance(value, dict):
        return value.get("value") or value.get("extendedValueG")
    return value


def walk_rates(site: dict):
    rows=[]
    containers=[("site", site)]
    for station in afir.as_list(site.get("energyInfrastructureStation")):
        if not isinstance(station, dict):
            continue
        containers.append(("station", station))
        for refill in afir.as_list(station.get("refillPoint")):
            if not isinstance(refill, dict):
                continue
            point=refill.get("aegiElectricChargingPoint")
            if isinstance(point, dict):
                containers.append(("chargingPoint", point))
    for scope, container in containers:
        for energy in afir.as_list(container.get("electricEnergy")):
            if not isinstance(energy, dict):
                continue
            for rate in afir.as_list(energy.get("energyRate")):
                if not isinstance(rate, dict):
                    continue
                prices=[]
                for price in afir.as_list(rate.get("energyPrice")):
                    if not isinstance(price, dict):
                        continue
                    value=afir.safe_float(price.get("value"))
                    if value is None:
                        continue
                    prices.append({
                        "priceType": scalar(price.get("priceType")),
                        "value": value,
                        "priceCap": afir.safe_float(price.get("priceCap")),
                        "taxIncluded": price.get("taxIncluded"),
                        "hasTimeBasedApplicability": bool(price.get("timeBasedApplicability")),
                        "hasOverallPeriod": bool(price.get("overallPeriod")),
                    })
                if prices:
                    rows.append({
                        "scope": scope,
                        "ratePolicy": scalar(rate.get("ratePolicy")),
                        "currency": tuple(str(x) for x in afir.as_list(rate.get("applicableCurrency")) if x),
                        "payment": rate.get("payment"),
                        "prices": prices,
                        "rateId": rate.get("idG"),
                    })
    return rows


def compact_payment(value):
    if value is None:
        return "null"
    if isinstance(value, (str,int,float,bool)):
        return str(value)
    if isinstance(value, list):
        return "list:"+",".join(sorted({str(scalar(x)) for x in value})[:12])
    if isinstance(value, dict):
        vals=[]
        for k,v in sorted(value.items()):
            if isinstance(v,(str,int,float,bool)) or v is None:
                vals.append(f"{k}={v}")
            elif isinstance(v,list):
                vals.append(f"{k}=[{','.join(str(scalar(x)) for x in v[:8])}]")
        return "obj:"+";".join(vals[:12])
    return type(value).__name__


def main():
    report={
        "schemaVersion":"0.1.0",
        "dataset":"germany-afir-tariff-profile",
        "countryCode":"DE",
        "scope":{"stagedOnly":True,"publishesToTcc":False,"tariffsRankable":False},
        "providers":{},
    }
    global_c=Counter()
    examples=defaultdict(list)
    for provider,meta in afir.OFFERS.items():
        payload,_=afir.fetch_offer(meta["offerId"])
        sites,_=afir.get_sites(payload)
        c=Counter(); site_with_rates=0
        combos=Counter(); values=Counter(); payments=Counter()
        for site in sites:
            rows=walk_rates(site)
            if rows: site_with_rates += 1
            for row in rows:
                c["rates"] += 1
                c[f"scope:{row['scope']}"] += 1
                c[f"ratePolicy:{row['ratePolicy']}"] += 1
                payments[compact_payment(row["payment"])] += 1
                currencies=row["currency"] or ("<none>",)
                for cur in currencies:
                    c[f"currency:{cur}"] += 1
                types=[]
                for p in row["prices"]:
                    pt=str(p["priceType"])
                    types.append(pt)
                    c[f"priceType:{pt}"] += 1
                    c["components"] += 1
                    if p["taxIncluded"] is True: c["taxIncluded:true"] += 1
                    elif p["taxIncluded"] is False: c["taxIncluded:false"] += 1
                    else: c["taxIncluded:null"] += 1
                    if p["hasTimeBasedApplicability"]: c["timeBasedComponents"] += 1
                    if p["hasOverallPeriod"]: c["overallPeriodComponents"] += 1
                    values[(pt, round(p["value"],6))] += 1
                combo="+".join(sorted(types))
                combos[(str(row["ratePolicy"]), combo)] += 1
                key=(provider,str(row["ratePolicy"]),combo)
                if len(examples[key])<4:
                    examples[key].append({
                        "siteId":site.get("idG"),"siteName":afir.text_value(site.get("name")),
                        "scope":row["scope"],"currency":row["currency"],"payment":row["payment"],"prices":row["prices"]
                    })
        c["sites"] = len(sites); c["sitesWithActualPrice"] = site_with_rates
        global_c.update(c)
        report["providers"][provider]={
            "stats":dict(c),
            "topRatePolicyPriceTypeCombos":[{"ratePolicy":k[0],"priceTypes":k[1],"count":v} for k,v in combos.most_common(40)],
            "topPayments":[{"signature":k,"count":v} for k,v in payments.most_common(30)],
            "topPriceValues":[{"priceType":k[0],"value":k[1],"count":v} for k,v in values.most_common(60)],
        }
    report["globalStats"]=dict(global_c)
    report["examples"]=[{"provider":k[0],"ratePolicy":k[1],"priceTypes":k[2],"rows":v} for k,v in sorted(examples.items())]
    out=Path("data/germany/afir_tariff_profile.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TCC_AFIR_TARIFF_PROFILE="+json.dumps({p:r["stats"] for p,r in report["providers"].items()},sort_keys=True))
    for p,r in report["providers"].items():
        print("TCC_AFIR_TARIFF_COMBOS="+json.dumps({"provider":p,"combos":r["topRatePolicyPriceTypeCombos"][:20]},ensure_ascii=False,sort_keys=True))
        print("TCC_AFIR_TARIFF_PAYMENTS="+json.dumps({"provider":p,"payments":r["topPayments"][:12]},ensure_ascii=False,sort_keys=True))
        print("TCC_AFIR_TARIFF_VALUES="+json.dumps({"provider":p,"values":r["topPriceValues"][:20]},ensure_ascii=False,sort_keys=True))

if __name__=="__main__": main()
