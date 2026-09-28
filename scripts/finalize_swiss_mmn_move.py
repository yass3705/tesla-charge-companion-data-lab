#!/usr/bin/env python3
import json,gzip,urllib.request
from pathlib import Path
from datetime import datetime,timezone
NAT="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
SRC=Path("data/switzerland/cci-direct-tariffs-second-pass.json")
OUT=Path("data/switzerland/mmn-move-cpo-tariffs.json")
DOC=Path("docs/switzerland-mmn-finalization-2026-09-28.json")
req=urllib.request.Request(NAT,headers={"User-Agent":"TCC-V9-Switzerland/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r: raw=r.read()
if len(raw)>=2 and raw[0]==31 and raw[1]==139: raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8")); src=json.loads(SRC.read_text(encoding="utf-8"))
schedules=[]
seen=set()
for st in src.get("stations") or []:
 for cp in st.get("chargePoints") or []:
  for t in cp.get("directTariffs") or []:
   a=t.get("attributes") or {}; ta=t.get("tariff",{}).get("attributes") or {}
   cpo=(t.get("cpo") or {}).get("attributes",{}).get("name"); emp=(t.get("emp") or {}).get("attributes",{}).get("name")
   if a.get("tariff_level")!="cpo" or a.get("is_roaming") is not False or a.get("prices_per_station_available") is not False or cpo!="Move" or emp!="Move": continue
   seg=a.get("restricted_segments") or []
   ac=[x for x in seg if x.get("dimension")=="kwh" and (x.get("charge_point_energy_type") or "").lower()=="ac" and x.get("price") is not None]
   if not ac: continue
   key=(ta.get("name"),ta.get("total_monthly_fee"))
   if key not in seen:
    seen.add(key); schedules.append({"tariffName":ta.get("name"),"monthlyFee":ta.get("total_monthly_fee"),"currency":ta.get("currency"),"segments":seg,"matchedKwhSegments":ac})
current={}
def walk(x):
 if isinstance(x,dict):
  eid=x.get("EvseID")
  if isinstance(eid,str) and eid.startswith("CH*MMN*"): current[eid]=x
  for v in x.values(): walk(v)
 elif isinstance(x,list):
  for v in x: walk(v)
walk(nat)
rows=[]; unresolved=[]
for eid,rec in sorted(current.items()):
 fac=rec.get("ChargingFacilities") or []
 is_ac=any("ac" in str(f.get("powertype") or "").lower() for f in fac)
 if is_ac and schedules: rows.append({"evseId":eid,"tariffs":schedules})
 else: unresolved.append({"evseId":eid,"reason":"not_deterministically_ac_or_missing_move_ac_schedule"})
now=datetime.now(timezone.utc).isoformat()
payload={"schemaVersion":1,"country":"CH","cpo":"MOVE Mobility / myNet","operatorId":"CH*MMN","status":"complete" if not unresolved else "partial","updatedAt":now,"nationalEvseCount":len(current),"pricedEvseCount":len(rows),"unresolvedEvseCount":len(unresolved),"method":"Current CH*MMN EVSE-prefix scope (nationally nested under Move) + explicit Move non-roaming CPO-level AC tariffs","policy":"CH*MMN current national records are nested under Move, advertise Direct Payment, and are AC. Apply only explicit Move CPO-level AC tariff schedules where prices_per_station_available=false.","evses":rows,"unresolved":unresolved}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); DOC.write_text(json.dumps({k:v for k,v in payload.items() if k not in ("evses","unresolved")},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in payload.items() if k not in ("evses","unresolved")},ensure_ascii=False,indent=2))
