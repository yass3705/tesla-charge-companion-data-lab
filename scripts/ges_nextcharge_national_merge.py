#!/usr/bin/env python3
"""Merge exact-identity NextCharge GES shards into a national research candidate."""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PREFIX="ITGESE"
RECOGNIZED={"energy","time","parking","session"}


def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def parse_uid(eid):
    s=str(eid or "").upper()
    if not s.startswith(PREFIX): return None
    t=s[len(PREFIX):]; return int(t) if t.isdigit() else None

def canonical_tariff(entry):
    t=entry.get("tariffSnapshot") or {}
    return json.dumps({"currency":t.get("currency"),"prices":t.get("prices") or {},"restrictions":t.get("restrictions") or {}},sort_keys=True,separators=(",",":"),ensure_ascii=False)
def valid_numeric_prices(t):
    p=t.get("prices") or {}
    return bool(p) and set(p)<=RECOGNIZED and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v)) for v in p.values())


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--pun",required=True); ap.add_argument("--shards-glob",default="/tmp/ges-shards/**/ges_nextcharge_shard_*.json.gz"); ap.add_argument("--out",default="data/national/nextcharge_ges_italy_candidate.json.gz"); ap.add_argument("--report",default="data/reports/ges_nextcharge_italy_national_report.json"); args=ap.parse_args()
    with gzip.open(args.pun,"rt",encoding="utf-8") as fh: pun=json.load(fh)
    pun_ges={str(e.get("evseId") or "").upper():e for e in pun.get("evses",[]) if str(e.get("partyId") or "").upper()=="GES" and e.get("evseId")}
    parseable={eid:e for eid,e in pun_ges.items() if parse_uid(eid) is not None}
    files=sorted(glob.glob(args.shards_glob,recursive=True))
    if not files: raise SystemExit("no shard files")

    rows=defaultdict(list); shard_counts=[]; stopped=[]; all_failures=[]
    for f in files:
        with gzip.open(f,"rt",encoding="utf-8") as fh: s=json.load(fh)
        shard_counts.append({"shard":s.get("shard"),**(s.get("counts") or {})})
        if (s.get("diagnostics") or {}).get("stoppedReason"): stopped.append({"shard":s.get("shard"),"reason":s["diagnostics"]["stoppedReason"]})
        all_failures.extend(s.get("failures") or [])
        for e in s.get("entries") or []:
            eid=str(e.get("evseId") or "").upper()
            if eid in parseable and e.get("exactIdentityMatch") is True: rows[eid].append(e)

    entries=[]; conflicting=[]; duplicate_same=0; currency=Counter(); components=Counter(); unknown_keys=Counter(); statuses=Counter();
    for eid,cands in sorted(rows.items()):
        tariffs=defaultdict(list)
        for e in cands: tariffs[canonical_tariff(e)].append(e)
        if len(tariffs)>1:
            conflicting.append({"evseId":eid,"variants":[json.loads(k) for k in tariffs]}); continue
        chosen=cands[0]
        if len(cands)>1: duplicate_same += len(cands)-1
        t=chosen.get("tariffSnapshot") or {}; p=t.get("prices") or {}
        currency[str(t.get("currency") or "unknown")]+=1
        for k,v in p.items():
            if v is not None: components[str(k)]+=1
            if k not in RECOGNIZED: unknown_keys[str(k)]+=1
        statuses[str(chosen.get("nextChargeConnectorStatus") or "unknown")]+=1
        consumer_snapshot_ok=(str(t.get("currency") or "").upper()=="EUR" and valid_numeric_prices(t))
        out=dict(chosen)
        out["consumerTariffSnapshotUsable"]=consumer_snapshot_ok
        # Deliberately not promoted as CPO-direct: official NextCharge terms define
        # this as the tariff charged to the NextCharge app user by Go Electric Stations.
        out["rankableAsCpoDirectTariff"]=False
        out["rankableAsNextChargeEmspTariff"]=consumer_snapshot_ok
        out["commercialSemantics"]="NextCharge consumer/eMSP tariff shown for the connector before charge; not assumed to equal the underlying CPO direct tariff"
        entries.append(out)

    matched={e["evseId"] for e in entries}; operational={eid for eid,e in parseable.items() if str(e.get("operationalState") or "").lower()=="operational"}
    matched_operational=matched & operational
    usable={e["evseId"] for e in entries if e.get("rankableAsNextChargeEmspTariff")}
    usable_operational=usable & operational
    missing=sorted(set(parseable)-matched)
    missing_operational=sorted(operational-matched)
    counts={
        "punGesEvse":len(pun_ges),"punGesParseableEvse":len(parseable),"punGesOperationalParseableEvse":len(operational),
        "shardFiles":len(files),"exactMatchedEvse":len(matched),"exactMatchCoverage":round(len(matched)/len(parseable),6) if parseable else 0,
        "exactMatchedOperationalEvse":len(matched_operational),"operationalExactMatchCoverage":round(len(matched_operational)/len(operational),6) if operational else 0,
        "usableNextChargeEmspTariffEvse":len(usable),"usableNextChargeCoverage":round(len(usable)/len(parseable),6) if parseable else 0,
        "usableOperationalNextChargeEmspTariffEvse":len(usable_operational),"usableOperationalCoverage":round(len(usable_operational)/len(operational),6) if operational else 0,
        "duplicateSameTariffRows":duplicate_same,"conflictingTariffEvse":len(conflicting),"missingExactEvse":len(missing),"missingOperationalExactEvse":len(missing_operational),
        "currencyDistribution":dict(currency),"tariffComponents":dict(components),"unknownPriceKeys":dict(unknown_keys),"connectorStatuses":dict(statuses),"rawShardFailures":len(all_failures),"stoppedShards":len(stopped),
    }
    gates={
        "allFourShardsPresent":len(files)==4,
        "noShardStoppedForCaptcha":not stopped,
        "exactCoverageGte85pct":counts["exactMatchCoverage"]>=0.85,
        "conflictingTariffEvseZero":not conflicting,
        "unknownPriceKeysZero":not unknown_keys,
        "matchedSubsetOfPunGes":matched<=set(parseable),
        "usableTariffNonzero":len(usable)>0,
    }
    payload={
        "generatedAt":now_iso(),"country":"IT","source":"NextCharge public web app","commercialLayer":"emsp","billedBy":"Go Electric Stations S.r.l.s.",
        "identityRule":"PUN GES evseId ITGESE<n> exactly equals NextCharge uidConnector <n>",
        "tariffSemantics":"Consumer tariff presented by NextCharge for each connector; components may include energy, time, parking and session and are additive per official NextCharge terms.",
        "entries":entries,
    }
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8") as fh: json.dump(payload,fh,ensure_ascii=False,separators=(",",":"))
    report={"generatedAt":now_iso(),"counts":counts,"qualityGates":gates,"shards":shard_counts,"stoppedShards":stopped,"conflicts":conflicting[:100],"missingExactEvseSample":missing[:200],"missingOperationalExactEvseSample":missing_operational[:200],"failureSample":all_failures[:100]}
    rp=Path(args.report); rp.parent.mkdir(parents=True,exist_ok=True); rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(counts,ensure_ascii=False,indent=2)); print(json.dumps(gates,ensure_ascii=False,indent=2))
    if not all(gates.values()): raise SystemExit(2)

if __name__=="__main__":main()
