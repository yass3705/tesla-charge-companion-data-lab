#!/usr/bin/env python3
"""Extract every active Type 2/CCS DOT-NL direct tariff as weighted, per-power fixtures.

Read-only staging input for the real production V9 engine. This does not validate
public access, does not publish prices, and does not certify CPO commercial terms.
"""
import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path

from dotnl_netherlands_runtime import choose_tariff, date_of
from v9_nl_type2_ccs_scope_audit_20261012 import valid_nl, plug, ACTIVE

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/national/netherlands_dotnl/normalized.json.gz"

def fixtures(data):
    date=date_of(data.get("generatedAt"))
    if date is None: raise ValueError("No trusted DOT-NL snapshot effective date")
    tariffs=data.get("tariffs")
    if not isinstance(tariffs,dict): raise ValueError("DOT-NL tariff catalog unavailable")
    compile_cache={};select_cache={}
    stats={"unsupportedReasons":collections.Counter(),"ambiguousTariffConnectors":0}
    groups={};active=compiled=missing=other=0
    for station in data.get("stations") or []:
        if not valid_nl(station) or not station.get("stationId"): continue
        cpo=str(station.get("partyId") or "UNKNOWN").upper()
        for evse in station.get("evses") or []:
            if str(evse.get("status") or "").upper() not in ACTIVE: continue
            for conn in evse.get("connectors") or []:
                connector_kind=plug(conn.get("standard"))
                if not connector_kind: continue
                active+=1
                keys=conn.get("tariffKeys") or []
                if not isinstance(keys,list): raise ValueError("Malformed DOT-NL tariff keys")
                if not keys:
                    missing+=1
                    continue
                selected,rules,error=choose_tariff(keys,tariffs,date,stats,compile_cache,select_cache)
                if not selected or not rules:
                    other+=1
                    continue
                compiled+=1
                power=conn.get("powerKw")
                try:
                    power=float(power)
                except (ValueError,TypeError):
                    power=0.0
                if not math.isfinite(power):
                    power=0.0
                power=round(power,3)
                implausible=power<=0 or power>2000
                # Preserve power, physical connector type and operator. A
                # tariff key reused at different powers must NOT be flattened.
                ident=(cpo,selected,connector_kind,power)
                if ident not in groups:
                    groups[ident]={
                        "cpo":cpo,"tariffKey":selected,
                        "connectorKind":"AC" if connector_kind=="TYPE_2" else "DC",
                        "standard":conn.get("standard"),"powerKw":power,
                        "count":0,"sourcePowerPlausible":not implausible,
                        "sampleStationId":station.get("stationId"),
                        "sampleEvseId":evse.get("evseId") or evse.get("uid"),
                        "sampleConnectorId":conn.get("id"),
                        "rules":rules
                    }
                groups[ident]["count"]+=1
    if active != compiled+missing+other or not groups:
        raise ValueError("DOT-NL fixture reconciliation failed")
    if sum(group["count"] for group in groups.values())!=compiled:
        raise ValueError("Weighted groups do not conserve compiled connectors")
    out={
      "schemaVersion":1,
      "status":"FROZEN_DIRECT_CPO_SIMULATION_INPUTS_NOT_PUBLIC_PRICE_PROOF",
      "sourceGeneratedAt":data["generatedAt"],
      "timeZone":"Europe/Amsterdam",
      "activeConnectors":active,
      "compiledConnectors":compiled,
      "noTariffReference":missing,
      "otherRejected":other,
      "uniquePowerConnectorTariffGroups":len(groups),
      "implausiblePowerConnectorOccurrences":sum(g["count"] for g in groups.values() if not g["sourcePowerPlausible"]),
      "groups":sorted(groups.values(),key=lambda g:(g["cpo"],g["tariffKey"],g["connectorKind"],g["powerKw"])),
      "publishedToTcc":False
    }
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,default=SOURCE)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    with gzip.open(args.source,"rt",encoding="utf-8") as inp: source=json.load(inp)
    report=fixtures(source)
    report["inputCompressedSha256"]=hashlib.sha256(args.source.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="groups"},ensure_ascii=False))

if __name__=="__main__":
    main()
