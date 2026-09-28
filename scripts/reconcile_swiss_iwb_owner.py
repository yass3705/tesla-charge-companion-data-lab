#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
DATA=Path("data/switzerland/iwb-direct-tariffs-second-pass.json")
OWNER="CH*IWB"
req=urllib.request.Request(NATIONAL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
owned={}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip(): owner=x["OperatorID"].strip()
        eid=x.get("EvseID")
        if owner==OWNER and isinstance(eid,str) and eid.strip(): owned[eid.strip()]=x
        for v in x.values():walk(v,owner)
    elif isinstance(x,list):
        for v in x:walk(v,owner)
walk(nat)
atlas=json.loads(DATA.read_text(encoding="utf-8"))
priced=set();seen=set()
for st in atlas.get("stations",[]):
    for eid in st.get("evseIds") or []:
        if isinstance(eid,str):seen.add(eid)
    for cp in st.get("chargePoints",[]):
        ids=(cp.get("chargePoint") or {}).get("evse_ids") or []
        if cp.get("directTariffs"):
            priced.update(i for i in ids if isinstance(i,str))
rows=[];classes={"priced_exact":[],"restricted_no_auth":[],"public_unpriced":[],"owner_not_seen_in_atlas":[]}
for eid,d in sorted(owned.items()):
    if eid in priced:
        cl="priced_exact"
    elif d.get("Accessibility")=="Restricted access" and not (d.get("AuthenticationModes") or []):
        cl="restricted_no_auth"
    elif eid not in seen:
        cl="owner_not_seen_in_atlas"
    else:
        cl="public_unpriced"
    row={"evseId":eid,"classification":cl,"accessibility":d.get("Accessibility"),
         "authenticationModes":d.get("AuthenticationModes"),"paymentOptions":d.get("PaymentOptions"),
         "stationId":d.get("ChargingStationId"),"address":d.get("Address"),"names":d.get("ChargingStationNames"),
         "chargingFacilities":d.get("ChargingFacilities")}
    rows.append(row);classes[cl].append(row)
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"operatorId":OWNER,"nationalOwnerEvseCount":len(owned),
     "atlasSeenCurrentOwnerEvseCount":len(set(owned)&seen),"pricedExactCurrentOwnerEvseCount":len(set(owned)&priced),
     "classCounts":{k:len(v) for k,v in classes.items()},"classes":classes}
Path("docs/switzerland-iwb-owner-reconciliation-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:v for k,v in out.items() if k!="classes"},ensure_ascii=False,indent=2))
