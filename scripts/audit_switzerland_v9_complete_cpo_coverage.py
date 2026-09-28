#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"data/tcc_v9/switzerland.json"
PROG=ROOT/"docs/switzerland-cpo-progress-2026-09.json"
OUT=ROOT/"docs/switzerland-v9-complete-cpo-coverage-audit-2026-09-28.json"

b=json.loads(SRC.read_text(encoding="utf-8"))
p=json.loads(PROG.read_text(encoding="utf-8"))
evses=b.get("evses",[])

def match(e,op):
    eid=str(e.get("evseId") or "")
    if "*" in op: return eid.startswith(op+"*") or eid==op
    return eid.startswith(op)

rows=[]
for o in p.get("operators",[]):
    if o.get("status")!="complete": continue
    op=o.get("operatorId")
    xs=[e for e in evses if match(e,op)]
    counts={"resolved":0,"no_public_direct_tariff":0,"unresolved":0}
    for e in xs:
        st=e.get("directTariffStatus") or "unresolved"
        if st=="resolved": counts["resolved"]+=1
        elif st=="no_public_direct_tariff": counts["no_public_direct_tariff"]+=1
        else: counts["unresolved"]+=1
    covered=counts["resolved"]+counts["no_public_direct_tariff"]
    rows.append({
      "operatorId":op,"name":o.get("name"),"canonicalEvseCount":o.get("evseCount"),
      "bundleMatchedEvseCount":len(xs),"pricedEvseCount":counts["resolved"],
      "noPublicDirectTariffCount":counts["no_public_direct_tariff"],
      "unresolvedEvseCount":counts["unresolved"],"resolvedOrClassifiedCount":covered,
      "unresolvedEvseIds":[e.get("evseId") for e in xs if (e.get("directTariffStatus") or "unresolved")=="unresolved"],
      "coverageComplete": counts["unresolved"]==0,
      "scopeCountChanged": (o.get("evseCount") is not None and len(xs)!=o.get("evseCount"))
    })
issues=[x for x in rows if not x["coverageComplete"]]
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"completeCpoCount":len(rows),"issueCount":len(issues),"issues":issues,"operators":rows}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"completeCpoCount":len(rows),"issueCount":len(issues),"issues":issues},ensure_ascii=False,indent=2))
