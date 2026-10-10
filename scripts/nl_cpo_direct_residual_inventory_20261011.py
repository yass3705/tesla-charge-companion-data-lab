#!/usr/bin/env python3
"""Reconcile latest DOT-NL exact physical EVSE gaps for four CPOs without price invention.

Read-only source analysis. One connector per CSV row, each with exact physical EVSE
identity, power, status and tariff match reason. National dynamic source as of last
successful DOT-NL workflow. No generic kWh/guest price, no eMSP substitution.
"""
from __future__ import annotations
import collections
import csv
import datetime as dt
import gzip
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dotnl_netherlands_runtime as eng

SOURCE=ROOT/"data/national/netherlands_dotnl/normalized.json.gz"
REPORT=ROOT/"reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.json"
DETAIL=ROOT/"reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.csv"
TARGET={"LNT":"Laadnet","AGO":"Agri Go Charge (AgriSnellaad)","SPA":"StellaPower","WAT":"WattHub"}

def main():
    with gzip.open(SOURCE,"rt",encoding="utf-8") as f: data=json.load(f)
    tariffs=data.get("tariffs") or {}
    gen=data.get("generatedAt") or dt.datetime.now(dt.timezone.utc).isoformat()
    today=eng.date_of(gen) or dt.datetime.now(dt.timezone.utc).date()
    stats={p:{"partyId":p,"operator":name,"locations":0,"totalConnectors":0,
                "exactPricedConnectors":0,"unpricedConnectors":0,"missingTariffRefs":0,
                "unpricedReasons":collections.Counter(),"kindPower":collections.Counter(),
                "unpricedByKindPower":collections.Counter(),"statusAll":collections.Counter(),
                "statusUnpriced":collections.Counter(),"sampleLocations":[]}
           for p,name in TARGET.items()}
    details=[]
    compile_cache={}
    selection_cache={}
    global_stats={"unsupportedReasons":collections.Counter(),"ambiguousTariffConnectors":0}
    included_station_ids=set()
    for st in data.get("stations") or []:
        party=str(st.get("partyId") or "")
        if party not in TARGET: continue
        coord=st.get("coordinates") or {}
        lat=eng.fnum(coord.get("latitude"));lon=eng.fnum(coord.get("longitude"))
        if lat is None or lon is None or not eng.in_nl_bounds(lat,lon): continue
        station_id=str(st.get("stationId") or "")
        assert station_id
        assert station_id not in included_station_ids,station_id
        included_station_ids.add(station_id)
        s=stats[party]
        s["locations"]+=1
        before=s["unpricedConnectors"]
        for evse in st.get("evses") or []:
            evse_id=str(evse.get("evseId") or evse.get("uid") or "")
            status=str(evse.get("status") or "UNKNOWN").upper()
            for connector in evse.get("connectors") or []:
                cid=str(connector.get("connectorId") or connector.get("id") or "")
                power=eng.fnum(connector.get("powerKw"))
                kind=eng.kind(connector)
                power_rounded=round(power,1) if power is not None else None
                keytype=(kind,repr(power_rounded))
                keys=list(connector.get("tariffKeys") or [])
                s["totalConnectors"]+=1
                s["statusAll"][status]+=1
                s["kindPower"][keytype]+=1
                tariff_key,rules,error=eng.choose_tariff(keys,tariffs,today,global_stats,compile_cache,selection_cache)
                if tariff_key:
                    s["exactPricedConnectors"]+=1
                    continue
                s["unpricedConnectors"]+=1
                s["statusUnpriced"][status]+=1
                s["unpricedByKindPower"][keytype]+=1
                if not keys:s["missingTariffRefs"]+=1
                reason=error or ("missing_tariff_reference" if not keys else "tariff_not_compilable")
                s["unpricedReasons"][reason]+=1
                tariff_types=sorted({str(tariffs.get(k,{}).get("type") or "UNSPECIFIED") for k in keys if k in tariffs})
                details.append({"partyId":party,"operator":TARGET[party],
                 "stationId":station_id,"name":str(st.get("name") or ""),
                 "city":str(st.get("city") or ""),"postalCode":str(st.get("postalCode") or ""),
                 "latitude":lat,"longitude":lon,
                 "evseId":evse_id,"connectorId":cid,"connectorKind":kind,
                 "powerKw":power_rounded,"evseStatus":status,
                 "tariffKeyCount":len(keys),"tariffKeys":";".join(map(str,keys)),
                 "tariffTypes":";".join(tariff_types),
                 "unpricedReason":reason,
                 "accessStatus":"national_OCPI_published_no_individual_physical_access_proof",
                 "directCpoGuestTariff":"UNVERIFIED"})
        if s["unpricedConnectors"]>before and len(s["sampleLocations"])<6:
            s["sampleLocations"].append({
                "stationId":station_id,"name":st.get("name"),"city":st.get("city"),
                "postalCode":st.get("postalCode"),"coordinates":{"lat":lat,"lon":lon},
                "unpricedConnectorsAtStation":s["unpricedConnectors"]-before
            })
    assert len(details)==sum(s["unpricedConnectors"] for s in stats.values())
    assert all(s["totalConnectors"]==s["exactPricedConnectors"]+s["unpricedConnectors"] for s in stats.values())
    with DETAIL.open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(details[0].keys()) if details else ["partyId"])
        w.writeheader();w.writerows(sorted(details,key=lambda r:(r["partyId"],r["stationId"],r["evseId"],r["connectorId"])))
    summary={}
    for p,s in stats.items():
        v={k:val for k,val in s.items() if k not in ("kindPower","unpricedByKindPower","statusAll","statusUnpriced","unpricedReasons")}
        v["allByPower"]=[{"kind":k[0],"powerKw":None if k[1]=="None" else float(k[1]),
                          "count":count} for k,count in sorted(s["kindPower"].items(),key=lambda x:(x[0][0],x[0][1]))]
        v["unpricedByPower"]=[{"kind":k[0],"powerKw":None if k[1]=="None" else float(k[1]),
                          "count":count} for k,count in sorted(s["unpricedByKindPower"].items(),key=lambda x:(x[0][0],x[0][1]))]
        v["statusAll"]=dict(s["statusAll"])
        v["statusUnpriced"]=dict(s["statusUnpriced"])
        v["unpricedReasons"]=dict(s["unpricedReasons"])
        summary[p]=v
    result={
        "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "snapshotGeneratedAt":gen,"evaluationTariffDate":today.isoformat(),
        "country":"NL","scope":"exact EVSE/direct-CPO; excluding off-bounds/tesla",
        "source":str(SOURCE.relative_to(ROOT)),
        "operatorStats":summary,
        "globalMissingConnectorCountAmongFourOperators":len(details),
        "issueNotes":[
           "Laadnet: per charger owner-configured prices and per-station opt-in QR, no uniform direct PAYG",
           "Agri Go: QR price depends on location category, time-connected and fast charger after-time fees; do not map only by power",
           "StellaPower: charger-side per-location posted price and QR bank card, exact official web amount not accessible",
           "WattHub: dynamic price per bookable vehicle/slot; confirm public car accessibility before tariff work"
        ],
        "sitePhysicalAccess":"Unverified national source publication is not independent proof of unrestricted public entry",
        "noPriceGuess":True,"roamingExcluded":True,"emspExcluded":True,
        "fullUnpricedConnectorCSV":str(DETAIL.relative_to(ROOT))
    }
    REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"snapshot":gen,
            "byParty":{p:{k:v[k] for k in ("locations","totalConnectors","exactPricedConnectors","unpricedConnectors","missingTariffRefs")} for p,v in summary.items()},
            "totalUnpriced":len(details)},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
