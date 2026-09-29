#!/usr/bin/env python3
from __future__ import annotations
import json, platform, uuid, time
from pathlib import Path
import requests

BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
OUT=Path("data/reports/nextcharge_ges_guest_session_probe.json")
EVSE="ITGESE125845134"
DEVICE=str(uuid.uuid4())

def post(path, data, headers=None, timeout=(8,20)):
    h={"User-Agent":"NextCharge/6.2.02 Android","Content-Type":"application/x-www-form-urlencoded"}
    if headers: h.update(headers)
    t=time.time()
    try:
        r=requests.post(BASE+path,data=data,headers=h,timeout=timeout)
        row={"elapsed":round(time.time()-t,3),"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:800]
        return row
    except Exception as e:
        return {"elapsed":round(time.time()-t,3),"error":f"{type(e).__name__}: {e}"}

def post_multipart(path, data, headers=None, timeout=(8,20)):
    h={"User-Agent":"NextCharge/6.2.02 Android"}
    if headers: h.update(headers)
    files={k:(None,str(v)) for k,v in data.items()}
    t=time.time()
    try:
        r=requests.post(BASE+path,files=files,headers=h,timeout=timeout)
        row={"elapsed":round(time.time()-t,3),"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:800]
        return row
    except Exception as e:
        return {"elapsed":round(time.time()-t,3),"error":f"{type(e).__name__}: {e}"}

def token_from(row):
    o=row.get("json") if isinstance(row,dict) else None
    if not isinstance(o,dict): return None
    status=o.get("status")
    if status not in ("OK","AUTH_NEW_USER"): return None
    d=o.get("data")
    if isinstance(d,dict):
        return d.get("token") or d.get("tokenStations") or d.get("tokenAppSessionForStations")
    return o.get("token")

def main():
    common={
      "request":"authSession",
      "deviceModel":"GitHub Actions",
      "osType":"android",
      "osVersion":"14",
      "appVersion":"6.2.02",
      "lang":"en",
      "tokenType":"stations",
    }
    variants=[
      ("empty_user", {**common,"userId":""}),
      ("zero_user", {**common,"userId":"0"}),
      ("device_as_user", {**common,"userId":DEVICE}),
      ("device_key_plus_empty_user", {**common,"userId":"","deviceKey":DEVICE}),
    ]
    auth=[]
    station=[]
    for name,form in variants:
        a=post("/userSession",form)
        tok=token_from(a)
        auth.append({"variant":name,"formKeys":sorted(form.keys()),"response":a,"tokenObtained":bool(tok)})
        if tok:
            header_sets=[
              ("token_only",{"tokenAppSessionForStations":tok}),
              ("apk_headers",{
                "tokenAppSessionForStations":tok,
                "deviceKey":DEVICE,
                "osType":"android",
                "appVersion":"6.2.02",
              }),
            ]
            for hn,hh in header_sets:
                for ev in (EVSE,"IT*GES*E125845134"):
                    s=post_multipart("/station",{"uidConnector":ev},hh)
                    row={"authVariant":name,"headerVariant":hn,"submittedEvseId":ev,"response":s}
                    o=s.get("json") if isinstance(s,dict) else None
                    sid=None
                    if isinstance(o,dict) and o.get("status")=="OK":
                        d=o.get("data")
                        if isinstance(d,dict):
                            sid=d.get("idStation") or d.get("stationId") or d.get("id")
                        elif isinstance(d,list):
                            for x in d:
                                if isinstance(x,dict):
                                    sid=x.get("idStation") or x.get("stationId") or x.get("id")
                                    if sid is not None: break
                    if sid is not None:
                        row["stationId"]=sid
                        row["connectors"]=post_multipart("/stationConnectors",{"idStation":str(sid),"limit":"100","offset":"0"},hh)
                    station.append(row)
    report={
      "scope":"NextCharge guest station reconstruction using APK-observed multipart uidConnector flow",
      "deviceKey":DEVICE,
      "authAttempts":auth,
      "stationAttempts":station,
      "security":{"credentialsUsed":False,"paymentAttempted":False,"chargingStarted":False}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:150000])

if __name__=="__main__": main()
