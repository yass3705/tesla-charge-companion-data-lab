#!/usr/bin/env python3
import gzip, json, re, requests
from pathlib import Path

BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
PUN=Path("data/national/pun_italy_national.json.gz")
OUT=Path("data/reports/nextcharge_ges_qr_probe.json")
HEAD={"User-Agent":"NextCharge/6.2.02 Android","Content-Type":"application/x-www-form-urlencoded"}

def post(path,data):
    try:
        r=requests.post(BASE+path,data=data,headers=HEAD,timeout=(8,20))
        row={"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:1000]
        return row
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}

def list_data(resp):
    o=resp.get("json") if isinstance(resp,dict) else None
    if not isinstance(o,dict) or o.get("status")!="OK": return []
    d=o.get("data")
    if isinstance(d,list): return d
    if isinstance(d,dict):
        for k in ("results","stations","data","connectors"):
            if isinstance(d.get(k),list): return d[k]
    return []

pun=json.loads(gzip.decompress(PUN.read_bytes()))
ges=[e for e in pun.get("evses",[]) if isinstance(e,dict) and e.get("partyId")=="GES" and e.get("evseId")]
sample=[]
seen=set()
for e in ges:
    sid=str(e.get("stationId") or "")
    if sid in seen: continue
    seen.add(sid); sample.append(e)
    if len(sample)>=8: break

rows=[]
for e in sample:
    ev=str(e["evseId"])
    star=ev
    if ev.startswith("ITGES"):
        star="IT*GES*"+ev[5:]
    forms=[
      ("raw_evse",ev),
      ("starred_evse",star),
      ("map_it_raw",f"https://nextcharge.app/map?lang=it&station={ev}"),
      ("map_it_star",f"https://nextcharge.app/map?lang=it&station={star}"),
      ("map_en_raw",f"https://nextcharge.app/map?lang=en&station={ev}"),
      ("map_en_star",f"https://nextcharge.app/map?lang=en&station={star}"),
      ("ges_scheme_raw",f"gesnextcharge://{ev}"),
      ("ges_scheme_star",f"gesnextcharge://{star}"),
    ]
    attempts=[]
    for name,payload in forms:
        resp=post("/station",{"payloadQrCode":payload})
        o=resp.get("json") if isinstance(resp,dict) else None
        status=o.get("status") if isinstance(o,dict) else None
        data=o.get("data") if isinstance(o,dict) else None
        sid=None
        if status=="OK":
            if isinstance(data,dict): sid=data.get("idStation") or data.get("stationId") or data.get("id")
            elif isinstance(data,list):
                for x in data:
                    if isinstance(x,dict):
                        sid=x.get("idStation") or x.get("stationId") or x.get("id")
                        if sid is not None: break
        chain=None
        if sid is not None:
            chain=post("/stationConnectors",{"idStation":str(sid),"limit":"100","offset":"0","osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""})
        attempts.append({"variant":name,"payload":payload,"response":resp,"stationId":sid,"connectors":chain})
    rows.append({"evseId":ev,"punStationId":e.get("stationId"),"attempts":attempts})

report={"scope":"GES NextCharge APK-observed QR payload probe","gesPunEvseCount":len(ges),"sampleCount":len(sample),"results":rows,"security":{"credentialsUsed":False,"paymentAttempted":False,"chargingStarted":False}}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2)[:180000])
