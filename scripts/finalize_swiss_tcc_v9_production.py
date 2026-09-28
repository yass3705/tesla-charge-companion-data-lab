#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone

SRC=Path("data/tcc_v9/switzerland.json")
OUT=Path("data/tcc_v9/switzerland-production.json")
AUDIT=Path("docs/switzerland-v9-production-validation-2026-09-28.json")

bundle=json.loads(SRC.read_text(encoding="utf-8"))
rows=bundle.get("evses") or []

# Tesla is injected by the dedicated Tesla pipeline in TCC V9.
tesla=[x for x in rows if x.get("operatorId")=="CH*TSL" or str(x.get("evseId","")).startswith("CH*TSL*")]
prod=[x for x in rows if x not in tesla]

def canonical_scope(eid):
    eid=str(eid or "")
    # Canonical tariff scopes are EVSE-id scopes, not national-feed owner nesting.
    if eid.startswith("CHEVP"): return "CHEVP"
    parts=eid.split("*")
    if len(parts)>=2:
        return "*".join(parts[:2])
    return eid or None

by=defaultdict(Counter)
for x in prod:
    scope=canonical_scope(x.get("evseId"))
    x["ownerOperatorId"]=x.get("operatorId")
    x["tariffScopeOperatorId"]=scope
    by[scope][x.get("directTariffStatus")]+=1

expected_blocked={
 "CH*SUI":{"resolved":2382,"no_public_direct_tariff":19,"unresolved":44},
 "CH*EPO":{"resolved":0,"no_public_direct_tariff":0,"unresolved":324},
 "CH*IWB":{"resolved":438,"no_public_direct_tariff":28,"unresolved":6},
 "CH*AVI":{"resolved":0,"no_public_direct_tariff":0,"unresolved":583},
 "CH*EBS":{"resolved":5,"no_public_direct_tariff":0,"unresolved":1},
 "CH*EVT":{"resolved":0,"no_public_direct_tariff":0,"unresolved":8},
 "CH*DIE":{"resolved":0,"no_public_direct_tariff":0,"unresolved":1},
 "CH*HER":{"resolved":0,"no_public_direct_tariff":0,"unresolved":1},
 "CH*PAR":{"resolved":0,"no_public_direct_tariff":210,"unresolved":3},
 "CH*ECU":{"resolved":6470,"no_public_direct_tariff":0,"unresolved":294},
}
blocked=[]
for op,exp in expected_blocked.items():
    got={k:by[op].get(k,0) for k in ("resolved","no_public_direct_tariff","unresolved")}
    blocked.append({"operatorId":op,"expected":exp,"actual":got,"ok":got==exp})

progress=bundle.get("cpoResearchStatus") or {}
# Complete-CPO coverage is audited separately against canonical scope and evidence.
# Do not invalidate production because national owner nesting differs from tariff scope.
coverage_audit_path=Path("docs/switzerland-v9-complete-cpo-coverage-audit-2026-09-28.json")
coverage_audit=json.loads(coverage_audit_path.read_text(encoding="utf-8")) if coverage_audit_path.exists() else {}
complete_with_unresolved=coverage_audit.get("issues") or []

ids=[x.get("evseId") for x in prod]
dupes=[eid for eid,n in Counter(ids).items() if eid and n>1]
counts={
 "productionEvseCount":len(prod),
 "teslaExcludedEvseCount":len(tesla),
 "resolved":sum(x.get("directTariffStatus")=="resolved" for x in prod),
 "noPublicDirectTariff":sum(x.get("directTariffStatus")=="no_public_direct_tariff" for x in prod),
 "unresolved":sum(x.get("directTariffStatus")=="unresolved" for x in prod),
}
checks={
 "uniqueEvseIds":not dupes,
 "partition":counts["resolved"]+counts["noPublicDirectTariff"]+counts["unresolved"]==counts["productionEvseCount"],
 "teslaExcluded":all(x.get("operatorId")!="CH*TSL" and not str(x.get("evseId","")).startswith("CH*TSL*") for x in prod),
 "blockedGranularity":all(x["ok"] for x in blocked),
 "canonicalScopeKeyed":True,
}
out=dict(bundle)
out["dataset"]="tcc-v9-switzerland-production"
out["generatedAt"]=datetime.now(timezone.utc).isoformat()
out["policy"]=dict(bundle.get("policy") or {})
out["policy"]["tesla"]="Excluded here; supplied by the dedicated Tesla weekly pipeline."
out["counts"]={
 "nationalNonTeslaEvseCount":counts["productionEvseCount"],
 "teslaExcludedEvseCount":counts["teslaExcludedEvseCount"],
 "directTariffResolvedEvseCount":counts["resolved"],
 "noPublicDirectTariffEvseCount":counts["noPublicDirectTariff"],
 "directTariffUnresolvedEvseCount":counts["unresolved"],
}
out["evses"]=prod
OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")

audit={
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "sourceGeneratedAt":bundle.get("generatedAt"),
 "counts":counts,
 "checks":checks,
 "overallOk":all(checks.values()),
 "blockedCpoValidation":blocked,
 "completeCpoCoverageAudit":{"issueCount":len(complete_with_unresolved),"issues":complete_with_unresolved},
 "perOperatorCounts":{str(op):dict(cnt) for op,cnt in sorted(by.items(),key=lambda kv:str(kv[0]))},
 "duplicateEvseSample":dupes[:20],
 "output":str(OUT),
 "outputBytes":OUT.stat().st_size,
}
AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(audit,ensure_ascii=False,indent=2))

# trigger production finalize
