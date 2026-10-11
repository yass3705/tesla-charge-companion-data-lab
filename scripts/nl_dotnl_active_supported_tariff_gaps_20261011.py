#!/usr/bin/env python3
"""Netherlands DOT-NL nationwide *in-service* Type 2 / CCS / domestic tariff gap audit.

Authority: DOT-NL is the canonical tariff source for ALL national CPOs.
Distinguish missing tariff vs invalid/ambiguous computation. Filter at EVSE
level to AVAILABLE / CHARGING only (strict operational); report BLOCKED and
RESERVED in separate appendix, excluding OUTOFORDER/INOPERATIVE/UNKNOWN etc.
Filter connector standards: domestic normal sockets, IEC Type 2, CCS Combo 2.
Never include CHAdeMO, Type 1, proprietary Tesla, or eMSP overlay as CPO tariff.
One row per exact source connector record; preserve duplicate physical IDs
rather than collapsing records. No changes to production or tariff prices.
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
import dotnl_netherlands_runtime as engine

SNAP=ROOT/"data/national/netherlands_dotnl/normalized.json.gz"
OUT=ROOT/"reports/netherlands/dotnl-active-type2-ccs-tariff-audit-latest.json"
DETAIL=ROOT/"reports/netherlands/dotnl-active-type2-ccs-unpriced-connectors-latest.csv"
IN_SERVICE={"AVAILABLE","CHARGING"}
ADJACENT={"BLOCKED","RESERVED"}

def standards(s):
    v=str(s or "").strip().upper()
    if v in {"IEC_62196_T2","IEC_62196_T2_COMBO","IEC_62196_T2_CABLE"}:return "CCS" if v=="IEC_62196_T2_COMBO" else "TYPE2"
    if v.startswith("DOMESTIC_"):return "DOMESTIC"
    return "EXCLUDED"

def nonempty(t):
    return t not in (None, "", [], {})

def issue(keys,unresolved,tariffs,selection_error):
    if selection_error=="ambiguous":return "CONFLICTING_TARIFFS"
    if selection_error=="none_exact" and not keys:
        return "UNRESOLVED_TARIFF_ID" if unresolved else "NO_TARIFF_IN_DOTNL"
    if selection_error=="none_exact":
        return "TARIFF_PRESENT_NOT_CALCULABLE"
    return "TARIFF_PRESENT_NOT_CALCULABLE"

def main():
    with gzip.open(SNAP,"rt",encoding="utf-8") as f:d=json.load(f)
    tariffs=d.get("tariffs") or {}
    today=engine.date_of(d.get("generatedAt")) or dt.datetime.now(dt.timezone.utc).date()
    stats=collections.defaultdict(lambda:{"locations":set(),"activeLocations":set(),
          "sourceRecordsAllStatusesSupportedConnectors":0,
          "activeSupportedConnectors":0,
          "activePricedConnectors":0,"activeUnpricedConnectors":0,
          "adjacentBlockedReservedSupportedConnectors":0,
          "inactiveOrUnknownSupportedConnectors":0,
          "activeByStandard":collections.Counter(),
          "activeMissingByStandard":collections.Counter(),
          "activeMissingByStatus":collections.Counter(),
          "activeMissingByKindPower":collections.Counter(),
          "activeMissingReasons":collections.Counter(),
          "activePricedByStandard":collections.Counter()})
    worldwide=collections.Counter()
    activeTotal=collections.Counter()
    detailed=[]
    seen=collections.Counter()
    compile_cache={}
    select_cache={}
    selectionStats={"unsupportedReasons":collections.Counter(),"ambiguousTariffConnectors":0}
    for station in d.get("stations") or []:
        co=station.get("coordinates") or {}
        lat=engine.fnum(co.get("latitude"));lon=engine.fnum(co.get("longitude"))
        if lat is None or lon is None or not engine.in_nl_bounds(lat,lon):continue
        party=str(station.get("partyId") or "UNKNOWN")
        sid=str(station.get("stationId") or "")
        st=stats[party]
        for evse in station.get("evses") or []:
            status=str(evse.get("status") or "UNKNOWN").upper()
            evid=str(evse.get("evseId") or evse.get("uid") or "")
            for conn in evse.get("connectors") or []:
                ct=standards(conn.get("standard"))
                worldwide[(status,ct)]+=1
                if ct=="EXCLUDED":continue
                st["locations"].add(sid)
                st["sourceRecordsAllStatusesSupportedConnectors"]+=1
                if status in ADJACENT:
                    st["adjacentBlockedReservedSupportedConnectors"]+=1
                    continue
                if status not in IN_SERVICE:
                    st["inactiveOrUnknownSupportedConnectors"]+=1
                    continue
                st["activeLocations"].add(sid)
                st["activeSupportedConnectors"]+=1
                st["activeByStandard"][ct]+=1
                activeTotal["supported_total"]+=1
                activeTotal[(ct,"total")]+=1
                keys=tuple(conn.get("tariffKeys") or [])
                unresolved=tuple(conn.get("unresolvedTariffIds") or [])
                tid=tuple(conn.get("tariffIds") or [])
                tariff_key,rules,reason=engine.choose_tariff(keys,tariffs,today,selectionStats,compile_cache,select_cache)
                if tariff_key:
                    st["activePricedConnectors"]+=1
                    st["activePricedByStandard"][ct]+=1
                    activeTotal["priced"]+=1
                    activeTotal[(ct,"priced")]+=1
                    continue
                why=issue(keys,unresolved,tariffs,reason)
                st["activeUnpricedConnectors"]+=1
                st["activeMissingByStandard"][ct]+=1
                st["activeMissingByStatus"][status]+=1
                st["activeMissingReasons"][why]+=1
                power=engine.fnum(conn.get("powerKw"))
                pwr=round(power,1) if power else None
                st["activeMissingByKindPower"][(ct,pwr)]+=1
                activeTotal["unpriced"]+=1
                activeTotal[(ct,"unpriced")]+=1
                activeTotal[("reason",why)]+=1
                cid=str(conn.get("id") or "")
                eid=(party,sid,evid,cid)
                seen[eid]+=1
                detailed.append({
                   "partyId":party,"stationId":sid,"stationName":str(station.get("name") or ""),
                   "city":str(station.get("city") or ""),"postalCode":str(station.get("postalCode") or ""),
                   "latitude":lat,"longitude":lon,
                   "evseId":evid,"connectorId":cid,"standard":str(conn.get("standard") or ""),
                   "tccConnectorClass":ct,"powerKw":pwr,"evseStatus":status,
                   "tariffIds":";".join(tid),"tariffKeys":";".join(keys),
                   "unresolvedTariffIds":";".join(unresolved),
                   "selectedTariffReason":str(reason or ""), "gapType":why,
                   "originalTariffRefCount":len(keys),"publishedDotnlTariff":"MISSING_OR_UNCALCULABLE"
                })
    assert activeTotal["supported_total"]==activeTotal["priced"]+activeTotal["unpriced"]
    cpo={}
    for party,s in stats.items():
        out={}
        for k,v in s.items():
            if isinstance(v,set):out[k]=len(v)
            elif isinstance(v,collections.Counter):
                if k=="activeMissingByKindPower":
                    out[k]=[{"connectorClass":cl,"powerKw":pw,"unpriced":n} for (cl,pw),n in sorted(v.items(),key=lambda pair:(pair[0][0],str(pair[0][1])))]
                else:out[k]=dict(v)
            else:out[k]=v
        out["activeCoveragePercent"]=round(out["activePricedConnectors"]*100/max(1,out["activeSupportedConnectors"]),3)
        cpo[party]=out
    with DETAIL.open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(detailed[0]) if detailed else ["partyId"])
        w.writeheader()
        w.writerows(sorted(detailed,key=lambda x:(x["partyId"],x["stationId"],x["evseId"],x["connectorId"])))
    all_standards=collections.Counter()
    for (status,cl),n in worldwide.items():all_standards[cl]+=n
    report={
        "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "snapshotAt":d.get("generatedAt"),"evaluatedTariffDate":today.isoformat(),
        "filter":{"country":"NL European geographic bounds","stationStatus":["AVAILABLE","CHARGING"],
                  "includedStandards":["DOMESTIC_*","IEC_62196_T2","IEC_62196_T2_CABLE","IEC_62196_T2_COMBO"],
                  "excludedStandards":["CHADEMO","IEC_62196_T1","TESLA_*","all other"],
                  "blockedReservedStatusAuditedSeparately":True,
                  "availableAndChargingOnly":True,"nationalCpoPriceIsCanonical":True},
        "activeScope":{"supportedConnectorRecords":activeTotal["supported_total"],
                       "priced":activeTotal["priced"],"unpriced":activeTotal["unpriced"],
                       "byStandard":{cat:{"activeConnectorRecords":activeTotal[(cat,"total")],
                                          "priced":activeTotal[(cat,"priced")],
                                          "unpriced":activeTotal[(cat,"unpriced")]} for cat in ("DOMESTIC","TYPE2","CCS")},
                       "missingReasons":{key[1]:value for key,value in activeTotal.items() if isinstance(key,tuple) and key[0]=="reason"}},
        "excludedOrSidecar":{"allSourceConnectorRecords":sum(worldwide.values()),
                             "allStatusExcludedStandardConnectorRecords":all_standards["EXCLUDED"],
                             "supportedConnectorRecordsBlockedOrReserved":sum(s["adjacentBlockedReservedSupportedConnectors"] for s in stats.values()),
                             "supportedConnectorRecordsInactiveOrUnknown":sum(s["inactiveOrUnknownSupportedConnectors"] for s in stats.values()),
                             "sourceStatusAndClassCounts":{status:{cat:worldwide[(status,cat)] for cat in ("DOMESTIC","TYPE2","CCS","EXCLUDED")} for status in sorted({s for s,c in worldwide})}},
        "cpoCount":len(cpo),
        "cpoCounts":dict(sorted(cpo.items(),key=lambda v:v[1]["activeUnpricedConnectors"],reverse=True)),
        "topCposByActiveMissing":[{"partyId":k,"unpriced":v["activeUnpricedConnectors"],
            "priced":v["activePricedConnectors"],"activeTotal":v["activeSupportedConnectors"],
            "noTariff":v["activeMissingReasons"].get("NO_TARIFF_IN_DOTNL",0),
            "unresolvedLink":v["activeMissingReasons"].get("UNRESOLVED_TARIFF_ID",0),
            "notCalculable":v["activeMissingReasons"].get("TARIFF_PRESENT_NOT_CALCULABLE",0),
            "ambiguous":v["activeMissingReasons"].get("CONFLICTING_TARIFFS",0)} for k,v in sorted(cpo.items(),key=lambda p:p[1]["activeUnpricedConnectors"],reverse=True)[:30]],
        "duplicateExactIdentityAmongUnpricedRecords":sum(1 for n in seen.values() if n>1),
        "selectionUnsupportedReasons":dict(selectionStats["unsupportedReasons"]),
        "noTariffInvented":True,"noPricingChanges":True,
        "detailCsv":"reports/netherlands/dotnl-active-type2-ccs-unpriced-connectors-latest.csv"
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"snapshotAt":report["snapshotAt"],"scope":report["activeScope"],
        "excludedOrSidecar":{k:v for k,v in report["excludedOrSidecar"].items() if k!="sourceStatusAndClassCounts"},
        "topCposByActiveMissing":report["topCposByActiveMissing"][:14]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
