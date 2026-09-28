#!/usr/bin/env python3
from __future__ import annotations
import json, os, time, urllib.parse, urllib.request
from pathlib import Path

BASE="https://nap-be.eco-movement.com/datex2/v1/locations"
TOKEN=os.environ["BELGIUM_NAP_TOKEN"].strip()

def fetch(offset):
    qs=urllib.parse.urlencode({"limit":1000,"offset":offset})
    req=urllib.request.Request(BASE+"?"+qs,headers={
      "Authorization":f"Bearer {TOKEN}",
      "Accept":"application/json",
      "User-Agent":"tesla-charge-companion-data-lab/1.0",
    })
    with urllib.request.urlopen(req,timeout=180) as resp:
        payload=json.loads(resp.read())
        headers={k:v for k,v in resp.headers.items() if k.lower() in {
          "link","x-total-count","x-total","content-range","x-next-offset"
        }}
        return payload,headers

def sites(payload):
    try:
        return payload["aegiEnergyInfrastructureTablePublication"]["energyInfrastructureTable"][0]["energyInfrastructureSite"]
    except Exception:
        return []

out=[]
for i,off in enumerate((0,1000,2000)):
    if i: time.sleep(11)
    p,h=fetch(off)
    s=sites(p)
    out.append({
      "offset":off,"count":len(s),"firstId":s[0].get("idG") if s else None,
      "lastId":s[-1].get("idG") if s else None,"headers":h
    })
Path("reports").mkdir(exist_ok=True)
Path("reports/belgium-pagination-probe-2026-09-28.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
