#!/usr/bin/env python3
"""Read-only EVGO/AMPECO location-route validation probe.

Tests only route existence/validation shape for public mobile location endpoints discovered
in the EVGO Android client. No login, credentials, mutation, charging/payment action,
query strings, or raw response persistence.
"""
from __future__ import annotations
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOST="evgo.eu-evgo.charge.ampeco.tech"
PATHS=[
    "/api/v1/app/locations/withEVSE",
    "/api/v2/app/locations/withEVSE",
    "/api/v1/app/locations/withEVSEIdentifier",
    "/api/v2/app/locations/withEVSEIdentifier",
    "/api/v1/app/locations",
    "/api/v2/app/locations",
]
OUT=Path("artifacts/morocco-evgo-location-validation")
UA="Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.7)"
SENSITIVE=("token","secret","auth","cookie","user","email","phone","account","payment","card")
SAFE_ERROR_KEYS=("message","errors","error","detail","fields")

def scrub(v,depth=0):
    if depth>4:return None
    if isinstance(v,dict):
        out={}
        for k,x in v.items():
            ks=str(k); low=ks.lower()
            if any(s in low for s in SENSITIVE):continue
            if low in SAFE_ERROR_KEYS or isinstance(x,(dict,list)):
                y=scrub(x,depth+1)
                if y not in (None,{},[]):out[ks]=y
        return out
    if isinstance(v,list):return [y for x in v[:20] if (y:=scrub(x,depth+1)) not in (None,{},[])]
    if isinstance(v,str):return v[:500]
    if isinstance(v,(int,float,bool)) or v is None:return v
    return None

def probe(path):
    url=f"https://{HOST}{path}"
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"},method="GET")
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            status=r.status; ctype=r.headers.get("content-type",""); body=r.read(120000)
    except urllib.error.HTTPError as e:
        status=e.code; ctype=e.headers.get("content-type","") if e.headers else ""; body=e.read(120000)
    except Exception as e:
        return {"path":path,"status":None,"error_type":type(e).__name__}
    out={"path":path,"status":status,"content_type":ctype}
    if "json" in ctype.lower() and body:
        try:
            obj=json.loads(body.decode("utf-8","replace"))
            out["safe_validation_shape"]=scrub(obj)
            if isinstance(obj,dict):
                out["top_level_keys"]=[str(k) for k in obj if not any(s in str(k).lower() for s in SENSITIVE)][:40]
        except Exception:
            out["json_parse"]="failed"
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={
        "schema_version":1,
        "generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "host":HOST,
        "policy":{"read_only":True,"no_login":True,"no_mutations":True,"no_credentials":True,"query_strings_used":False,"raw_response_bodies_persisted":False},
        "probes":[probe(p) for p in PATHS],
    }
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"statuses":[x.get("status") for x in result["probes"]]}))
if __name__=="__main__":main()
