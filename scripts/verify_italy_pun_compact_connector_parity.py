#!/usr/bin/env python3
"""Fail-closed EVSE/connector/power parity between PUN source and V9 compact rows."""
import argparse, collections, gzip, json
from pathlib import Path

def load(p):
    raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix==".gz" else raw)

def inventory(pun):
    result=collections.Counter()
    skipped=collections.Counter()
    for st in pun["stations"]:
        for ev in st.get("evses",[]):
            eid=str(ev.get("evseId") or "").strip()
            for c in ev.get("connectors",[]):
                kind=str(c.get("standard") or "").upper()
                if "COMBO" in kind or "CCS" in kind: kind="CCS"
                elif "TYPE_2" in kind or "TYPE2" in kind: kind="TYPE2"
                else: skipped[kind]+=1;continue
                power=c.get("maxPowerKw")
                if not isinstance(power,(int,float)) or power<=0: skipped["missing_power"]+=1;continue
                cid=str(c.get("connectorId") or st.get("stationKey"))
                result[(eid,cid,kind,round(float(power),6))]+=1
    return result,skipped

def compact_inventory(rows):
    result=collections.Counter()
    for row in rows:
        for cfg in row[8]:
            ident=str(cfg[0])
            if ":connector:" not in ident:continue
            eid,cid=ident.rsplit(":connector:",1)
            result[(eid,cid,str(cfg[2]),round(float(cfg[3]),6))]+=1
    return result

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--pun",type=Path,required=True)
    a.add_argument("--compact",type=Path,required=True)
    a.add_argument("--report",type=Path,required=True)
    args=a.parse_args()
    expected,skipped=inventory(load(args.pun))
    actual=compact_inventory(load(args.compact))
    missing=expected-actual
    unexpected=actual-expected
    report={"expectedConnectorOccurrences":sum(expected.values()),
            "compactConnectorOccurrences":sum(actual.values()),
            "skippedUnsupportedConnectors":dict(skipped),
            "missingConnectorOccurrences":sum(missing.values()),
            "unexpectedConnectorOccurrences":sum(unexpected.values()),
            "missingExamples":[list(x) for x in list(missing)[:12]],
            "unexpectedExamples":[list(x) for x in list(unexpected)[:12]],
            "exactEvseConnectorPowerParity":not missing and not unexpected,
            "readyForProductionSwitch":False}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    if missing or unexpected:raise SystemExit(1)

if __name__=="__main__":main()
