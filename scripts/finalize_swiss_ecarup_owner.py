#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone
EX=Path("data/switzerland/ecarup-owner-direct-tariffs.json")
CO=Path("data/switzerland/ecarup-owner-coordinate-safe-overlay.json")
DOC=Path("docs/switzerland-ecarup-finalization-2026-09-28.json")
ex=json.loads(EX.read_text(encoding="utf-8")); co=json.loads(CO.read_text(encoding="utf-8"))
n=(ex.get("counts") or {}).get("nationalEvseCount")
if not isinstance(n,int) or n<0 or co.get("nationalEvseCount")!=n:
    raise ValueError("eCarUp exact and coordinate snapshots disagree on national source")
priced={x.get("evseId") for x in ex.get("evses",[]) if x.get("classification")=="priced_public_direct"}
restricted={x.get("evseId") for x in ex.get("evses",[]) if x.get("classification") in ("restricted_or_nonpublic_connector","restricted_no_public_direct_tariff")}
overlay={x.get("evseId") for x in co.get("evses",[])}
if None in priced|restricted|overlay or priced&restricted or overlay&(priced|restricted):
    raise ValueError("eCarUp finalization identity or pricing scope conflict")
unresolved=n-len(priced)-len(restricted)-len(overlay)
if unresolved<0: raise ValueError("eCarUp finalization identities exceed national source")
now=datetime.now(timezone.utc).isoformat()
out={"schemaVersion":1,"country":"CH","cpo":"eCarUp","operatorId":"CH*ECU","status":"complete" if unresolved==0 else "partial","updatedAt":now,"nationalEvseCount":n,"exactConnectorPricedCount":len(priced),"exactRestrictedCount":len(restricted),"safeCoordinateOverlayCount":len(overlay),"pricedEvseCount":len(priced)+len(overlay),"unresolvedEvseCount":unresolved,"method":"Exact normalized eCarUp Hubject connector IDs plus conservative <=3m coordinate overlay only where all public candidate connectors share one identical price tuple","policy":"No nearest-neighbour tariff selection; no cross-location extrapolation. Coordinate overlay is accepted only for one identical public price tuple across the full <=3m candidate set.","productionSources":[str(EX),str(CO)]}
DOC.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps(out,indent=2))

# final refreshed trigger
