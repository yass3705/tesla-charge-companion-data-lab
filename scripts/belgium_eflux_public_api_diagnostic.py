#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.parse,urllib.request,urllib.error,re
from pathlib import Path

OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
BASE="https://api.e-flux.nl"

def fetch(path,query=None):
    url=BASE+path
    if query:url+="?"+urllib.parse.urlencode(query)
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"TCC-EFlux-public-diag/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            return getattr(r,"status",None),json.loads(r.read().decode("utf-8","replace"))
    except urllib.error.HTTPError as e:
        try:return e.code,json.loads(e.read().decode("utf-8","replace"))
        except:return e.code,{"error":"non-json"}
    except Exception as e:
        return 0,{"error":type(e).__name__+": "+str(e)}

def shape(x,depth=0):
    if depth>4:return type(x).__name__
    if isinstance(x,dict):
        return {k:shape(v,depth+1) for k,v in list(x.items())[:80]}
    if isinstance(x,list):
        return {"type":"list","count":len(x),"sampleShape":shape(x[0],depth+1) if x else None}
    return type(x).__name__

status,config=fetch("/1/map/config")
tests=[]
for name,path,q in [
 ("locations-empty","/1/map/locations",None),
 ("locations-viewport","/1/map/locations",{"north":"51.6","south":"49.4","east":"6.5","west":"2.5","zoom":"8"}),
 ("locations-bbox","/1/map/locations",{"bbox":"2.5,49.4,6.5,51.6"}),
 ("search-query","/2/locations/msp/search/fast",{"q":"BE*EFL*EV*0080612*C1"}),
 ("search-term","/2/locations/msp/search/fast",{"search":"BE*EFL*EV*0080612*C1"}),
]:
    st,obj=fetch(path,q)
    tests.append({"name":name,"status":st,"response":obj if isinstance(obj,dict) and set(obj.keys())<= {"error","message","code","errors"} else shape(obj)})

# Find config key paths containing useful terms; persist values only when simple and non-secret.
hits=[]
def walk(x,path=""):
    if isinstance(x,dict):
        for k,v in x.items():
            p=f"{path}.{k}" if path else k
            lk=p.lower()
            if any(t in lk for t in ("map","location","tariff","price","connector","search","bounds","zoom","filter")):
                if isinstance(v,(str,int,float,bool)) or v is None:
                    if "key" in p.lower() or "token" in p.lower() or "secret" in p.lower():
                        sv=str(v)
                        hits.append({"path":p,"value":{"redacted":True,"length":len(sv)}})
                    else:
                        hits.append({"path":p,"value":v})
                else:
                    hits.append({"path":p,"shape":shape(v)})
            walk(v,p)
    elif isinstance(x,list):
        for i,v in enumerate(x[:50]):walk(v,f"{path}[{i}]")
walk(config)

payload={
 "country":"BE","asOf":"2026-09-29","scope":"public unauthenticated E-Flux map API diagnostics",
 "config":{"status":status,"shape":shape(config),"interestingPaths":hits[:250]},
 "tests":tests,
 "policy":{"credentialsUsed":False,"authenticationBypassAttempted":False,"readOnly":True}
}
(OUT/"eflux-public-api-diagnostic-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
