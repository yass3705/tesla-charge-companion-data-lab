#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
src=ROOT/"reports/driveco/inventory_tariffs_latest.json"
out=ROOT/"reports/france/driveco/direct-scope-reconciliation.json"
x=json.loads(src.read_text(encoding="utf-8"))
classes=x.get("networkClassRows") or {}
direct_total=int(classes.get("driveco_network") or 0)
partner_total=int(classes.get("partner_network") or 0)
other_total=sum(int(v or 0) for k,v in classes.items() if k not in ("driveco_network","partner_network"))
direct_priced=0
partner_priced=0
for t in x.get("tarificationValues") or []:
    nc=t.get("networkClasses") or {}
    direct_priced += int(nc.get("driveco_network") or 0)
    partner_priced += int(nc.get("partner_network") or 0)
assert direct_priced <= direct_total
payload={
 "schemaVersion":"1.0.0","country":"FR","operator":"DRIVECO",
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "sourcePath":"reports/driveco/inventory_tariffs_latest.json",
 "sourceGeneratedAt":x.get("generatedAt"),
 "scope":{
   "drivecoNetworkRows":direct_total,
   "partnerNetworkRows":partner_total,
   "otherRows":other_total,
   "drivecoRowsWithPublishedTarification":direct_priced,
   "drivecoRowsWithoutPublishedTarification":direct_total-direct_priced,
   "drivecoPublishedTarificationCoverage":direct_priced/direct_total if direct_total else 0,
   "partnerRowsWithPublishedTarification":partner_priced
 },
 "decision":{
   "partnerNetworkExcludedFromDrivecoDirectGap":True,
   "reason":"Rows explicitly classified as partner_network/powered by DRIVECO are not eligible for inheritance of a DRIVECO CPO-direct tariff.",
   "failClosedResidual":direct_total-direct_priced,
   "noTariffInheritance":True
 },
 "supersedesGapInterpretation":{
   "oldInventoryWideResidual":int(x.get("rowCount") or 0)-int(x.get("rowsWithTarification") or 0),
   "correctDrivecoDirectResidual":direct_total-direct_priced
 }
}
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False,indent=2))
