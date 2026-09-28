#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone

B=Path("data/tcc_v9/switzerland.json")
P=Path("docs/switzerland-cpo-progress-2026-09.json")
O=Path("docs/switzerland-v9-validation-2026-09-28.json")

bundle=json.loads(B.read_text(encoding="utf-8"))
progress=json.loads(P.read_text(encoding="utf-8"))
rows=bundle["evses"]

ids=[x["evseId"] for x in rows]
dupes=[x for x,n in Counter(ids).items() if n>1]
by_owner=defaultdict(lambda: Counter())
for x in rows:
    by_owner[x.get("operatorId")][x.get("directTariffStatus")]+=1

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
checks=[]
for op,exp in expected_blocked.items():
    got={k:by_owner[op].get(k,0) for k in ("resolved","no_public_direct_tariff","unresolved")}
    checks.append({"operatorId":op,"expected":exp,"actual":got,"ok":got==exp})

complete_ops=[x["operatorId"] for x in progress.get("operators",[]) if x.get("status")=="complete"]
complete_with_unresolved=[{"operatorId":op,"unresolved":by_owner[op].get("unresolved",0),"counts":dict(by_owner[op])} for op in complete_ops if by_owner[op].get("unresolved",0)>0]

tesla=dict(by_owner.get("CH*TSL",{}))
sum_counts=bundle["counts"]["directTariffResolvedEvseCount"]+bundle["counts"]["noPublicDirectTariffEvseCount"]+bundle["counts"]["directTariffUnresolvedEvseCount"]
validation={
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "bundleGeneratedAt":bundle.get("generatedAt"),
 "checks":{
   "uniqueEvseIds":{"ok":not dupes,"duplicateCount":len(dupes),"sample":dupes[:20]},
   "countPartition":{"ok":sum_counts==bundle["counts"]["nationalEvseCount"],"sum":sum_counts,"national":bundle["counts"]["nationalEvseCount"]},
   "blockedCpoGranularity":{"ok":all(x["ok"] for x in checks),"details":checks},
   "completeCposHaveNoUnresolved":{"ok":not complete_with_unresolved,"details":complete_with_unresolved},
   "teslaSeparatePipeline":{"ok":len(tesla)>0,"bundleCounts":tesla,"note":"Presence in this direct-CPO bundle is a duplication risk because CH*TSL is handled-separately in canonical progress."}
 }
}
validation["overallOkExcludingTeslaSeparation"]=all(v["ok"] for k,v in validation["checks"].items() if k!="teslaSeparatePipeline")
O.write_text(json.dumps(validation,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(validation,ensure_ascii=False,indent=2))
if not validation["overallOkExcludingTeslaSeparation"]:
    raise SystemExit(2)
