#!/usr/bin/env python3
from __future__ import annotations
import gzip,json,requests
from pathlib import Path
from urllib.parse import urljoin
import enel_italy_station_probe as probe

BASE="https://emobility.enelx.com/api/"
OUT=Path("data/reports/enel_italy_second_route_probe.json")
CANDIDATES=[
 "pst/evos/tariff/",
 "pst/evos/tariff",
 "pst/evos/v1/catalog/penalty",
 "pst/evos/v2/tariff/tariff-plan/calendar/",
 "optimization/tariffs/",
]
PARAM_KEYS=["serialNumber","stationSerialNumber","evseId","connectorId","csId"]

def safe_json(r):
    try:
        o=r.json()
    except Exception:
        return {"json":False,"textPrefix":r.text[:300]}
    if isinstance(o,dict):
        return {"json":True,"keys":sorted(o.keys())[:80],"code":o.get("code"),"message":o.get("message"),"resultType":type(o.get("result")).__name__,"resultPresent":o.get("result") not in (None,[],{})}
    return {"json":True,"type":type(o).__name__}

def main():
    headers,diag=probe.extract_browser_station_headers()
    known="18XP22T3KK4AH00014"
    residual="18XP22T3KK4AH00015"
    # Prefer exact residual from retry report when present.
    rp=Path("data/reports/enel_italy_directpayment_retry_report.json")
    if rp.exists():
        try:
            d=json.loads(rp.read_text())
            s=(d.get("remainingSerialSample") or [])
            if s: residual=str(s[0])
        except Exception: pass
    rows=[]
    session=requests.Session()
    for path in CANDIDATES:
        url=urljoin(BASE,path)
        tests=[("bare",{})]
        for key in PARAM_KEYS:
            tests.append((f"known:{key}",{key:known}))
            tests.append((f"residual:{key}",{key:residual}))
        for label,params in tests:
            try:
                r=session.get(url,headers=headers,params=params,timeout=30,allow_redirects=False)
                rows.append({"path":path,"label":label,"status":r.status_code,"contentType":r.headers.get("content-type"),"location":r.headers.get("location"),"response":safe_json(r)})
            except Exception as e:
                rows.append({"path":path,"label":label,"error":f"{type(e).__name__}: {e}"})
    report={"scope":"enel_second_route_get_only_probe","browser":diag,"knownSerial":known,"residualSerial":residual,"rows":rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:50000])

if __name__=="__main__": main()
