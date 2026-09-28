#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
ECAR=Path("data/switzerland/ecarup-public-stations.json")
TARGETS={"CH*EWO","CH*EBS","CH*EWD","CH*EVT","CH*EPO","CH*EDH","CH*AIL","CH*HER","CH*DIE"}
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
ec=json.loads(ECAR.read_text(encoding="utf-8"))

# Exact eCarUp Hubject EVSE index.
idx=defaultdict(list)
for st in ec.get("stations",[]):
    for c in st.get("Connectors") or []:
        hid=((c.get("Hubject") or {}).get("ID"))
        if isinstance(hid,str) and hid.strip():
            idx[hid.strip()].append({"stationId":st.get("ID"),"stationName":st.get("Name"),"address":st.get("Address"),
                                     "latitude":st.get("Latitude"),"longitude":st.get("Longitude"),
                                     "operatorName":((st.get("ContactDetails") or {}).get("OperatorName")),
                                     "connectorId":c.get("Id"),"deviceId":c.get("DeviceID"),"plugType":c.get("PlugType"),
                                     "maxPowerW":c.get("MaxPower"),"price":c.get("Price"),"state":c.get("State")})

# Collect EVSE records by official owner OperatorID, not by EVSE prefix.
owned=defaultdict(dict)
def collect_records(x, owner=None):
    if isinstance(x,dict):
        newowner=owner
        if isinstance(x.get("OperatorID"),str):
            newowner=x["OperatorID"]
        eid=x.get("EvseID")
        if newowner in TARGETS and isinstance(eid,str):
            owned[newowner][eid]=x
        for v in x.values(): collect_records(v,newowner)
    elif isinstance(x,list):
        for v in x: collect_records(v,owner)
collect_records(nat)

results={}
for op in sorted(TARGETS):
    evs=owned.get(op,{})
    matched=[]; unresolved=[]; ambiguous=[]
    for eid,d in sorted(evs.items()):
        cand=idx.get(eid,[])
        if len(cand)==1:
            c=cand[0]; price=c.get("price") or {}
            matched.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),
                            "nationalAddress":d.get("Address"),"nationalGeo":d.get("GeoCoordinates"),
                            "ecarup":c,
                            "tariff":{"energyPrice":price.get("EnergyPrice"),"parkingPrice":price.get("ParkingPrice"),
                                      "specialUserEnergyPrice":price.get("SpecialUserEnergyPrice"),
                                      "specialUserParkingPrice":price.get("SpecialUserParkingPrice"),
                                      "penaltyGracePeriodMinutes":price.get("PenaltyGracePeriodMinutes"),
                                      "penaltyPricePerMinute":price.get("PenaltyPricePerMinute"),
                                      "penaltyMaxFee":price.get("PenaltyMaxFee"),"currency":price.get("Currency")}})
        elif len(cand)>1:
            ambiguous.append({"evseId":eid,"candidateCount":len(cand),"candidates":cand})
        else:
            unresolved.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"address":d.get("Address"),"geo":d.get("GeoCoordinates"),
                               "power":d.get("ChargingFacilities"),"plugs":d.get("Plugs")})
    results[op]={"nationalEvseCount":len(evs),"exactHubjectMatchCount":len(matched),
                 "unresolvedCount":len(unresolved),"ambiguousCount":len(ambiguous),
                 "coveragePct":round(100*len(matched)/len(evs),3) if evs else 0,
                 "status":"complete" if evs and len(matched)==len(evs) and not ambiguous else "partial",
                 "matched":matched,"unresolved":unresolved,"ambiguous":ambiguous}

out={"schemaVersion":1,"country":"CH","generatedAt":datetime.now(timezone.utc).isoformat(),
     "nationalSource":NATIONAL,"ecarupSource":"data/switzerland/ecarup-public-stations.json",
     "policy":"Exact national EvseID to eCarUp public connector Hubject.ID only. No coordinate fallback and no tariff extrapolation in this stage.",
     "operators":results}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-ecarup-exact-national-reconciliation-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{k:v for k,v in d.items() if k not in ("matched","unresolved","ambiguous")} for op,d in results.items()},ensure_ascii=False,indent=2))
