#!/usr/bin/env python3
"""Retry only missing ENX station serials from a prior direct-payment candidate.

Inputs:
- current PUN Italy inventory: data/national/pun_italy_national.json.gz
- first-pass candidate: data/national/enel_direct_stations_italy.json.gz

The script preserves exact PUN inventory authority, retries only station serials
with no successful station-detail row in the first pass, and unions recovered
EVSE without replacing already validated rows.
"""
from __future__ import annotations
import argparse, gzip, json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
import enel_italy_national_tariffs as base

PUN=Path("data/national/pun_italy_national.json.gz")
FIRST=Path("data/national/enel_direct_stations_italy.json.gz")
OUT=Path("data/national/enel_direct_stations_italy_retry_union.json.gz")
REPORT=Path("data/reports/enel_italy_directpayment_retry_report.json")

def load(path: Path)->dict[str,Any]:
    return json.loads(gzip.decompress(path.read_bytes()))

def collapse(serial:str, station:dict[str,Any], rows:list[dict[str,Any]])->dict[str,Any]:
    first=rows[0]
    return {
      "evseId": first.get("evseId"),
      "stationSerialNumber": serial,
      "operator": first.get("operator"),
      "partyId": first.get("partyId"),
      "coordinates": first.get("coordinates"),
      "punStatus": first.get("punStatus"),
      "punOperationalState": first.get("punOperationalState"),
      "enelStationStatus": first.get("enelStationStatus"),
      "enelEvseStatus": first.get("enelEvseStatus"),
      "crossSource": first.get("crossSource"),
      "plugs":[{
        "connector": r.get("connector"),
        "enelPlugStatus": r.get("enelPlugStatus"),
        "appPayPerUseTariff": r.get("appPayPerUseTariff"),
        "directPaymentTariff": r.get("directPaymentTariff"),
        "penaltyCandidate": r.get("penaltyCandidate"),
      } for r in rows]
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--workers",type=int,default=16); args=ap.parse_args()
    pun=load(PUN); first=load(FIRST)
    pun_evs=[e for e in pun.get("evses",[]) if isinstance(e,dict) and e.get("partyId")=="ENX"]
    pun_index={str(e.get("evseId")):e for e in pun_evs if e.get("evseId")}
    serial_to_pun=defaultdict(list)
    for eid in sorted(pun_index):
        s=base.extract_serial(eid)
        if s: serial_to_pun[s].append(eid)

    by_evse={str(e.get("evseId")):e for e in first.get("evses",[]) if isinstance(e,dict) and e.get("evseId")}
    successful_serials={str(e.get("stationSerialNumber")) for e in by_evse.values() if e.get("stationSerialNumber")}
    missing_serials=sorted(set(serial_to_pun)-successful_serials)

    headers=base.extract_public_headers()
    details=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        futs={pool.submit(base.get_detail,s,headers):s for s in missing_serials}
        for i,f in enumerate(as_completed(futs),1):
            try: details.append(f.result())
            except Exception as exc: details.append({"ok":False,"serial":futs[f],"error":f"{type(exc).__name__}: {exc}"})
            if i%100==0 or i==len(futs):
                ok=sum(1 for x in details if x.get("ok") is True)
                print(f"ENX targeted retry: {i}/{len(futs)} successful={ok} failed={len(details)-ok}")

    recovered=defaultdict(list); failures=[]; unmatched=[]
    for d in details:
        if d.get("ok") is not True:
            failures.append({k:d.get(k) for k in ("serial","httpStatus","businessCode","businessMessage","error")})
            continue
        serial=str(d.get("serial")); station=d.get("result")
        if not isinstance(station,dict): continue
        for evse in station.get("evses") or []:
            if not isinstance(evse,dict): continue
            for plug in evse.get("plugs") or []:
                if not isinstance(plug,dict): continue
                rec,miss=base.normalize_plug(serial,station,evse,plug,pun_index)
                if miss: unmatched.append(miss)
                elif rec: recovered[str(rec["evseId"])].append(rec)

    recovered_rows={}
    for eid,rows in recovered.items():
        if eid in by_evse: continue
        recovered_rows[eid]=collapse(str(rows[0].get("stationSerialNumber")),{},rows)
    by_evse.update(recovered_rows)
    union=[by_evse[eid] for eid in sorted(by_evse)]

    direct=Counter(); app=Counter(); statuses=Counter()
    rankable=0
    for row in union:
        is_rank=False
        for pl in row.get("plugs") or []:
            dt=pl.get("directPaymentTariff") or {}
            at=pl.get("appPayPerUseTariff") or {}
            if dt.get("rankable") and dt.get("eurPerKwh") is not None:
                is_rank=True; direct[f"{float(dt['eurPerKwh']):.3f}"]+=1
            if at.get("eurPerKwh") is not None: app[f"{float(at['eurPerKwh']):.3f}"]+=1
            statuses[str(pl.get("enelPlugStatus") or "UNKNOWN")]+=1
        rankable += int(is_rank)

    failure_class_counts=Counter()
    failure_http_counts=Counter()
    for x in failures:
        failure_class_counts[str(x.get("error") or "unknown")] += 1
        if x.get("httpStatus") is not None:
            failure_http_counts[str(x.get("httpStatus"))] += 1
    unmatched_prefix_counts=Counter()
    for x in unmatched:
        raw=x.get("rawEnelEvseId")
        if isinstance(raw,str) and raw.startswith("IT*"):
            parts=raw.split("*")
            if len(parts) >= 2:
                unmatched_prefix_counts[parts[1]] += 1
        else:
            unmatched_prefix_counts["UNKNOWN"] += 1

    successful_after={str(e.get("stationSerialNumber")) for e in union if e.get("stationSerialNumber")}
    remaining_serials=sorted(set(serial_to_pun)-successful_after)
    remaining_evs=sorted(set(pun_index)-set(by_evse))
    counts=dict(first.get("counts") or {})
    counts.update({
      "retryRequestedStationSerialCount":len(missing_serials),
      "retrySuccessfulStationDetailCount":sum(1 for x in details if x.get("ok") is True),
      "retryFailureStationCount":len(failures),
      "retryRecoveredEvseCount":len(recovered_rows),
      "matchedEnelEvseCountAfterRetry":len(union),
      "rankableDirectPaymentEvseCountAfterRetry":rankable,
      "rankableDirectPaymentCoveragePctAfterRetry":round(100*rankable/max(1,len(pun_evs)),2),
      "remainingStationSerialWithoutDetailAfterRetry":len(remaining_serials),
      "remainingEvseWithoutMatchedDetailAfterRetry":len(remaining_evs),
      "retryFailureClassCounts":dict(sorted(failure_class_counts.items())),
      "retryFailureHttpStatusCounts":dict(sorted(failure_http_counts.items())),
      "retryUnmatchedPrefixCounts":dict(sorted(unmatched_prefix_counts.items())),
    })
    out=dict(first)
    out["generatedAtAfterRetry"]=base.now_iso()
    out["counts"]=counts
    out["observedAppPayPerUsePriceEurPerKwhAfterRetry"]=dict(sorted(app.items()))
    out["observedDirectPaymentPriceEurPerKwhAfterRetry"]=dict(sorted(direct.items()))
    out["observedPlugStatusCountsAfterRetry"]=dict(sorted(statuses.items()))
    out["retryQuality"]={
      "failureSample":failures[:100],
      "unmatchedSample":unmatched[:100],
      "remainingSerialSample":remaining_serials[:100],
      "remainingEvseSample":remaining_evs[:100],
      "failureClassCounts":dict(sorted(failure_class_counts.items())),
      "failureHttpStatusCounts":dict(sorted(failure_http_counts.items())),
      "unmatchedPrefixCounts":dict(sorted(unmatched_prefix_counts.items())),
    }
    out["evses"]=union
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes(gzip.compress((json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n").encode(),compresslevel=9))
    report={
      "generatedAt":out["generatedAtAfterRetry"],
      "counts":counts,
      "observedDirectPaymentPriceEurPerKwh":out["observedDirectPaymentPriceEurPerKwhAfterRetry"],
      "observedAppPayPerUsePriceEurPerKwh":out["observedAppPayPerUsePriceEurPerKwhAfterRetry"],
      "retryFailureSample":failures[:100],
      "retryUnmatchedSample":unmatched[:100],
      "remainingSerialSample":remaining_serials[:100],
      "remainingEvseSample":remaining_evs[:100],
      "failureClassCounts":dict(sorted(failure_class_counts.items())),
      "failureHttpStatusCounts":dict(sorted(failure_http_counts.items())),
      "unmatchedPrefixCounts":dict(sorted(unmatched_prefix_counts.items())),
    }
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:30000])

if __name__=="__main__": main()
