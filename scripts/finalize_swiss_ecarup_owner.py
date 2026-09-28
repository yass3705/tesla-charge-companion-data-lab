#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone
EX=Path("data/switzerland/ecarup-owner-direct-tariffs.json")
CO=Path("data/switzerland/ecarup-owner-coordinate-safe-overlay.json")
DOC=Path("docs/switzerland-ecarup-finalization-2026-09-28.json")
ex=json.loads(EX.read_text(encoding="utf-8")); co=json.loads(CO.read_text(encoding="utf-8"))
exact={x.get("evseId") for x in ex.get("evses",[]) if x.get("evseId")}
overlay={x.get("evseId") for x in co.get("evses",[]) if x.get("evseId")}
union=exact|overlay
n=ex.get("nationalEvseCount",co.get("nationalEvseCount",6764))
now=datetime.now(timezone.utc).isoformat()
out={"schemaVersion":1,"country":"CH","cpo":"eCarUp","operatorId":"CH*ECU","status":"complete" if len(union)==n else "partial","updatedAt":now,"nationalEvseCount":n,"exactConnectorPricedCount":len(exact),"safeCoordinateOverlayCount":len(overlay-exact),"pricedEvseCount":len(union),"unresolvedEvseCount":n-len(union),"method":"Exact normalized eCarUp Hubject connector IDs plus conservative <=3m coordinate overlay only where all public candidate connectors share one identical price tuple","policy":"No nearest-neighbour tariff selection; no cross-location extrapolation. Coordinate overlay is accepted only for one identical public price tuple across the full <=3m candidate set.","productionSources":[str(EX),str(CO)]}
DOC.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps(out,indent=2))

# final refreshed trigger
