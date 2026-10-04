#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"docs/v9-country-progress-2026-09-30.json"

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    idx=load(INDEX)
    assert idx["policy"]=="fail-closed"
    c=idx["countries"]

    fr=c["FR"]["counters"]
    fr_ledger=load(ROOT/c["FR"]["ledger"])
    assert fr["totalCpos"]==291
    assert fr["treated"]+fr["setAside"]+fr["activeBusiness"]+fr["historicalResolvedSlots"]==fr["totalCpos"]
    assert fr=={
        "totalCpos":fr_ledger["totalCpos"],
        "treated":fr_ledger["treatedCpos"],
        "setAside":fr_ledger["setAsideCpos"],
        "activeBusiness":fr_ledger["activeRemainingCpos"],
        "historicalResolvedSlots":fr_ledger["historicalResolvedSlots"],
    }, (fr, fr_ledger["treatedCpos"], fr_ledger["setAsideCpos"], fr_ledger["activeRemainingCpos"], fr_ledger.get("historicalResolvedSlots"))

    de=c["DE"]["counters"]
    assert de["totalNamedCpos"]==591
    assert de["complete"]+de["partial"]+de["blocked"]==de["totalNamedCpos"]

    it=c["IT"]["counters"]
    assert it["currentPunPartyIds"]==it["currentPunNamedInCanonical"]==92
    assert it["unreconciledCurrentPunPartyIds"]==0
    assert it["treated"]+it["partialCurrent"]==it["currentPunPartyIds"]

    uk=c["UK"]["counters"]
    assert uk["complete"]+uk["actionablePartial"]+uk["setAsideOrExternalBlocked"]+uk["other"]==uk["canonicalCpos"]
    assert c["UK"]["firstPassComplete"] is True

    required={"TESLA","ES","NL","CH","FR","IT","DE","UK","MA"}
    assert set(c)==required
    assert c["ES"]["coverage"]=="complete"
    assert c["NL"]["coverage"]=="complete"
    assert c["CH"]["coverage"]=="complete-with-fail-closed-residuals"

    print(json.dumps({
      "status":"ok",
      "countries":len(c),
      "FR":fr,
      "DE":de,
      "IT":{"currentPunPartyIds":it["currentPunPartyIds"],"treated":it["treated"],"partialCurrent":it["partialCurrent"]},
      "UK":uk
    },ensure_ascii=False))

if __name__=="__main__":
    main()
