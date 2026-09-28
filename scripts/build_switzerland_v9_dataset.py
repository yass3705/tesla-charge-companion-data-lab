#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"data/tcc_v9/switzerland.json"
OUT=ROOT/"data/national/switzerland_public_charging_v9.json"
REPORT=ROOT/"docs/switzerland-v9-canonical-integration-2026-09-28.json"

def main():
    src=json.loads(SRC.read_text(encoding="utf-8"))
    rows=[]
    priced=no_public=unresolved=0
    used={}
    for ev in src.get("evses",[]):
        status=ev.get("directTariffStatus") or "unresolved"
        overlays=ev.get("directTariffs") or []
        if status=="resolved":
            priced+=1
            for x in overlays:
                f=x.get("sourceFile")
                if f: used[f]=used.get(f,0)+1
        elif status=="no_public_direct_tariff":
            no_public+=1
        else:
            unresolved+=1
        rows.append({
          "evseId":ev.get("evseId"),
          "operatorId":ev.get("operatorId"),
          "operatorName":ev.get("operatorName"),
          "chargingStationId":ev.get("stationId"),
          "names":ev.get("names"),
          "address":ev.get("address"),
          "coordinates":ev.get("coordinates"),
          "plugs":ev.get("plugs"),
          "chargingFacilities":ev.get("chargingFacilities"),
          "accessibility":ev.get("accessibility"),
          "authenticationModes":ev.get("authenticationModes"),
          "paymentOptions":ev.get("paymentOptions"),
          "isOpen24Hours":ev.get("isOpen24Hours"),
          "directTariff":{
             "status":"priced" if status=="resolved" else status,
             "overlays":overlays,
             "classification":ev.get("directTariffClassification")
          }
        })
    progress=src.get("cpoResearchStatus") or {}
    status_counts={}
    for x in progress.values():
        s=x.get("status","unknown"); status_counts[s]=status_counts.get(s,0)+1
    now=datetime.now(timezone.utc).isoformat()
    payload={
      "schemaVersion":2,
      "dataset":"switzerland-public-charging-v9",
      "country":"CH",
      "generatedAt":now,
      "sourceBundle":"data/tcc_v9/switzerland.json",
      "baseInventory":{"source":src.get("nationalSource"),"role":"authoritative physical EVSE/station inventory"},
      "overlayPolicy":{
        "joinSource":"prevalidated Switzerland TCC V9 bundle",
        "noCrossStationExtrapolation":True,
        "unresolvedPriceKeepsEvseVisible":True,
        "blockedCpoDoesNotHideResolvedEvses":True,
        "roamingLayersSeparate":["Electra","Electroverse"],
        "teslaHandledSeparately":True
      },
      "summary":{
        "nationalEvseCount":len(rows),
        "directPricedEvseCount":priced,
        "classifiedNoPublicDirectTariffCount":no_public,
        "directUnresolvedEvseCount":unresolved,
        "directResolvedEvseCount":priced+no_public,
        "operatorStatusCounts":status_counts
      },
      "cpoResearchStatus":progress,
      "usedSourceCounts":used,
      "evses":rows
    }
    assert payload["summary"]["nationalEvseCount"]==src["counts"]["nationalEvseCount"]
    assert priced==src["counts"]["directTariffResolvedEvseCount"]
    assert no_public==src["counts"]["noPublicDirectTariffEvseCount"]
    assert unresolved==src["counts"]["directTariffUnresolvedEvseCount"]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    rep={k:v for k,v in payload.items() if k!="evses"}
    rep["output"]=str(OUT.relative_to(ROOT)); rep["outputBytes"]=OUT.stat().st_size
    REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload["summary"],ensure_ascii=False))

if __name__=="__main__":
    main()

# refresh after final Swiss bundle
