#!/usr/bin/env python3
"""Preserved inline Eco-Movement PCPR collector from G1 workflow archive."""
import os,json,time,urllib.request,urllib.parse,urllib.error,gzip
from pathlib import Path
from datetime import datetime,timezone

token=os.environ.get("ECO_MOVEMENT_PCPR_TOKEN","").strip()
if not token:
    raise SystemExit("ECO_MOVEMENT_PCPR_TOKEN missing")

BASE="https://open-chargepoints.com/api/ocpi/cpo/2.2.1"
STATUS_URL="https://open-chargepoints.com/api/statuses"
UA="TeslaChargeCompanion/9 Eco-Movement-PCPR"
headers={"Authorization":"Token "+token,"Accept":"application/json","User-Agent":UA}

def get_json(url,timeout=60):
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        body=r.read()
        return r.status,dict(r.headers.items()),json.loads(body.decode("utf-8"))

def page(endpoint,limit=1000):
    out=[]; offset=0
    while True:
        q=urllib.parse.urlencode({"limit":limit,"offset":offset})
        st,h,j=get_json(f"{BASE}/{endpoint}?{q}")
        if st!=200: raise RuntimeError(f"{endpoint} HTTP {st}")
        data=j.get("data") if isinstance(j,dict) else None
        if data is None: data=[]
        if isinstance(data,dict): data=[data]
        out.extend(data)
        if len(data)<limit: break
        offset+=len(data)
        time.sleep(.25)
    return out

locations=page("locations")
tariffs=page("tariffs")

status_http,status_headers,status_json=get_json(STATUS_URL)
statuses=status_json.get("data") if isinstance(status_json,dict) else status_json
if statuses is None: statuses=[]
if isinstance(statuses,dict): statuses=[statuses]

def names(loc):
    vals=[]
    for k in ("operator","owner","suboperator"):
        x=loc.get(k)
        if isinstance(x,dict):
            if x.get("name"): vals.append(x.get("name"))
            for e in x.get("ema_id") or []: vals.append(e)
    return [str(v) for v in vals if v]

target_terms={
  "Blink":["blink"],
  "bp pulse":["bp pulse","chargemaster","bpc","bpp","bpt"],
  "Source EV":["source ev","sourceev"],
  "ubitricity":["ubitricity"],
  "Shell Recharge":["shell recharge","shell"],
  "evyve":["evyve"],
  "ChargePoint CMS":["chargepoint"],
  "InstaVolt":["instavolt"],
  "ev-point":["ev-point","ev point"]
}

operator_hits={k:{"locations":0,"sampleNames":set(),"sampleIds":[]} for k in target_terms}
for loc in locations:
    hay=" | ".join(names(loc)).lower()
    for label,terms in target_terms.items():
        if any(t in hay for t in terms):
            h=operator_hits[label]
            h["locations"]+=1
            h["sampleNames"].update(names(loc))
            if len(h["sampleIds"])<10: h["sampleIds"].append(loc.get("id"))

for v in operator_hits.values():
    v["sampleNames"]=sorted(v["sampleNames"])[:20]

now=datetime.now(timezone.utc).isoformat()
payload={"retrievedAt":now,"source":"Eco-Movement PCPR","locations":locations,"tariffs":tariffs,"statuses":statuses}
with gzip.open("data/national/uk_eco_movement_pcpr.json.gz","wt",encoding="utf-8") as g:
    json.dump(payload,g,ensure_ascii=False,separators=(",",":"))

report={
  "retrievedAt":now,
  "locationCount":len(locations),
  "tariffCount":len(tariffs),
  "statusCount":len(statuses),
  "operatorHits":operator_hits
}
Path("reports/uk/eco-movement-pcpr-latest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2))
