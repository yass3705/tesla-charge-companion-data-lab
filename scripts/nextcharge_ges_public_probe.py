#!/usr/bin/env python3
from __future__ import annotations
import gzip, json, uuid
from pathlib import Path
import requests

PUN=Path("data/national/pun_italy_national.json.gz")
OUT=Path("data/reports/nextcharge_ges_public_probe.json")
BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
UA="NextCharge/6.2.02 Android"

def loadgz(p): return json.loads(gzip.decompress(p.read_bytes()))

def safe_obj(r):
    row={"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
    try:
        o=r.json()
    except Exception:
        row["textPrefix"]=r.text[:500]
        return row
    row["json"]=o
    return row

def post(path, form, extra_headers=None):
    headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"}
    if extra_headers: headers.update(extra_headers)
    try:
        r=requests.post(BASE+path,data=form,headers=headers,timeout=35)
        return safe_obj(r)
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}

def extract_data(obj):
    if not isinstance(obj,dict): return None
    if obj.get("status")=="OK":
        return obj.get("data")
    return None

def main():
    pun=loadgz(PUN)
    ges=[e for e in pun.get("evses",[]) if isinstance(e,dict) and e.get("partyId")=="GES" and e.get("evseId")]
    sample=ges[:8]
    device=str(uuid.uuid4())
    header_profiles=[
      ("plain",{}),
      ("app_headers",{"deviceKey":device,"osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""}),
    ]
    results=[]
    for e in sample:
        evse=str(e["evseId"])
        for profile,h in header_profiles:
            form={"idStation":"","evseId":evse,"uidConnector":"","urlToEncode":"","payloadQrCode":""}
            st=post("/station",form,h)
            entry={"evseId":evse,"profile":profile,"stationCall":st}
            data=extract_data(st.get("json") if isinstance(st,dict) else None)
            station_id=None
            if isinstance(data,dict):
                station_id=data.get("idStation") or data.get("stationId") or data.get("id")
                entry["stationKeys"]=sorted(data.keys())
            elif isinstance(data,list) and data and isinstance(data[0],dict):
                station_id=data[0].get("idStation") or data[0].get("stationId") or data[0].get("id")
                entry["stationKeys"]=sorted(data[0].keys())
            if station_id is not None:
                con=post("/stationConnectors",{"idStation":str(station_id),"limit":"100","offset":"0"},h)
                entry["stationId"]=station_id
                entry["connectorsCall"]=con
            results.append(entry)
    # Compact tariff evidence
    price_evidence=[]
    def walk(o,path=""):
        if isinstance(o,dict):
            for k,v in o.items():
                p=f"{path}.{k}" if path else str(k)
                lk=str(k).lower()
                if any(x in lk for x in ("price","tariff","currency","parking","roaming","provider","emp","payment")) and not isinstance(v,(dict,list)):
                    price_evidence.append({"path":p,"value":v})
                walk(v,p)
        elif isinstance(o,list):
            for i,v in enumerate(o[:100]): walk(v,f"{path}[{i}]")
    for r in results:
        walk(r.get("connectorsCall",{}),f"{r['evseId']}:{r['profile']}")
    report={
      "scope":"GES NextCharge public POST probe from APK 6.2.02",
      "gesPunEvseCount":len(ges),
      "sampleEvseIds":[str(x["evseId"]) for x in sample],
      "results":results,
      "priceEvidence":price_evidence[:1000],
      "security":{"accountCredentialsUsed":False,"chargingStarted":False,"paymentAttempted":False},
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:120000])

if __name__=="__main__": main()
