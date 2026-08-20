#!/usr/bin/env python3
"""Read-only EVGO/AMPECO public station-search probe.

Uses only the already-confirmed mobile search routes and the public station name
"Marjane Mohammedia" as the required search query. No login, credentials,
mutation, charging/payment action or raw response persistence.
"""
from __future__ import annotations
import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST="evgo.eu-evgo.charge.ampeco.tech"
PATHS=["/api/v1/app/evses/search","/api/v2/app/evses/search"]
QUERY="Marjane Mohammedia"
OUT=Path("artifacts/morocco-evgo-public-search")
UA="Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.4)"
SAFE_KEYS=("id","name","title","status","availability","occupied","available","power","kw","connector","evse","location","address","city","latitude","longitude","lat","lng","tariff","price","currency","free","operator","network")
SENSITIVE=("user","email","phone","account","payment","card","token","secret","auth","cookie")

def keep_key(k:str)->bool:
 s=k.lower()
 return not any(x in s for x in SENSITIVE) and any(x in s for x in SAFE_KEYS)

def safe(v,depth=0):
 if depth>6:return None
 if isinstance(v,dict):
  out={}
  for k,x in v.items():
   ks=str(k)
   if keep_key(ks):
    y=safe(x,depth+1)
    if y not in (None,{},[]):out[ks]=y
   elif isinstance(x,(dict,list)):
    y=safe(x,depth+1)
    if y not in (None,{},[]):out[ks]=y
  return out
 if isinstance(v,list): return [y for x in v[:20] if (y:=safe(x,depth+1)) not in (None,{},[])]
 if isinstance(v,(int,float,bool)) or v is None:return v
 if isinstance(v,str): return v[:300] if len(v)<=300 else None
 return None

def probe(path):
 qs=urllib.parse.urlencode({"query":QUERY})
 url=f"https://{HOST}{path}?{qs}"
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"},method="GET")
 try:
  with urllib.request.urlopen(req,timeout=20) as r: status=r.status;ctype=r.headers.get("content-type","");body=r.read(200000)
 except urllib.error.HTTPError as e:
  status=e.code;ctype=e.headers.get("content-type","") if e.headers else "";body=e.read(200000)
 except Exception as e:return {"path":path,"status":None,"error":type(e).__name__}
 out={"path":path,"status":status,"content_type":ctype}
 if "json" in ctype.lower() and body:
  try:
   obj=json.loads(body.decode("utf-8","replace"));out["public_charging_data"]=safe(obj)
   if isinstance(obj,dict):out["top_level_keys"]=[str(k) for k in obj.keys() if not any(x in str(k).lower() for x in SENSITIVE)][:40]
  except Exception:out["json_parse"]="failed"
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 result={"schema_version":1,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"host":HOST,"query":QUERY,"policy":{"read_only":True,"no_login":True,"no_mutations":True,"no_credentials":True,"raw_response_bodies_persisted":False},"probes":[probe(p) for p in PATHS]}
 (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"statuses":[x.get("status") for x in result["probes"]]}))
if __name__=="__main__":main()
