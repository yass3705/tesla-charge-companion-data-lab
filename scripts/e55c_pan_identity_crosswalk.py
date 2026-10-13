#!/usr/bin/env python3
"""Consolidate proven E55C PAN aliases. Never publish roaming prices as Direct."""
import hashlib
import json
import pathlib
import re
from collections import Counter

SOURCE=pathlib.Path("reports/france/e55c/pan-gap-recovery.json")
TARGET=pathlib.Path("data/operator_direct/e55c_pan_identity_crosswalk_france.json")
def norm(s):return re.sub(r"[^A-Z0-9]","",str(s or "").upper())
def compile_crosswalk(source):
    if source.get("gapCount")!=55 or len(source.get("recovered",[]))!=55:raise ValueError("unexpected gap source")
    matched=[];unmatched=[]
    for row in source["recovered"]:
        p=row["pan"]
        good=[q for q in row.get("probes",[]) if q.get("status")==200 and isinstance(q.get("json"),dict) and q["json"].get("pricingDefinitions")]
        if len(good)!=1:
            unmatched.append({"panPdcId":p["pdcId"],"station":p["station"],"reason":"no unique source identity"})
            continue
        q=good[0];actual=(q["json"].get("chargingStation") or {}).get("id")
        if actual!=q["evse"] or norm(actual)!=norm(p["pdcId"]):
            raise ValueError("source identity/PAN mismatch: "+p["pdcId"])
        methods=sorted(set(str(d.get("method") or "") for d in q["json"]["pricingDefinitions"]))
        matched.append({"panPdcId":p["pdcId"],"sourceEvseId":actual,
          "station":p["station"],"match":"exact normalized eMI3 + CPO response",
          "directConsumerTariffValidated":False,
          "methodsSeenDuringIdentityProof":methods})
    if len(matched)!=54 or len(unmatched)!=1:raise ValueError("unexpected recovery count")
    if len({x["panPdcId"] for x in matched})!=54 or len({x["sourceEvseId"] for x in matched})!=54:raise ValueError("duplicate crosswalk")
    if set(x for v in matched for x in v["methodsSeenDuringIdentityProof"])!={"ROAMING_EMPS"}:
        raise ValueError("method drift: revalidate separation")
    if unmatched[0]["panPdcId"]!="FR55CEFR84160178MA103":raise ValueError("unresolved PAN identity changed")
    return {"schemaVersion":1,"source":"E55C official Scan Pay exact EVSE identity (NOT price)",
       "sourceRecoveryGeneratedAt":source["generatedAt"],"sourceSha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
       "matchedCount":54,"unmatchedCount":1,"records":matched,"unmatched":unmatched,
       "directTariffPromotionAuthorized":False,"requiresProductionConsumptionProof":True}
def main():
    report=json.loads(SOURCE.read_text());compiled=compile_crosswalk(report)
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    TARGET.write_text(json.dumps(compiled,ensure_ascii=False,indent=2)+"\n")
    print({"matched":compiled["matchedCount"],"unmatched":compiled["unmatchedCount"],"directPricesPromoted":0})
if __name__=="__main__":main()
