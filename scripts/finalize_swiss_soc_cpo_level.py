#!/usr/bin/env python3
import json,gzip,urllib.request
from pathlib import Path
from datetime import datetime,timezone
NAT="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
SRC=Path("data/switzerland/soc-direct-tariffs.json")
OUT=Path("data/switzerland/soc-move-cpo-tariffs-national.json")
DOC=Path("docs/switzerland-soc-finalization-2026-09-28.json")
req=urllib.request.Request(NAT,headers={"User-Agent":"TCC-V9-Switzerland/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r: raw=r.read()
if len(raw)>=2 and raw[0]==31 and raw[1]==139: raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8")); src=json.loads(SRC.read_text(encoding="utf-8"))
schedules={}
for st in src.get("stations") or []:
 for cp in st.get("chargePoints") or []:
  for t in cp.get("directTariffs") or []:
   a=t.get("attributes") or {}; ta=t.get("tariff",{}).get("attributes") or {}
   cpo=(t.get("cpo") or {}).get("attributes",{}).get("name"); emp=(t.get("emp") or {}).get("attributes",{}).get("name")
   if a.get("tariff_level")!="cpo" or a.get("is_roaming") is not False or a.get("prices_per_station_available") is not False or cpo!="Move" or emp!="Move": continue
   seg=a.get("restricted_segments") or []
   if not any(x.get("dimension")=="kwh" and x.get("price") is not None for x in seg): continue
   schedules[(ta.get("name"),ta.get("total_monthly_fee"))]={"tariffName":ta.get("name"),"monthlyFee":ta.get("total_monthly_fee"),"currency":ta.get("currency"),"segments":seg}
atlas_types={}
for st in src.get("stations") or []:
  station_types=set()
  for cp in st.get("chargePoints") or []:
    cpt=cp.get("chargePoint") or {}; et=(cpt.get("energy_type") or "").lower()
    if et in ("ac","dc"): station_types.add(et)
    for aeid in cpt.get("evse_ids") or []:
      if et in ("ac","dc"): atlas_types.setdefault(aeid,set()).add(et)
  if len(station_types)==1:
    et=next(iter(station_types))
    for aeid in st.get("evseIds") or []: atlas_types.setdefault(aeid,set()).add(et)
current={}
def walk(x):
 if isinstance(x,dict):
  eid=x.get("EvseID")
  if isinstance(eid,str) and eid.startswith("CH*SOC*"): current[eid]=x
  for v in x.values(): walk(v)
 elif isinstance(x,list):
  for v in x: walk(v)
walk(nat)
rows=[]; unresolved=[]
for eid,rec in sorted(current.items()):
 types=set()
 for f in rec.get("ChargingFacilities") or []:
  pt=str(f.get("powertype") or "").lower()
  if "dc" in pt: types.add("dc")
  elif "ac" in pt: types.add("ac")
 if not types:
  plugs=" ".join(str(x) for x in rec.get("Plugs") or []).lower()
  if "chademo" in plugs or "ccs" in plugs or "combo" in plugs: types.add("dc")
  if "type 2" in plugs: types.add("ac")
 if not types and len(atlas_types.get(eid,set()))==1:
  types.update(atlas_types[eid])
 applicable=[]
 for sch in schedules.values():
  matched=[x for x in sch["segments"] if x.get("dimension")=="kwh" and (x.get("charge_point_energy_type") or "").lower() in types]
  if matched: applicable.append({**sch,"matchedKwhSegments":matched})
 if applicable: rows.append({"evseId":eid,"tariffs":applicable})
 else: unresolved.append({"evseId":eid,"reason":"no_explicit_move_cpo_segment_for_evse_type","types":sorted(types)})
now=datetime.now(timezone.utc).isoformat()
payload={"schemaVersion":1,"country":"CH","cpo":"SOCAR / Move charging backend","operatorId":"CH*SOC","generatedAt":now,"nationalEvseCount":len(current),"pricedEvseCount":len(rows),"unresolvedEvseCount":len(unresolved),"tariffSchedules":list(schedules.values()),"policy":"Apply only explicit non-roaming Move CPO-level tariffs with prices_per_station_available=false, matched to each current CH*SOC EVSE's AC/DC type. No station-specific price extrapolation.","evses":rows,"unresolved":unresolved}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
final={k:payload[k] for k in ["schemaVersion","country","cpo","operatorId","nationalEvseCount","pricedEvseCount","unresolvedEvseCount","policy"]}
final.update({"status":"complete" if not unresolved else "partial","updatedAt":now,"method":"Current national CH*SOC EVSE-prefix scope + explicit Move non-roaming CPO-level tariff schedules, exact AC/DC matching","productionSource":str(OUT)})
DOC.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
