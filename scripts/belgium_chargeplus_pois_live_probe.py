#!/usr/bin/env python3
import json, urllib.parse, urllib.request, urllib.error
from pathlib import Path

BASE="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2/pois"
OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)

tests=[
 ("none",{}),
 ("latlon",{"latitude":"51.260","longitude":"4.220"}),
 ("fromlatlon",{"fromLatitude":"51.260","fromLongitude":"4.220"}),
 ("latlonradius",{"latitude":"51.260","longitude":"4.220","radius":"10"}),
 ("fromlatlonradius",{"fromLatitude":"51.260","fromLongitude":"4.220","radius":"10"}),
 ("country",{"countryCode":"BE"}),
]
paths=[
 ("collection",BASE),
 ("nap_station",BASE+"/BEDEC-VRAS"),
 ("nap_location",BASE+"/TotalEnergies-BEDEC-VRAS"),
]
res=[]
def get(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return {"status":r.status,"contentType":r.headers.get("content-type"),"body":r.read().decode("utf-8","replace")[:30000]}
    except urllib.error.HTTPError as e:
        return {"status":e.code,"contentType":e.headers.get("content-type"),"body":e.read().decode("utf-8","replace")[:30000]}
    except Exception as e:
        return {"status":0,"error":type(e).__name__+": "+str(e)}

for label,params in tests:
    url=BASE+("?" + urllib.parse.urlencode(params) if params else "")
    res.append({"label":label,"url":url,**get(url)})
for label,url in paths[1:]:
    res.append({"label":label,"url":url,**get(url)})

payload={"base":BASE,"results":res}
(OUT/"chargeplus-pois-live-probe-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps([{"label":x["label"],"status":x["status"],"body":x.get("body","")[:1200]} for x in res],ensure_ascii=False,indent=2))
