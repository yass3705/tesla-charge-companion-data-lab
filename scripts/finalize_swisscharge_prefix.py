#!/usr/bin/env python3
import json,gzip,urllib.request
from pathlib import Path
from datetime import datetime,timezone
SRC=Path("data/swisscharge/swisscharge-tariffs.json")
NAT="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
DOC=Path("docs/switzerland-swisscharge-prefix-closeout-2026-09-28.json")
s=json.loads(SRC.read_text(encoding="utf-8"))
req=urllib.request.Request(NAT,headers={"User-Agent":"TCC-V9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if len(raw)>=2 and raw[0]==31 and raw[1]==139: raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
records={}
def walk(x):
 if isinstance(x,dict):
  eid=x.get("EvseID")
  if isinstance(eid,str) and eid.startswith("CH*SUI*E"): records[eid]=x
  for v in x.values(): walk(v)
 elif isinstance(x,list):
  for v in x: walk(v)
walk(nat)
resolved={x.get("physicalReference") for x in s.get("evses",[]) if x.get("physicalReference")}
un=s.get("unresolved") or []
classified=[]; remaining=[]
for x in un:
 ref=str(x.get("physicalReference") or "")
 eid="CH*SUI*E"+ref
 rec=records.get(eid)
 if rec and str(rec.get("Accessibility") or "").lower().startswith("restricted") and not (rec.get("AuthenticationModes") or []):
  classified.append({"evseId":eid,"physicalReference":ref,"classification":"no_public_direct_tariff","reason":"restricted_access_and_no_authentication_modes"})
 else:
  remaining.append({"evseId":eid,"physicalReference":ref,"collectorReason":x.get("reason"),"httpStatus":x.get("httpStatus"),"nationalRecord":rec})
now=datetime.now(timezone.utc).isoformat()
out={"schemaVersion":1,"country":"CH","cpo":"Swisscharge","operatorId":"CH*SUI","status":"complete" if not remaining else "partial","updatedAt":now,"nationalPrefixEvseCount":len(records),"pricedEvseCount":len(resolved),"classifiedNoPublicDirectTariffCount":len(classified),"unresolvedEvseCount":len(remaining),"method":"Existing Swisscharge direct tariff collection for CH*SUI prefix + explicit national restricted/no-auth classification","policy":"CH*SUI EVSE-prefix scope is the tariff scope. National CH*SUI owner records with non-SUI prefixes were separately tested against the Swisscharge direct endpoint and returned 404, so they are not imported into Swisscharge tariff scope. No tariff extrapolation.","classified":classified,"unresolved":remaining}
DOC.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({k:v for k,v in out.items() if k not in ("classified","unresolved")}|{"unresolvedSample":remaining[:20]},ensure_ascii=False,indent=2))
