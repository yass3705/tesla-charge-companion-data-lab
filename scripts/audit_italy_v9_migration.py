#!/usr/bin/env python3
"""Read-only Italy V9 source coverage audit. Never rewrites tariffs or production pins."""
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
ledger = json.loads((ROOT / "docs/italy-cpo-progress-2026-09.json").read_text())
baseline = ledger["inventoryBaselines"]["pun2026-09-20"]
sources = [
 "data/national/ionity_pun_inventory_italy_20260830.json.gz",
 "data/national/ionity_direct_stations_italy.json.gz",
 "data/national/atlante_direct_stations_italy_latest.json.gz",
 "data/national/allego_direct_stations_italy_20260925.json.gz",
 "data/national/ewiva_pos_direct_italy_candidate.json.gz",
 "data/national/freetox_direct_stations_italy.json.gz",
 "data/national/neogy_alperia_italy_v9_candidate.json.gz",
 "data/national/repower_italy_v9_candidate.json.gz",
]
inputs = [{"path":p,"present":(ROOT/p).is_file(),"bytes":(ROOT/p).stat().st_size if (ROOT/p).is_file() else None} for p in sources]
report = {
 "schemaVersion":1,
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "country":"IT",
 "mode":"read-only-pre-integration",
 "punBaseline":{"stations":baseline["stations"],"evse":baseline["uniqueEvse"],"partyIds":baseline["uniquePartyIds"]},
 "ledger":{"inventoryComplete":ledger.get("inventoryComplete"),"treated":ledger["counters"]["treated"],"partialCurrent":ledger["counters"]["partialCurrent"]},
 "directInputs":inputs,
 "compiledNationalSnapshotPresent":(ROOT/"data/national/italy-static/manifest.json").exists(),
 "nationalBuilder":{"path":"scripts/pun_italy_national.py","present":(ROOT/"scripts/pun_italy_national.py").is_file(),"defaultOutput":"data/national/pun_italy_national.json.gz"},
 "sourceSeparation":{"punNationalInventory":"technical and location baseline; numeric PUN tariffs not rankable without independent validation","directCpo":"operator-specific exact connector overlays","legacyItalyTiles":"must be regenerated and parity-tested before source switch"},
 "requiredBeforeSwitch":{"nationalGzipPresent":(ROOT/"data/national/pun_italy_national.json.gz").is_file(),"legacyStaticManifestRegenerated":(ROOT/"data/national/italy-static/manifest.json").is_file(),"legacyDirectOffersRegenerated":(ROOT/"data/national/italy-offers.json").is_file()},
 "readyForProductionSwitch":False,
 "blockers":["Full PUN station/EVSE static output and tiles are not yet certified equal to pinned Stable", "Validate EVSE connector/power/status and direct pricing against pinned Stable before modifying Production"],
}
out=ROOT/"reports/migration/italy-source-readiness-20261014.json"
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2))
assert baseline["stations"]>0 and baseline["uniqueEvse"]>0
assert all(x["present"] for x in inputs), "Some input datasets missing; investigate, do not auto-publish"
