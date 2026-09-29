#!/usr/bin/env python3
import json,time,urllib.request,urllib.parse,urllib.error,http.cookiejar
from datetime import datetime,timezone
from pathlib import Path

BASE="https://adhoc.swisscharge.ch"
TENANT="Swisscharge_CH"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SRC=Path("docs/switzerland-swisscharge-prefix-closeout-2026-09-28.json")
OUT=Path("docs/switzerland-swisscharge-residual-live-probe-2026-09-29.json")

def opener():
    cj=http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get(op,url,headers=None,timeout=30):
    req=urllib.request.Request(url,headers=headers or {},method="GET")
    try:
        with op.open(req,timeout=timeout) as r:
            return r.status,dict(r.headers.items()),r.read()
    except urllib.error.HTTPError as e:
        return e.code,dict(e.headers.items()),e.read()
    except Exception as e:
        return 0,{},(type(e).__name__+": "+str(e)).encode()

def parse(raw):
    try:return json.loads(raw.decode())
    except:return None

src=json.loads(SRC.read_text())
refs=[str(x["physicalReference"]) for x in src.get("unresolved",[])]
op=opener()
rows=[]
for i,ref in enumerate(refs,1):
    page=f"{BASE}/tenant/{TENANT}/session-start/{urllib.parse.quote(ref,safe='')}"
    api=f"{BASE}/api/v1/charge-points?evsePhysicalReference={urllib.parse.quote(ref,safe='')}"
    headers={"Accept":"application/json","Tenant":TENANT,"tenant-path":page,"Referer":page,"User-Agent":UA}
    get(op,page,{"User-Agent":UA},25)
    time.sleep(0.8)
    st,h,raw=get(op,api,headers,25)
    if st in (0,401,403,409,422,429):
        get(op,page,{"User-Agent":UA},25)
        time.sleep(1.0)
        st,h,raw=get(op,api,headers,25)
    p=parse(raw)
    row={"physicalReference":ref,"httpStatus":st}
    if st==200 and isinstance(p,dict):
        data=p.get("data") or {}
        cp=data.get("chargePoint") or {}
        evses=data.get("evses") or []
        ev=next((e for e in evses if str(e.get("physicalReference"))==ref),evses[0] if evses else {})
        t=ev.get("tariff") or {}
        row.update({
          "chargePoint":{"id":cp.get("id"),"locationName":cp.get("locationName"),"address":cp.get("address"),"city":cp.get("city")},
          "evse":{"physicalReference":ev.get("physicalReference"),"emi3Id":ev.get("emi3Id"),"id":ev.get("id"),"currentType":ev.get("currentType"),"powerOptions":ev.get("powerOptions")},
          "tariff":t
        })
    else:
        row["body"]=raw.decode("utf-8","replace")[:500]
    rows.append(row)
    print(f"{i}/{len(refs)} {ref} status={st}",flush=True)
out={
 "schemaVersion":1,
 "country":"CH",
 "operatorId":"CH*SUI",
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "method":"Validated Swisscharge anonymous tenant bootstrap + exact physicalReference API + one retry for context errors",
 "tenant":TENANT,
 "rows":rows,
 "summary":{
   "total":len(rows),
   "http200":sum(1 for r in rows if r["httpStatus"]==200),
   "withTariff":sum(1 for r in rows if (r.get("tariff") or {}).get("id") is not None),
   "withoutTariff":sum(1 for r in rows if r["httpStatus"]==200 and (r.get("tariff") or {}).get("id") is None),
   "errors":sum(1 for r in rows if r["httpStatus"]!=200)
 }
}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out["summary"],indent=2))
