#!/usr/bin/env python3
"""Read-only EVGO/AMPECO public station-search probe.

Uses only already-confirmed public mobile search routes on the branded EVGO
backend plus public place-name or public EVSE-label queries. No login,
credentials, mutation, charging/payment action or raw response persistence.
The report keeps only charging-infrastructure fields plus harmless result-shape
metadata.
"""
from __future__ import annotations
import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST="cp.evgo.ma"
PATHS=["/api/v1/app/evses/search","/api/v2/app/evses/search"]
# Include both native-app place names and a couple of public labels observed via
# EVOne, to determine whether this endpoint searches places or EVSE identifiers.
QUERIES=[
 "Marjane Mohammedia","Marjane","Mohammedia",
 "Marjane Ain Sebaa","Ain Sebaa","Casablanca","1004","1005"
]
OUT=Path("artifacts/morocco-evgo-public-search")
UA="Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.7)"
SAFE_KEYS=("id","name","title","status","availability","occupied","available","power","kw","connector","evse","location","address","city","latitude","longitude","lat","lng","tariff","price","currency","free","operator","network")
SENSITIVE=("user","email","phone","account","payment","card","token","secret","auth","cookie")

def keep_key(k:str)->bool:
 s=k.lower()
 return not any(x in s for x in SENSITIVE) and any(x in s for x in SAFE_KEYS)

def safe(v,depth=0):
 if depth>7:return None
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
 if isinstance(v,list):
  return [y for x in v[:25] if (y:=safe(x,depth+1)) not in (None,{},[])]
 if isinstance(v,(int,float,bool)) or v is None:return v
 if isinstance(v,str): return v[:300] if len(v)<=300 else None
 return None

def result_shape(obj):
 out={}
 if not isinstance(obj,dict):return out
 results=obj.get("results")
 if isinstance(results,list):
  out["result_count"]=len(results)
  if results and isinstance(results[0],dict):
   out["first_result_keys"]=[str(k) for k in results[0].keys() if not any(x in str(k).lower() for x in SENSITIVE)][:60]
 elif isinstance(results,dict):
  out["result_container_type"]="object"
  out["result_container_keys"]=[str(k) for k in results.keys() if not any(x in str(k).lower() for x in SENSITIVE)][:60]
 return out

def probe(path,query):
 qs=urllib.parse.urlencode({"query":query})
 url=f"https://{HOST}{path}?{qs}"
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"},method="GET")
 try:
  with urllib.request.urlopen(req,timeout=20) as r: status=r.status;ctype=r.headers.get("content-type","");body=r.read(300000)
 except urllib.error.HTTPError as e:
  status=e.code;ctype=e.headers.get("content-type","") if e.headers else "";body=e.read(300000)
 except Exception as e:return {"path":path,"query":query,"status":None,"error":type(e).__name__}
 out={"path":path,"query":query,"status":status,"content_type":ctype}
 if "json" in ctype.lower() and body:
  try:
   obj=json.loads(body.decode("utf-8","replace"))
   out.update(result_shape(obj))
   out["public_charging_data"]=safe(obj)
   if isinstance(obj,dict):out["top_level_keys"]=[str(k) for k in obj.keys() if not any(x in str(k).lower() for x in SENSITIVE)][:40]
  except Exception:out["json_parse"]="failed"
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 probes=[probe(path,query) for query in QUERIES for path in PATHS]
 result={"schema_version":4,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"host":HOST,"queries":QUERIES,"policy":{"read_only":True,"no_login":True,"no_mutations":True,"no_credentials":True,"raw_response_bodies_persisted":False},"probes":probes}
 (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"statuses":[x.get("status") for x in probes],"result_counts":[x.get("result_count") for x in probes]}))
if __name__=="__main__":main()
