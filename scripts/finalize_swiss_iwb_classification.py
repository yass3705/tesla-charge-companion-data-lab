#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone

SRC=Path("docs/switzerland-iwb-owner-reconciliation-2026-09-28.json")
OUT=Path("docs/switzerland-iwb-finalization-2026-09-28.json")
j=json.loads(SRC.read_text(encoding="utf-8"))
cc=j["classCounts"]
resolved=cc.get("priced_exact",0)+cc.get("restricted_no_auth",0)
unresolved=cc.get("public_unpriced",0)+cc.get("owner_not_seen_in_atlas",0)
out={
 "schemaVersion":1,"country":"CH","cpo":"IWB","operatorId":"CH*IWB",
 "status":"complete" if unresolved==0 else "partial",
 "updatedAt":datetime.now(timezone.utc).isoformat(),
 "nationalEvseCount":j["nationalOwnerEvseCount"],
 "pricedEvseCount":cc.get("priced_exact",0),
 "classifiedNoPublicDirectTariffCount":cc.get("restricted_no_auth",0),
 "resolvedEvseCount":resolved,
 "unresolvedEvseCount":unresolved,
 "publicUnpricedEvseCount":cc.get("public_unpriced",0),
 "ownerNotSeenInAtlasCount":cc.get("owner_not_seen_in_atlas",0),
 "method":"Current national CH*IWB owner scope + exact direct-tariff matches + explicit restricted/no-auth classification",
 "policy":"Exact current owner scope only. Restricted records with no authentication modes are classified no-public-direct. Public unpriced and owner-not-seen records remain unresolved; no tariff extrapolation.",
 "evidenceSource":str(SRC)
}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
