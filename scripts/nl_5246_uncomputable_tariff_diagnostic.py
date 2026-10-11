#!/usr/bin/env python3
"""Diagnose the 5,246 source tariff present but uncomputable cases exactly.

No modifications to inputs/prices. On active AVAILABLE/CHARGING Type 2,
CCS2, domestic NL connector records, resolve tariff id -> normalized tariff
and record the *actual reasons* and first-party component structures.
"""
from __future__ import annotations
import collections,datetime as dt,gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dotnl_netherlands_runtime as engine

CATS={"IEC_62196_T2","IEC_62196_T2_CABLE","IEC_62196_T2_COMBO"}
STAT={"AVAILABLE","CHARGING"}
OUT=ROOT/"reports/netherlands/dotnl-5246-calculation-root-cause-latest.json"
def nice(v):
    if isinstance(v,float):return round(v,6)
    return v
def main():
    with gzip.open(ROOT/"data/national/netherlands_dotnl/normalized.json.gz","rt",encoding="utf8") as f:d=json.load(f)
    tariffs=d["tariffs"];today=engine.date_of(d.get("generatedAt")) or dt.date.today()
    calc_cache={};chosen_cache={}
    engine_counts={"unsupportedReasons":collections.Counter(),"ambiguousTariffConnectors":0}
    by_reason=collections.Counter();by_party=collections.Counter();by_type=collections.Counter()
    fingerprint=collections.Counter();tariffs_by_reason=collections.defaultdict(set)
    tariff_refs=collections.Counter();samples=collections.defaultdict(list);total=0
    with_tariff_count=0
    for st in d["stations"]:
        c=st.get("coordinates") or {}
        lat=engine.fnum(c.get("latitude"));lon=engine.fnum(c.get("longitude"))
        if lat is None or lon is None or not engine.in_nl_bounds(lat,lon):continue
        for evse in st.get("evses") or []:
            if str(evse.get("status") or "").upper() not in STAT:continue
            for co in evse.get("connectors") or []:
                std=str(co.get("standard") or "").upper()
                if std not in CATS and not std.startswith("DOMESTIC_"):continue
                keys=co.get("tariffKeys") or []
                if not keys:continue
                key,rsn=engine.choose_tariff(keys,tariffs,today,engine_counts,calc_cache,chosen_cache)[::2]
                if key:continue
                total+=1
                party=str(st.get("partyId") or "")
                by_party[party]+=1
                errs=[]
                for k in keys:
                    t=tariffs.get(k)
                    if not t:continue
                    compiled,error=calc_cache[k]
                    if not error:continue
                    errs.append(error)
                    tariffs_by_reason[error].add(k)
                    tariff_refs[(error,k)]+=1
                    for el in t.get("elements") or []:
                        rr=el.get("restrictions") or {}
                        dims=tuple((c.get("type"),c.get("stepSize"),nice(c.get("priceInclVat"))) for c in el.get("priceComponents") or [])
                        restricted=tuple(sorted(k for k,v in rr.items() if v not in (None,"",[],{})))
                        key0=(error,str(t.get("type")),tuple(x[0] for x in dims),tuple(x[1] for x in dims),restricted)
                        fingerprint[key0]+=1
                    if len(samples[error])<9 and (not any(x.get("tariffKey")==k for x in samples[error])):
                        samples[error].append({"tariffKey":k,"partyId":party,"stationId":st.get("stationId"),
                          "evseId":evse.get("evseId"),"connectorId":co.get("id"),
                          "standard":std,"tariffType":t.get("type"),"currency":t.get("currency"),
                          "elements":t.get("elements"),"minPrice":t.get("minPrice"),"maxPrice":t.get("maxPrice")})
                reason=";".join(sorted(set(errs))) if errs else "unknown"
                by_reason[reason]+=1
                by_type[(party,reason)]+=1
    print("TOTAL",total,"REASONS",dict(by_reason),"PARTIES",dict(by_party))
    top_groups=[{"reason":k[0],"tariffType":k[1],"dimensions":list(k[2]),"steps":list(k[3]),
         "restrictions":list(k[4]),"elementOccurrences":n}
        for k,n in fingerprint.most_common(35)]
    out={
      "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
      "snapshotAt":d.get("generatedAt"),"sourceConnectorRecordsWithTariffUncomputable":total,
      "sourceConnectorReasons":dict(by_reason),
      "byParty":dict(by_party),"partyReasonCounts":[{"partyId":k[0],"reason":k[1],"connectors":n} for k,n in by_type.most_common()],
      "uniqueTariffIdsByFailure":{k:len(v) for k,v in tariffs_by_reason.items()},
      "topFailureTariffKeys":[{"reason":a,"tariffKey":b,"connectors":n} for (a,b),n in tariff_refs.most_common(28)],
      "topElementPatterns":top_groups,"samples":dict(samples),
      "notLiveTariff":"This is a source analysis only. No price inference; validate scenario semantics before publishing."
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    assert total==5246, f"Baseline moved: expected 5246, actual {total}"
    print(json.dumps({"total":total,"reasons":out["sourceConnectorReasons"],
      "unique":out["uniqueTariffIdsByFailure"],"topPatterns":top_groups[:12]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
