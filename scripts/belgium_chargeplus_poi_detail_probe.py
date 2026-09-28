#!/usr/bin/env python3
import json, urllib.parse, urllib.request, urllib.error, math
from pathlib import Path

BASE="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2"
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)

target={"label":"TotalEnergies Boom","latitude":51.099934,"longitude":4.368176,"napLocationId":"TotalEnergies-MOW-BOOM","napEvseId":"CU-MOW-BOOM-001-1","externalId":"BE*TCB*E800372"}

def get(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read().decode("utf-8","replace")
            return {"status":r.status,"contentType":r.headers.get("content-type"),"body":body}
    except urllib.error.HTTPError as e:
        return {"status":e.code,"contentType":e.headers.get("content-type"),"body":e.read().decode("utf-8","replace")}
    except Exception as e:
        return {"status":0,"error":type(e).__name__+": "+str(e),"body":""}

q=urllib.parse.urlencode({"latitude":target["latitude"],"longitude":target["longitude"],"poiType":2,"radius":2})
collection=get(BASE+"/pois?"+q)
pois=[]
if collection["status"]==200:
    try:
        payload=json.loads(collection["body"]); pois=payload.get("data") or []
    except Exception: pass

def dist(p):
    return (float(p.get("latitude",0))-target["latitude"])**2+(float(p.get("longitude",0))-target["longitude"])**2
pois=sorted(pois,key=dist)[:8]

details=[]
for p in pois:
    pid=str(p.get("id") or "")
    variants=[
      BASE+"/pois/2-"+urllib.parse.quote(pid,safe="")+"/details",
      BASE+"/pois/2-"+urllib.parse.quote(pid.removeprefix("BEMO-"),safe="")+"/details",
    ]
    item={"poiSummary":p,"tests":[]}
    for u in dict.fromkeys(variants):
        r=get(u)
        rec={"url":u,"status":r["status"],"contentType":r.get("contentType")}
        if r.get("body"):
            rec["body"]=r["body"][:50000]
        if r.get("error"):rec["error"]=r["error"]
        item["tests"].append(rec)
    details.append(item)

report={"target":target,"collection":{"status":collection["status"],"count":len(pois)},"details":details}
(OUT/"chargeplus-poi-detail-probe-2026-09-28.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({
 "target":target,
 "collectionStatus":collection["status"],
 "nearest":[{"id":p.get("id"),"lat":p.get("latitude"),"lon":p.get("longitude")} for p in pois],
 "detailStatuses":[{"id":d["poiSummary"].get("id"),"statuses":[x["status"] for x in d["tests"]]} for d in details]
},ensure_ascii=False,indent=2))
