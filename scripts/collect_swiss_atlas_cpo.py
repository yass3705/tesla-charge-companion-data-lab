#!/usr/bin/env python3
import argparse,json,re,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from datetime import datetime,timezone

ATLAS="https://api.chargeprice.app"
FRONT="https://swiss.chargeprice.app/"

def get(url, headers=None, timeout=60):
    req=urllib.request.Request(url,headers=headers or {"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.status,dict(r.headers.items()),r.read()

def extract_public_key():
    _,_,html=get(FRONT,{"User-Agent":"Mozilla/5.0","Accept":"text/html"})
    text=html.decode("utf-8","replace")
    scripts=re.findall(r'<script[^>]+src="([^"]+)"',text,re.I)
    for s in scripts:
        u=urllib.parse.urljoin(FRONT,s)
        try:
            _,_,raw=get(u,{"User-Agent":"Mozilla/5.0"})
        except Exception:
            continue
        js=raw.decode("utf-8","replace")
        m=re.search(r'getApiKey\(\)\{return"([A-Fa-f0-9]{20,})"\}',js)
        if m:
            return m.group(1)
    raise SystemExit("Could not resolve public Swiss price-atlas API key from frontend")

def api_call(url,key,method="GET",body=None,retries=4,delay=0.0):
    headers={
        "User-Agent":"Mozilla/5.0",
        "Accept":"application/json",
        "Content-Type":"application/json",
        "Accept-Language":"en",
        "Api-Key":key
    }
    data=None if body is None else json.dumps(body).encode()
    last=None
    for attempt in range(retries):
        if delay: time.sleep(delay)
        req=urllib.request.Request(url,headers=headers,data=data,method=method)
        try:
            with urllib.request.urlopen(req,timeout=60) as r:
                return r.status,json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw=e.read().decode("utf-8","replace")
            last=(e.code,raw)
            if e.code not in (429,500,502,503,504):
                return e.code,{"error":raw}
            time.sleep(min(8,2**attempt))
        except Exception as e:
            last=(0,type(e).__name__+": "+str(e))
            time.sleep(min(8,2**attempt))
    return last[0],{"error":last[1]}

def direct_tariffs(payload):
    included={(x.get("type"),x.get("id")):x for x in (payload.get("included") or [])}
    out=[]
    for d in payload.get("data") or []:
        attrs=d.get("attributes") or {}
        rel=d.get("relationships") or {}
        emp=rel.get("emp",{}).get("data") or {}
        cpo=rel.get("cpo",{}).get("data") or {}
        if attrs.get("is_roaming") is not False or not emp.get("id") or emp.get("id")!=cpo.get("id"):
            continue
        tar=rel.get("tariff",{}).get("data") or {}
        t= included.get((tar.get("type"),tar.get("id")))
        e= included.get((emp.get("type"),emp.get("id")))
        c= included.get((cpo.get("type"),cpo.get("id")))
        out.append({
            "detailId":d.get("id"),
            "attributes":attrs,
            "tariff":t,
            "emp":e,
            "cpo":c
        })
    return out

def station_pages(operator,key):
    rows=[]
    page=1
    while True:
        params={
            "filter[latitude.gte]":"45.80",
            "filter[latitude.lte]":"47.90",
            "filter[longitude.gte]":"5.80",
            "filter[longitude.lte]":"10.60",
            "filter[evse_operator]":operator,
            "page[number]":str(page),
            "page[size]":"400"
        }
        url=ATLAS+"/v1/charging_stations?"+urllib.parse.urlencode(params)
        st,p=api_call(url,key,delay=0.05)
        if st!=200:
            raise SystemExit(f"station query failed {operator} page {page}: HTTP {st}")
        rows.extend(p.get("data") or [])
        meta=p.get("meta") or {}
        if not meta.get("more_available"):
            break
        page+=1
        if page>100:
            raise SystemExit("page guard hit")
    # de-dup
    seen=set(); out=[]
    for s in rows:
        sid=s.get("id")
        if sid in seen: continue
        seen.add(sid); out.append(s)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--operator",required=True)
    ap.add_argument("--name",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--delay",type=float,default=0.18)
    ap.add_argument("--provider-customer-tariffs",action="store_true")
    ap.add_argument("--brand-restricted-tariffs",action="store_true")
    args=ap.parse_args()

    key=extract_public_key()
    stations=station_pages(args.operator,key)
    results=[]
    unresolved=[]
    direct_detail_count=0
    direct_payment_count=0

    for idx,s in enumerate(stations,1):
        attrs=s.get("attributes") or {}
        cps=attrs.get("charge_points") or []
        cp_results=[]
        station_has_direct=False
        for cp in cps:
            power=cp.get("power")
            plug=cp.get("plug")
            if power is None or plug is None:
                cp_results.append({"chargePoint":cp,"status":None,"directTariffs":[],"reason":"missing_power_or_plug"})
                continue
            body={"data":{"attributes":{"station":{
                "id":[s.get("id")],
                "charge_point":{"power":power,"plug":plug}
            },"filter":{
                "brand_restricted_tariffs":args.brand_restricted_tariffs,
                "foreign_tariffs":False,
                "provider_customer_tariffs":args.provider_customer_tariffs
            }},"relationships":{}}}
            st,p=api_call(ATLAS+"/v1/tariff_details",key,"POST",body,delay=args.delay)
            ds=direct_tariffs(p) if st==200 and isinstance(p,dict) else []
            if ds:
                station_has_direct=True
                direct_detail_count += len(ds)
                for d in ds:
                    ta=(d.get("tariff") or {}).get("attributes") or {}
                    if ta.get("is_direct_payment") is True:
                        direct_payment_count += 1
            cp_results.append({"chargePoint":cp,"status":st,"directTariffs":ds,
                               "error":None if st==200 else p.get("error") if isinstance(p,dict) else str(p)})
        row={
            "stationId":s.get("id"),
            "name":attrs.get("name"),
            "latitude":attrs.get("latitude"),
            "longitude":attrs.get("longitude"),
            "address":attrs.get("address"),
            "evseIds":attrs.get("evse_ids") or [],
            "evseOperator":attrs.get("evse_operator"),
            "chargePoints":cp_results
        }
        results.append(row)
        if not station_has_direct:
            unresolved.append({
                "stationId":s.get("id"),
                "name":attrs.get("name"),
                "evseIds":attrs.get("evse_ids") or [],
                "reason":"no_direct_non_roaming_tariff"
            })
        if idx % 50 == 0:
            print(f"{args.operator}: {idx}/{len(stations)} stations; unresolved={len(unresolved)}",flush=True)

    resolved=len(stations)-len(unresolved)
    payload={
        "schemaVersion":1,
        "country":"CH",
        "cpo":args.name,
        "operatorId":args.operator,
        "retrievedAt":datetime.now(timezone.utc).isoformat(),
        "source":{
            "stationApi":ATLAS+"/v1/charging_stations",
            "tariffApi":ATLAS+"/v1/tariff_details",
            "frontend":FRONT,
            "authentication":"public frontend API key resolved dynamically"
        },
        "summary":{
            "stationCount":len(stations),
            "stationsWithDirectTariff":resolved,
            "stationsWithoutDirectTariff":len(unresolved),
            "coveragePct":round(resolved*100/len(stations),3) if stations else 0,
            "directTariffDetailCount":direct_detail_count,
            "directPaymentTariffDetailCount":direct_payment_count,
            "status":"complete" if stations and not unresolved else "partial"
        },
        "stations":results,
        "unresolved":unresolved,
        "policy":"Only is_roaming=false records with EMP id equal to CPO id are retained as direct CPO tariffs. No extrapolation across stations."
    }
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload["summary"],ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
