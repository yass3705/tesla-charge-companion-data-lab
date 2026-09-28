#!/usr/bin/env python3
import argparse,json,time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime,timezone
import collect_swiss_atlas_cpo as base

def one_station(s,key,args):
    attrs=s.get("attributes") or {}
    cps=attrs.get("charge_points") or []
    cp_results=[]; station_has_direct=False; direct_detail_count=0; direct_payment_count=0
    for cp in cps:
        power=cp.get("power"); plug=cp.get("plug")
        if power is None or plug is None:
            cp_results.append({"chargePoint":cp,"status":None,"directTariffs":[],"reason":"missing_power_or_plug"})
            continue
        body={"data":{"attributes":{"station":{"id":[s.get("id")],"charge_point":{"power":power,"plug":plug}},"filter":{
            "brand_restricted_tariffs":False,"foreign_tariffs":False,"provider_customer_tariffs":args.provider_customer_tariffs
        }},"relationships":{}}}
        st,p=base.api_call(base.ATLAS+"/v1/tariff_details",key,"POST",body,delay=args.delay)
        ds=base.direct_tariffs(p) if st==200 and isinstance(p,dict) else []
        if ds:
            station_has_direct=True; direct_detail_count += len(ds)
            for d in ds:
                ta=(d.get("tariff") or {}).get("attributes") or {}
                if ta.get("is_direct_payment") is True: direct_payment_count += 1
        cp_results.append({"chargePoint":cp,"status":st,"directTariffs":ds,
                           "error":None if st==200 else p.get("error") if isinstance(p,dict) else str(p)})
    row={"stationId":s.get("id"),"name":attrs.get("name"),"latitude":attrs.get("latitude"),
         "longitude":attrs.get("longitude"),"address":attrs.get("address"),"evseIds":attrs.get("evse_ids") or [],
         "evseOperator":attrs.get("evse_operator"),"chargePoints":cp_results}
    unresolved=None if station_has_direct else {"stationId":s.get("id"),"name":attrs.get("name"),
        "evseIds":attrs.get("evse_ids") or [],"reason":"no_direct_non_roaming_tariff"}
    return row,unresolved,direct_detail_count,direct_payment_count

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--operator",required=True); ap.add_argument("--name",required=True); ap.add_argument("--output",required=True)
    ap.add_argument("--workers",type=int,default=4); ap.add_argument("--delay",type=float,default=0.10)
    ap.add_argument("--provider-customer-tariffs",action="store_true")
    args=ap.parse_args()
    key=base.extract_public_key(); stations=base.station_pages(args.operator,key)
    rows=[None]*len(stations); unresolved=[]; direct_detail_count=0; direct_payment_count=0
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,6))) as pool:
        futs={pool.submit(one_station,s,key,args):i for i,s in enumerate(stations)}
        done=0
        for fut in as_completed(futs):
            i=futs[fut]; row,miss,dc,pc=fut.result(); rows[i]=row
            if miss: unresolved.append(miss)
            direct_detail_count += dc; direct_payment_count += pc; done += 1
            if done%50==0 or done==len(stations):
                print(f"{args.operator}: {done}/{len(stations)} stations; unresolved={len(unresolved)}",flush=True)
    unresolved_by_id={x["stationId"]:x for x in unresolved}
    unresolved=[unresolved_by_id[k] for k in sorted(unresolved_by_id)]
    resolved=len(stations)-len(unresolved)
    payload={"schemaVersion":1,"country":"CH","cpo":args.name,"operatorId":args.operator,
      "retrievedAt":datetime.now(timezone.utc).isoformat(),
      "source":{"stationApi":base.ATLAS+"/v1/charging_stations","tariffApi":base.ATLAS+"/v1/tariff_details",
        "frontend":base.FRONT,"authentication":"public frontend API key resolved dynamically",
        "collectorMode":"parallel-second-pass" if args.provider_customer_tariffs else "parallel-first-pass-fallback"},
      "summary":{"stationCount":len(stations),"stationsWithDirectTariff":resolved,
        "stationsWithoutDirectTariff":len(unresolved),
        "coveragePct":round(resolved*100/len(stations),3) if stations else 0,
        "directTariffDetailCount":direct_detail_count,"directPaymentTariffDetailCount":direct_payment_count,
        "status":"complete" if stations and not unresolved else "partial"},
      "stations":rows,"unresolved":unresolved,
      "policy":"Only is_roaming=false records with EMP id equal to CPO id are retained. No extrapolation."}
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload["summary"],ensure_ascii=False),flush=True)

if __name__=="__main__": main()
