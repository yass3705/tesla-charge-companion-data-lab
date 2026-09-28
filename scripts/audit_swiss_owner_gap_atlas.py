#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone
import collect_swiss_atlas_cpo as atlas

OPS=[
 "CH*PAR","CH*REP","CH*911","CHEVP","CH*CPI","CH*505","CH*TAE",
 "CH*ENMOBILECHARGE","CH*MOBIMOEMOBILITY","CH*BCK","CH*EVAEMOBILITAET","CH*PACEMOBILITY"
]
key=atlas.extract_public_key()
rows=[]
for op in OPS:
    try:
        st=atlas.station_pages(op,key)
        rows.append({"operatorId":op,"atlasStationCount":len(st),
                     "sample":[{"id":x.get("id"),"name":(x.get("attributes") or {}).get("name"),
                                "evseOperator":(x.get("attributes") or {}).get("evse_operator"),
                                "evseIds":((x.get("attributes") or {}).get("evse_ids") or [])[:5]} for x in st[:5]]})
    except Exception as e:
        rows.append({"operatorId":op,"error":type(e).__name__+": "+str(e),"atlasStationCount":None})
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"operators":rows}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-owner-gap-atlas-census-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(rows,ensure_ascii=False,indent=2))
