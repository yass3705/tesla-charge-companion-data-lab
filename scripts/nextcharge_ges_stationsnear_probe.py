#!/usr/bin/env python3
import json, requests
from pathlib import Path

BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
OUT=Path("data/reports/nextcharge_ges_stationsnear_probe.json")

samples=[
 ("rome",41.9028,12.4964),
 ("milan",45.4642,9.1900),
 ("bologna",44.4949,11.3426),
]

def post(path,data):
    try:
        r=requests.post(BASE+path,data=data,headers={"User-Agent":"NextCharge/6.2.02 Android","Content-Type":"application/x-www-form-urlencoded"},timeout=(8,20))
        row={"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:1000]
        return row
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}

rows=[]
for name,lat,lon in samples:
    base={
      "latitude":str(lat),
      "longitude":str(lon),
      "limit":"20",
      "includeHighway":"1",
      "includeNextcharge":"1",
      "favorites":"0",
    }
    variants=[
      ("plain",base),
      ("app_form",{**base,"osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""}),
    ]
    for vn,form in variants:
        rows.append({"sample":name,"variant":vn,"formKeys":sorted(form.keys()),"response":post("/stationsNear",form)})

report={"scope":"NextCharge stationsNear unauthenticated/app-form probe","results":rows}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2)[:120000])
