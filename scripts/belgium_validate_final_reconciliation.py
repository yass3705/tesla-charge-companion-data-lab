#!/usr/bin/env python3
import json
from pathlib import Path

progress=json.loads(Path("docs/belgium-cpo-progress-2026-09.json").read_text())
final=json.loads(Path("reports/belgium/belgium-final-gap-reconciliation-2026-09-28.json").read_text())
shell=json.loads(Path("data/operator_direct/shell_belgium_official_2026-09-28.json").read_text())
detail=json.loads(Path("reports/belgium/belgium-residual-unpriced-detail-v2-2026-09-28.json").read_text())

assert progress["counts"]=={"complete":64,"partial":7,"blocked":0,"total":71}
assert final["inputMissingPriceEvses"]==12858
d=final["decisions"]
assert d["resolvedExactOfficial"]+d["excludedNonProduction"]+d["unresolvedSourceLimited"]==12858
assert shell["count"]==8==len(shell["entries"])
assert len({tuple(x["externalIdentifiers"]) for x in shell["entries"]})==8
assert all(x["powerW"]>50000 for x in shell["entries"])
assert all(x["tariff"]["price"]==0.79 and x["tariff"]["currency"]=="EUR" and x["tariff"]["taxIncluded"] is True for x in shell["entries"])
missing_shell={tuple(x["externalIdentifiers"]) for x in detail["targets"]["Shell Recharge"]["items"]}
assert all(tuple(x["externalIdentifiers"]) in missing_shell for x in shell["entries"])
assert detail["targets"]["Gabriels"]["count"]==1
g=detail["targets"]["Gabriels"]["items"][0]
assert "test location" in (g.get("brand") or "").lower()
assert g.get("status")=="inoperative"
assert max([c.get("maxPowerW") or 0 for c in g.get("connectors") or []] or [0])==0
expected_unresolved=12729+16+2+60+30+12
assert expected_unresolved==12849==d["unresolvedSourceLimited"]
out={
 "ok":True,
 "rawCpos":progress["counts"],
 "rawMissing":12858,
 "resolvedExactOfficial":8,
 "excludedNonProduction":1,
 "unresolvedSourceLimited":12849,
 "shellOverlayEntries":8,
 "productionPartialRemaining":final["productionSummary"]["productionPartialRemaining"]
}
Path("reports/belgium/belgium-final-reconciliation-validation-2026-09-28.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
