#!/usr/bin/env python3
import gzip,json,time,urllib.request,urllib.parse,urllib.error,http.cookiejar
from pathlib import Path
from datetime import datetime,timezone
FEED="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
BASE="https://adhoc.swisscharge.ch"; TENANT="Swisscharge_CH"; UA="Mozilla/5.0 TCC-V9"
req=urllib.request.Request(FEED,headers={"User-Agent":UA,"Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if len(raw)>=2 and raw[0]==31 and raw[1]==139: raw=gzip.decompress(raw)
feed=json.loads(raw.decode("utf-8"))
refs=[]
def walk(x,owner=None):
 if isinstance(x,dict):
  if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
  eid=x.get("EvseID")
  if owner=="CH*SUI" and isinstance(eid,str) and not eid.startswith("CH*SUI*"): refs.append(eid)
  for v in x.values(): walk(v,owner)
 elif isinstance(x,list):
  for v in x: walk(v,owner)
walk(feed)
refs=list(dict.fromkeys(refs))
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def get(url,headers=None):
 req=urllib.request.Request(url,headers=headers or {},method="GET")
 try:
  with op.open(req,timeout=35) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
results=[]; unresolved=[]
for i,ref in enumerate(refs,1):
 page=f"{BASE}/tenant/{TENANT}/session-start/{urllib.parse.quote(ref,safe='')}"
 api=f"{BASE}/api/v1/charge-points?evsePhysicalReference={urllib.parse.quote(ref,safe='')}"
 get(page,{"User-Agent":UA})
 st,raw=get(api,{"Accept":"application/json","Tenant":TENANT,"tenant-path":page,"Referer":page,"User-Agent":UA})
 if st==200:
  try:
   p=json.loads(raw.decode("utf-8")); data=p.get("data") or {}; evses=data.get("evses") or []
   ev=next((e for e in evses if str(e.get("physicalReference"))==ref),evses[0] if evses else {})
   tariff=ev.get("tariff") or {}; pricing=tariff.get("pricing") or {}; restrictions=tariff.get("restrictions") or {}
   if tariff.get("id") is not None:
    results.append({"evseId":ref,"tariff":{"id":tariff.get("id"),"name":tariff.get("name"),"currency":tariff.get("currency"),"pricing":pricing,"restrictions":restrictions}})
   else: unresolved.append({"evseId":ref,"reason":"no_tariff"})
  except Exception as e: unresolved.append({"evseId":ref,"reason":"parse_error","error":str(e)})
 else: unresolved.append({"evseId":ref,"reason":"http_error","status":st,"body":raw.decode("utf-8","replace")[:300]})
 time.sleep(.75)
out={"schemaVersion":1,"country":"CH","operatorId":"CH*SUI","generatedAt":datetime.now(timezone.utc).isoformat(),"nonCanonicalOwnerEvseCount":len(refs),"resolvedTariffEvseCount":len(results),"unresolvedEvseCount":len(unresolved),"evses":results,"unresolved":unresolved}
Path("data/switzerland/swisscharge-owner-noncanonical-tariffs.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-swisscharge-owner-noncanonical-2026-09-28.json").write_text(json.dumps({k:v for k,v in out.items() if k not in ("evses","unresolved")}|{"unresolved":unresolved},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k not in ("evses","unresolved")}|{"unresolved":unresolved},ensure_ascii=False,indent=2))
