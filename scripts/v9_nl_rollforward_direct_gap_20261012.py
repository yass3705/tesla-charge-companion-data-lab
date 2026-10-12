#!/usr/bin/env python3
"""Compare frozen 2026-10-11 DOT-NL scope with a dated, rolling DOT-NL snapshot.

Read-only Type 2 / CCS + AVAILABLE / CHARGING. Counts are connector
occurrences, not distinct public chargers or certified tariffs. Do not
promote this report into production pricing.
"""
import argparse
import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

from v9_nl_type2_ccs_scope_audit_20261012 import scan
from v9_nl_direct_tariff_compiler_audit_20261012 import evaluate

ROOT=Path(__file__).resolve().parents[1]
BASE_SHA="651d3723e67250ff9e5dfe0644a4b7973a8609ff08e3021b3f253cc5ef85ee93"
COUNTS=("type2CcsConnectorOccurrences","activeAvailableOrCharging",
        "activeWithTariffReference","activeWithoutTariffReference")

def compare(prev_scope,next_scope,prev_comp,next_comp,prev_sha,new_sha):
    before=prev_scope["totals"]
    after=next_scope["totals"]
    if before["activeAvailableOrCharging"]!=prev_comp["totalActiveType2CcsConnectorOccurrences"]:
        raise ValueError("Prior scope and compiler do not reconcile")
    if after["activeAvailableOrCharging"]!=next_comp["totalActiveType2CcsConnectorOccurrences"]:
        raise ValueError("Latest scope and compiler do not reconcile")
    if prev_comp["counts"]["noNationalReference"]!=before["activeWithoutTariffReference"]:
        raise ValueError("Prior missing-reference census inconsistent")
    if next_comp["counts"]["noNationalReference"]!=after["activeWithoutTariffReference"]:
        raise ValueError("New missing-reference census inconsistent")
    if sum(next_comp["counts"].values())!=after["activeAvailableOrCharging"]:
        raise ValueError("Latest compiler classes do not cover all active plugs")
    codes=sorted(set(prev_scope["operatorRows"])|set(next_scope["operatorRows"]))
    rows=[]
    for code in codes:
        a=prev_scope["operatorRows"].get(code,{})
        b=next_scope["operatorRows"].get(code,{})
        a_comp=prev_comp["cpoBreakdown"].get(code,{})
        b_comp=next_comp["cpoBreakdown"].get(code,{})
        old=a.get("activeWithoutTariffReference",0)
        new=b.get("activeWithoutTariffReference",0)
        rows.append({
            "cpoCode":code,"oldMissingRef":old,"newMissingRef":new,"deltaMissingRef":new-old,
            "oldActiveType2Ccs":a.get("activeAvailableOrCharging",0),
            "newActiveType2Ccs":b.get("activeAvailableOrCharging",0),
            "oldCompilerAccepted":a_comp.get("compiledNotSimulated",0),
            "newCompilerAccepted":b_comp.get("compiledNotSimulated",0),
            "newCompilerRejected":sum(v for k,v in b_comp.items()
                                      if k not in ("activeType2Ccs","compiledNotSimulated","noNationalReference")),
        })
    if sum(r["oldMissingRef"] for r in rows)!=before["activeWithoutTariffReference"]:
        raise ValueError("Lost old CPO gap entries")
    if sum(r["newMissingRef"] for r in rows)!=after["activeWithoutTariffReference"]:
        raise ValueError("Lost new CPO gap entries")
    return {
        "schemaVersion":1,"reportKind":"ROLLING_DOTNL_ACTIVE_TYPE2_CCS_DIRECT_CPO_GAP",
        "scope":"DOT NL geo-filter; active AVAILABLE or CHARGING, Type 2/CCS only",
        "oldDataAt":prev_scope["datasetGeneratedAt"],"currentDataAt":next_scope["datasetGeneratedAt"],
        "oldInputCompressedSha256":prev_sha,"currentInputCompressedSha256":new_sha,
        "oldTotals":{k:before[k] for k in COUNTS},
        "currentTotals":{k:after[k] for k in COUNTS},
        "delta":{k:after[k]-before[k] for k in COUNTS},
        "oldCompilerClasses":prev_comp["counts"],"currentCompilerClasses":next_comp["counts"],
        "currentCompilerReasons":next_comp["compilerRejectionReasons"],
        "currentRejectionSamples":{k:v for k,v in next_comp["examplesByClass"].items()
                                   if k not in ("compiledNotSimulated","noNationalReference")},
        "operatorsByCurrentMissingRef":sorted(rows,key=lambda r:(-r["newMissingRef"],r["cpoCode"])),
        "limitations":[
            "Connector occurrences, not necessarily unique EVSE or physical plug identities",
            "Status is a dated snapshot, not current physical public access",
            "A new active connector can change totals without a tariff change",
            "Compiled rule availability is not proof of correct numerical session simulation",
            "CPO codes require provider identity verification; no station-price inference",
            "No eMSP substitutions or invented direct prices",
        ],
        "publishedToTcc":False,
    }

def moment(s):
    return datetime.fromisoformat(str(s).replace("Z","+00:00"))

def execute(old_path,new_path):
    old_bytes=old_path.read_bytes()
    new_bytes=new_path.read_bytes()
    old_sha=hashlib.sha256(old_bytes).hexdigest()
    current_sha=hashlib.sha256(new_bytes).hexdigest()
    if old_sha!=BASE_SHA:
        raise ValueError("October 11 baseline bytes differ from locked SHA256")
    with gzip.open(old_path,"rt",encoding="utf-8") as file: old=json.load(file)
    with gzip.open(new_path,"rt",encoding="utf-8") as file: current=json.load(file)
    if moment(current.get("generatedAt"))<=moment(old.get("generatedAt")):
        raise ValueError("Rolling DOT-NL observation must be later than October 11")
    return compare(scan(old),scan(current),evaluate(old),evaluate(current),old_sha,current_sha)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--previous",type=Path,required=True)
    parser.add_argument("--current",type=Path,default=ROOT/"data/national/netherlands_dotnl/normalized.json.gz")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    report=execute(args.previous,args.current)
    print(json.dumps({
        "oldAt":report["oldDataAt"],"currentAt":report["currentDataAt"],
        "sourceSha":report["currentInputCompressedSha256"],
        "oldTotals":report["oldTotals"],"newTotals":report["currentTotals"],
        "delta":report["delta"],"currentCompilerClasses":report["currentCompilerClasses"],
        "newTopMissingByCpo":report["operatorsByCurrentMissingRef"][:12],
        "rejectionSamples":report["currentRejectionSamples"]
    },ensure_ascii=False))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
