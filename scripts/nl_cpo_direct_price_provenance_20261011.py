#!/usr/bin/env python3
"""Audit the provenance of technically-priced Laadnet and StellaPower connectors.

Avoid conflating the DOT-NL REGULAR tariff type with verified QR guest pricing.
Read-only. Persist exact sampled source IDs, VAT and origin metadata for manual
and operator-side confirmation. No eMSP tariff promotion.
"""
import collections
import datetime as dt
import gzip
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dotnl_netherlands_runtime as eng

OUT=ROOT/"reports/netherlands/nl-direct-price-provenance-2026-10-11.json"
PARTIES=["LNT","AGO","SPA","WAT"]

def load():
    with gzip.open(ROOT/"data/national/netherlands_dotnl/normalized.json.gz","rt",encoding="utf8") as f:return json.load(f)

def main():
    raw=load();tr=raw.get("tariffs") or {};today=eng.date_of(raw.get("generatedAt")) or dt.date.today()
    stats={p:{"compilable":0,"nonCompilable":0,"types":collections.Counter(),"sourceKind":collections.Counter(),
              "tariffParty":collections.Counter(),"componentsWithGrossInclVAT":0,"componentsExVATOnly":0,
              "componentsNoVatPct":0,"sourceKeys":collections.Counter(),"samplePriced":[],
              "sampleUnpriced":[]} for p in PARTIES}
    compile_cache={};selection_cache={};choose_stats={"unsupportedReasons":collections.Counter(),"ambiguousTariffConnectors":0}
    for loc in raw.get("stations") or []:
        p=str(loc.get("partyId") or "")
        if p not in stats:continue
        co=loc.get("coordinates") or {};lat=eng.fnum(co.get("latitude"));lon=eng.fnum(co.get("longitude"))
        if lat is None or lon is None or not eng.in_nl_bounds(lat,lon):continue
        s=stats[p]
        for evse in loc.get("evses") or []:
            for c in evse.get("connectors") or []:
                keys=c.get("tariffKeys") or []
                k,rules,reason=eng.choose_tariff(keys,tr,today,choose_stats,compile_cache,selection_cache)
                if not k:
                    s["nonCompilable"]+=1
                    if len(s["sampleUnpriced"])<3:
                        s["sampleUnpriced"].append({"locationId":loc.get("stationId"),
                              "evseId":evse.get("evseId"),"tariffKeys":keys,"reason":reason})
                    continue
                s["compilable"]+=1
                t=tr[k]
                typ=str(t.get("type") or "UNSPECIFIED")
                src=str(t.get("sourceKind") or "DOT_NL_UNSPECIFIED")
                tid=str(t.get("partyId") or "MISSING")
                s["types"][typ]+=1;s["sourceKind"][src]+=1;s["tariffParty"][tid]+=1;s["sourceKeys"][str(k)]+=1
                flat=[]
                for element in t.get("elements") or []:
                    for comp in element.get("priceComponents") or []:
                        if comp.get("priceInclVat") is not None:s["componentsWithGrossInclVAT"]+=1
                        elif comp.get("priceExVat") is not None:s["componentsExVATOnly"]+=1
                        if comp.get("vatPct") is None:s["componentsNoVatPct"]+=1
                        flat.append({"dimension":comp.get("type"),"grossInclVat":comp.get("priceInclVat"),
                                     "net":comp.get("priceExVat"),"vatPct":comp.get("vatPct"),
                                     "stepSize":comp.get("stepSize"),"restrictions":element.get("restrictions")})
                if len(s["samplePriced"])<5:
                    s["samplePriced"].append({"locationId":loc.get("stationId"),"locationName":loc.get("name"),
                      "evseId":evse.get("evseId"),"connectorId":c.get("connectorId") or c.get("id"),
                      "powerKw":c.get("powerKw"),"selectedTariffKey":str(k),
                      "type":typ,"sourceKind":src,"tariffParty":tid,
                      "currency":t.get("currency"),"components":flat[:8]})
    out={}
    for p,s in stats.items():
        out[p]={k:(dict(v) if isinstance(v,collections.Counter) else v)
                for k,v in s.items() if k!="sourceKeys"}
        out[p]["distinctSelectedTariffKeys"]=len(s["sourceKeys"])
        out[p]["topTariffKeys"]=[{"key":k,"connectorCount":n} for k,n in s["sourceKeys"].most_common(8)]
    report={"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "snapshotGeneratedAt":raw.get("generatedAt"),"evaluationDate":today.isoformat(),
            "source":"data/national/netherlands_dotnl/normalized.json.gz",
            "operators":out,
            "interpretation":"Source tariff type REGULAR/untyped can be technically compiled but does NOT prove the exact amount available via the operator's QR guest checkout. Absent public payment proof, retain QUARANTINE even if the compiler returns a number.",
            "noChangesToV9":True}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"snapshot":report["snapshotGeneratedAt"],"operators":{p:{k:v for k,v in vals.items() if k in ("compilable","nonCompilable","types","sourceKind","tariffParty","componentsWithGrossInclVAT","componentsExVATOnly","componentsNoVatPct","distinctSelectedTariffKeys")} for p,vals in out.items()}},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
