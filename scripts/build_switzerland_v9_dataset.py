#!/usr/bin/env python3
from __future__ import annotations

import json, re, urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/national/switzerland_public_charging_v9.json"
SUMMARY=ROOT/"docs/switzerland-v9-integration-2026-09-28.json"
NATIONAL_URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"

# Highest priority first. Only production/validated sources belong here.
SOURCES=[
 ("data/switzerland/ionity-official-national-direct-tariffs.json",10),
 ("data/switzerland/lidl-official-direct-tariffs.json",10),
 ("data/switzerland/migrol-official-direct-tariffs.json",10),
 ("data/switzerland/shell-evpass-official-direct-tariffs.json",10),
 ("data/switzerland/plenitude-official-direct-tariffs.json",10),
 ("data/switzerland/saascharge-official-direct-tariffs.json",10),
 ("data/switzerland/ail-emoti-official-direct-tariffs.json",10),
 ("data/switzerland/autosense-amag-direct-tariffs.json",10),
 ("data/switzerland/fastned-official-direct-tariffs.json",10),
 ("data/switzerland/tae-matterhorn-terminal-direct-tariffs.json",10),
 ("data/switzerland/cci-move-cpo-tariffs-national.json",10),
 ("data/switzerland/soc-move-cpo-tariffs-national.json",10),
 ("data/switzerland/iwb-official-basel-overlay.json",10),
 ("data/switzerland/iwb-direct-tariffs-second-pass.json",20),
 ("data/switzerland/ecarup-owner-direct-tariffs.json",10),
 ("data/switzerland/ecarup-owner-coordinate-safe-overlay.json",20),
 ("data/switzerland/ewo-ecarup-direct-tariffs.json",10),
 ("data/switzerland/ebs-ecarup-direct-tariffs.json",10),
 ("data/switzerland/powerup-monta-direct-tariffs.json",10),
 ("data/switzerland/agr-monta-direct-tariffs.json",10),
 ("data/switzerland/ewd-official-direct-tariffs.json",10),
 ("data/switzerland/ewz-direct-tariffs.json",20),
 ("data/switzerland/energie360-direct-tariffs.json",20),
 ("data/switzerland/electra-direct-tariffs.json",20),
 ("data/switzerland/move-direct-tariffs.json",20),
 ("data/switzerland/mmn-move-cpo-tariffs.json",10),
 ("data/switzerland/cpi-current-direct-tariffs.json",10),
 ("data/switzerland/chevp-evpass-official-direct-tariffs.json",10),
 ("data/switzerland/edh-direct-tariffs.json",20),
 ("data/switzerland/de-edh-direct-tariffs.json",20),
 ("data/switzerland/505-restricted-direct-classification.json",10),
 ("data/switzerland/911-restricted-direct-classification.json",10),
 ("data/switzerland/bck-restricted-direct-classification.json",10),
 ("data/switzerland/par-partino-restricted-direct-classification.json",10),
 ("data/swisscharge/swisscharge-tariffs.json",10),
 ("data/gofast/ev_charger_stations.json",20),
]

PRICE_KEYS={
 "pricePerKwh","chfPerKwh","energyPrice","EnergyPrice","EnergyPricePerKwh",
 "price_per_kwh","pricePerMinute","parkingPrice","ParkingPrice","ParkingPricePerHour",
 "startFee","sessionFee","price","Price","tariff","tariffs","restricted_segments",
 "specialUserEnergyPrice","SpecialUserEnergyPrice","SpecialUserParkingPrice",
}
CLASS_KEYS={"classification","tariffState","tariff_state","noPublicDirectTariff"}

def norm(v:Any)->str:
    return re.sub(r"[^A-Z0-9]","",str(v or "").upper())

def load(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def name_of(ev:dict)->str|None:
    n=ev.get("ChargingStationNames")
    if isinstance(n,str): return n
    if isinstance(n,dict): return n.get("value")
    if isinstance(n,list):
        for x in n:
            if isinstance(x,dict) and x.get("value"): return str(x["value"])
    return None

def extract_national(payload:Any):
    out=[]
    def walk(x:Any, operator_id=None, operator_name=None):
        if isinstance(x,dict):
            oid=x.get("OperatorID",operator_id)
            on=x.get("OperatorName",operator_name)
            eid=x.get("EvseID")
            if eid:
                out.append({
                    "evseId":eid,
                    "operatorId":oid,
                    "operatorName":on,
                    "chargingStationId":x.get("ChargingStationId"),
                    "name":name_of(x),
                    "address":x.get("Address"),
                    "coordinates":x.get("GeoCoordinates"),
                    "plugs":x.get("Plugs"),
                    "chargingFacilities":x.get("ChargingFacilities"),
                    "accessibility":x.get("Accessibility"),
                    "authenticationModes":x.get("AuthenticationModes"),
                    "paymentOptions":x.get("PaymentOptions"),
                    "isOpen24Hours":x.get("IsOpen24Hours"),
                })
            for v in x.values(): walk(v,oid,on)
        elif isinstance(x,list):
            for v in x: walk(v,operator_id,operator_name)
    walk(payload)
    # De-dupe exact EVSE IDs; owner feed is authoritative and duplicates would be a data-quality fault.
    d={}
    for r in out:
        d.setdefault(r["evseId"],r)
    return list(d.values())

def find_evse_id(d:dict)->str|None:
    for k in ("evseId","EvseID","evse_id","id"):
        v=d.get(k)
        if isinstance(v,str) and ("*" in v or v.upper().startswith(("CH","DE","+41","NL"))):
            return v
    return None

def has_tariff_signal(d:dict)->bool:
    if any(k in d for k in PRICE_KEYS|CLASS_KEYS): return True
    p=d.get("price")
    if isinstance(p,dict) and any(k in p for k in PRICE_KEYS): return True
    if d.get("classification") in {"no_public_direct_tariff","no-public-direct-tariff"}: return True
    return False

def compact(d:dict)->dict:
    keep={
      "evseId","EvseID","chargingStationId","stationId","maxPowerKw","powerKw","currency",
      "pricePerKwh","chfPerKwh","energyPrice","EnergyPrice","EnergyPricePerKwh",
      "pricePerMinute","parkingPrice","ParkingPrice","ParkingPricePerHour",
      "startFee","sessionFee","classification","reason","source","method",
      "tariffState","tariff_state","accessType","public","restricted",
      "specialUserEnergyPrice","SpecialUserEnergyPrice","SpecialUserParkingPrice",
      "penaltyGracePeriodMinutes","PenaltyGracePeriodMinutes","penaltyPricePerMinute",
      "PenaltyPricePerMinute","penaltyMaxFee","PenaltyMaxFee","rateDescription",
      "profile","customerProfile","directPrice","price",
    }
    o={k:v for k,v in d.items() if k in keep and v is not None}
    if "price" in o and isinstance(o["price"],dict):
        o["price"]={k:v for k,v in o["price"].items() if k in PRICE_KEYS or k in {
            "Currency","PenaltyGracePeriodMinutes","PenaltyPricePerMinute","PenaltyMaxFee"
        }}
    return o

def extract_source(payload:Any,path:str,priority:int):
    rows=[]
    def walk(x:Any):
        if isinstance(x,dict):
            eid=find_evse_id(x)
            if eid and has_tariff_signal(x):
                classification=str(x.get("classification") or "")
                no_public=classification in {"no_public_direct_tariff","no-public-direct-tariff"}
                rows.append({
                    "evseId":eid,
                    "normId":norm(eid),
                    "priority":priority,
                    "sourcePath":path,
                    "status":"no_public_direct_tariff" if no_public else "priced",
                    "tariff":compact(x),
                })
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(payload)
    # One best record per normalized id per source.
    d={}
    for r in rows: d.setdefault(r["normId"],r)
    return list(d.values())

def main():
    req=urllib.request.Request(NATIONAL_URL,headers={"User-Agent":"TCC-V9-Switzerland/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=120) as r:
        national_payload=json.load(r)
    national=extract_national(national_payload)

    candidates={}
    source_report=[]
    for path_s,priority in SOURCES:
        path=ROOT/path_s
        if not path.exists():
            source_report.append({"path":path_s,"priority":priority,"status":"missing"})
            continue
        try:
            payload=load(path)
        except Exception as e:
            source_report.append({"path":path_s,"priority":priority,"status":"invalid_json","error":str(e)[:300]})
            continue
        rows=extract_source(payload,path_s,priority)
        source_report.append({"path":path_s,"priority":priority,"status":"ok","candidateEvseCount":len(rows)})
        for row in rows:
            candidates.setdefault(row["normId"],[]).append(row)

    priced=no_public=unresolved=0
    joined=[]
    used_sources={}
    for ev in national:
        opts=sorted(candidates.get(norm(ev["evseId"]),[]),key=lambda x:x["priority"])
        chosen=opts[0] if opts else None
        if chosen:
            direct={
              "status":chosen["status"],
              "sourcePath":chosen["sourcePath"],
              "tariff":chosen["tariff"],
            }
            used_sources[chosen["sourcePath"]]=used_sources.get(chosen["sourcePath"],0)+1
            if chosen["status"]=="no_public_direct_tariff": no_public+=1
            else: priced+=1
        else:
            direct={"status":"unresolved","sourcePath":None,"tariff":None}
            unresolved+=1
        joined.append(ev|{"directTariff":direct})

    progress=load(ROOT/"docs/switzerland-cpo-progress-2026-09.json")
    operator_status={o.get("operatorId"):o.get("status") for o in progress.get("operators",[])}
    operator_setaside={o.get("operatorId"):bool(o.get("setAside")) for o in progress.get("operators",[])}

    payload={
      "schemaVersion":1,
      "dataset":"switzerland-public-charging-v9",
      "country":"CH",
      "generatedAt":datetime.now(timezone.utc).isoformat(),
      "baseInventory":{
        "source":NATIONAL_URL,
        "role":"authoritative physical EVSE/station inventory",
        "rule":"Every national EVSE remains visible even when direct CPO pricing is unresolved.",
      },
      "overlayPolicy":{
        "joinKey":"punctuation-insensitive normalized EVSE ID, only from validated production sources",
        "sourcePrecedence":"lower numeric priority wins",
        "noCrossStationExtrapolation":True,
        "unresolvedPriceKeepsEvseVisible":True,
        "blockedCpoDoesNotHideResolvedEvses":True,
        "roamingLayersSeparate":["Electra","Electroverse"],
        "teslaHandledSeparately":True,
      },
      "summary":{
        "nationalEvseCount":len(national),
        "directPricedEvseCount":priced,
        "classifiedNoPublicDirectTariffCount":no_public,
        "directUnresolvedEvseCount":unresolved,
        "directResolvedEvseCount":priced+no_public,
        "operatorStatusCounts":{},
      },
      "sourceReport":source_report,
      "usedSourceCounts":used_sources,
      "operatorProgress":{
        "statusByOperator":operator_status,
        "setAsideByOperator":operator_setaside,
      },
      "evses":joined,
    }
    for s in operator_status.values():
        payload["summary"]["operatorStatusCounts"][s]=payload["summary"]["operatorStatusCounts"].get(s,0)+1

    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    summary={
      "schemaVersion":1,
      "country":"CH",
      "dataset":payload["dataset"],
      "generatedAt":payload["generatedAt"],
      "output":str(OUT.relative_to(ROOT)),
      "summary":payload["summary"],
      "policy":payload["overlayPolicy"],
      "sourceReport":source_report,
      "usedSourceCounts":used_sources,
      "blockedOperators":[
        {"operatorId":o.get("operatorId"),"name":o.get("name"),"note":o.get("note")}
        for o in progress.get("operators",[]) if o.get("status")=="blocked"
      ],
      "note":"This is the V9 integration layer: national EVSE visibility is independent from direct-tariff completion. Resolved prices are joined per EVSE; unresolved prices remain null/unranked.",
    }
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary["summary"],ensure_ascii=False))

if __name__=="__main__":
    main()
