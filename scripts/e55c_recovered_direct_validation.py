#!/usr/bin/env python3
"""Audit recovered E55C PAN PDCs against the CPO's direct ad-hoc tariff-display API.
The scan-pay initialize roaming response is identity evidence only, never a Direct price.
"""
import concurrent.futures
import datetime
import json
import pathlib
import urllib.parse
import urllib.request
import urllib.error

RECOVERY=pathlib.Path("reports/france/e55c/pan-gap-recovery.json")
OUT=pathlib.Path("reports/france/e55c/recovered-direct-tariff-validation.json")
L=pathlib.Path("data/station_verifications/electric55_lourmarin_user_exact_2026_10_13.json")
def probe(row):
    good=[p for p in row.get("probes",[]) if p.get("status")==200 and isinstance(p.get("json"),dict) and p["json"].get("pricingDefinitions")]
    identities={p["evse"] for p in good}
    if len(identities)!=1:
        return {"panPdcId":row["pan"]["pdcId"],"status":"identity_ambiguous_or_absent"}
    evse=identities.pop()
    connector=good[0]["connector"]
    source=good[0]["json"]
    returned=(source.get("chargingStation") or {}).get("id")
    if returned!=evse:
        return {"panPdcId":row["pan"]["pdcId"],"status":"source_evse_mismatch","evse":evse}
    url="https://rest.service-evse.com/v1/util/pricing-model/tariff-display/"+urllib.parse.quote(evse,safe="*")+"?tenant=e55c&ConnectorID="+urllib.parse.quote(str(connector))
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"TeslaChargeCompanion-E55C-Direct-Audit/1.0","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=22) as res:
            payload=json.load(res)
        definitions=[d for d in payload.get("definitions",[]) if d.get("isMatching") is True]
        methods=sorted({str(d.get("method") or "") for d in definitions})
        amounts=[]
        for d in definitions:
            for item in d.get("items") or []:
                dims=item.get("dimensions") or {}
                amounts.append({k:{"price":v.get("price"),"vat":v.get("vat")} for k,v in dims.items() if isinstance(v,dict) and v.get("active") is True})
        valid=bool(definitions and amounts) and all(x!="ROAMING_EMPS" for x in methods)
        return {"panPdcId":row["pan"]["pdcId"],"evse":evse,"status":"direct_candidate" if valid else "not_validated_as_direct",
                "methods":methods,"definitionCount":len(definitions),"components":amounts[:10],
                "note":"Direct endpoint check; only filtered matching tariff definitions, no promotion"}
    except urllib.error.HTTPError as exc:
        return {"panPdcId":row["pan"]["pdcId"],"evse":evse,"status":"endpoint_http_error","httpStatus":exc.code}
    except Exception as exc:
        return {"panPdcId":row["pan"]["pdcId"],"evse":evse,"status":"endpoint_error","errorType":type(exc).__name__}

def probe_exact_direct(evse):
    """Check exact user-identified consumer EVSE without relying on a PAN alias."""
    url="https://rest.service-evse.com/v1/util/pricing-model/tariff-display/"+urllib.parse.quote(evse,safe="*")+"?tenant=e55c&ConnectorID=1"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"TeslaChargeCompanion-E55C-Direct-Audit/1.0","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=22) as res:
            payload=json.load(res)
        definitions=[d for d in payload.get("definitions",[]) if d.get("isMatching") is True]
        return {"evseId":evse,"httpStatus":200,"matchingDefinitionCount":len(definitions),
                "methods":sorted({str(d.get("method") or "") for d in definitions}),
                "sourceNames":sorted({str(d.get("name") or "") for d in definitions}),
                "items":[{"dimensions":{k:{"price":v.get("price"),"vat":v.get("vat")} for k,v in (item.get("dimensions") or {}).items() if isinstance(v,dict) and v.get("active")},
                          "timeFrom":(item.get("restrictions") or {}).get("timeFrom"),
                          "timeTo":(item.get("restrictions") or {}).get("timeTo")}
                         for d in definitions for item in d.get("items") or []][:12]}
    except urllib.error.HTTPError as exc:
        return {"evseId":evse,"httpStatus":exc.code,"matchingDefinitionCount":0}
    except Exception as exc:
        return {"evseId":evse,"error":type(exc).__name__}

def main():
    recovery=json.loads(RECOVERY.read_text())
    manual=json.loads(L.read_text())
    assert recovery["gapCount"]==55 and len(recovery["recovered"])==55
    assert manual["rows"][0]["evseId"].endswith("*0") and manual["rows"][0]["dayChargeEurPerMinute"]==.08
    assert len(manual["rows"])==4 and all(x["sessionFeeEur"]==.60 for x in manual["rows"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(probe,recovery["recovered"]))
    assert len(results)==55 and len({p["panPdcId"] for p in results})==55
    statuses={k:sum(p["status"]==k for p in results) for k in sorted({p["status"] for p in results})}
    samples=["FR*55C*EFR78210*P21PL*0"]+[row["evseId"] for row in manual["rows"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        direct_samples=list(pool.map(probe_exact_direct,samples))
    doc={"directExamples":direct_samples,"generatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "sourceRecoveryGeneratedAt":recovery["generatedAt"],"pdcChecked":len(results),"statusCounts":statuses,
      "lourmarin":{"exactUmapEvseIds":[x["evseId"] for x in manual["rows"]],"premiumEvseId":manual["rows"][0]["evseId"],
        "manualAdHocPriceRecorded":True,"panPdcIdentityUnverified":True,
        "automaticDirectTariffPromotion":False},
      "publicationReady":False,"results":results}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"pdcChecked":len(results),"statusCounts":statuses,"directExamples":direct_samples,"lourmarin":doc["lourmarin"],"publicationReady":False},ensure_ascii=False))
if __name__=="__main__":main()
