#!/usr/bin/env python3
"""Read-only Agri Go (AGO) Dutch EVSE plug/power/site-evidence inventory.

No pricing assigned. Agri Go official PAYG AC rate depends on location
context that a 22 kW connector does NOT independently establish.
"""
import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
from v9_nl_type2_ccs_scope_audit_20261012 import plug,valid_nl,ACTIVE

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/national/netherlands_dotnl/normalized.json.gz"
SUSPECT_FIELDS=("access","parkingType","parking_type","locationType",
                "location_type","parking","facilities","type")

def classify(kind,power):
    # 60 kW exact is deliberately a boundary of overlapping official text.
    if kind=="TYPE_2":
        return "AC_RESIDENTIAL_OR_PUBLIC_PARKING_CONTEXT_REQUIRED"
    if kind=="CCS":
        if power is None or power<22:return "DC_POWER_OR_TIER_UNVERIFIED"
        if power<60:return "DC_22_TO_UNDER_60_KW_CANDIDATE"
        if power==60:return "DC_EXACTLY_60_KW_OFFICIAL_BOUNDARY_AMBIGUOUS"
        return "DC_OVER_60_KW_CANDIDATE"
    return "NOT_IN_SCOPE"

def inventory(data,limit=15):
    rows=collections.Counter()
    candidate=collections.Counter()
    status=collections.Counter()
    meta=collections.Counter()
    metaValues=collections.defaultdict(collections.Counter)
    samples=[]
    selected=0
    for station in data.get("stations") or []:
        if str(station.get("partyId") or "").upper()!="AGO" or not valid_nl(station):
            continue
        context={k:station[k] for k in SUSPECT_FIELDS if station.get(k) is not None}
        for k,val in context.items():
            meta[k]+=1
            compact=str(val)
            if len(compact)<100:
                metaValues[k][compact]+=1
        for evse in station.get("evses") or []:
            state=str(evse.get("status") or "UNKNOWN").upper()
            for conn in evse.get("connectors") or []:
                kind=plug(conn.get("standard"))
                if not kind: continue
                status[state]+=1
                if state not in ACTIVE:continue
                selected+=1
                raw=conn.get("powerKw")
                try: power=float(raw)
                except (ValueError,TypeError):power=None
                if power is not None and not math.isfinite(power):power=None
                level=classify(kind,power)
                powerString="UNKNOWN" if power is None else format(power,".3f").rstrip("0").rstrip(".")
                rows[(kind,powerString)]+=1
                candidate[level]+=1
                if len(samples)<limit:
                    samples.append({
                        "stationId":station.get("stationId"),
                        "evseId":evse.get("evseId") or evse.get("uid"),
                        "connectorId":conn.get("id"),
                        "kind":kind,"powerKw":power,
                        "context":context,
                        "note":"Not proof of public access or official rate match",
                    })
    if selected!=sum(rows.values()) or selected!=sum(candidate.values()):
        raise ValueError("Missing AGO plug occurrences in breakdown")
    return {
        "schemaVersion":1,
        "sourceGeneratedAt":data.get("generatedAt"),
        "cpoCode":"AGO",
        "scope":"NL-bounded AGO, Type 2/CCS, EVSE AVAILABLE/CHARGING",
        "totalActiveType2Ccs":selected,
        "byKindPower":[{"kind":k,"powerKw":p,"active":n}
                        for (k,p),n in sorted(rows.items())],
        "byUnassignedTariffCandidate":dict(sorted(candidate.items())),
        "statusCountsAllType2Ccs":dict(sorted(status.items())),
        "stationContextFieldsPresent":dict(meta),
        "stationContextValueCounts":{
            k:dict(sorted(v.items())) for k,v in sorted(metaValues.items())},
        "sampleEvseSources":samples,
        "officialDirectTariffPage":"https://agrigo.nl/charge/tarieven/",
        "pricingAssigned":False,
        "publishedToTcc":False,
        "warnings":[
            "AC residential versus public parking requires station classification, not power inference",
            "Official page says ad-hoc QR displays actual station-specific current price",
            "Connection after-minutes charges are not optional flat surcharges",
            "Physical public access not verified; garage/private sites must be reviewed",
            "DC 60 kW boundary is textually ambiguous and must not be guessed",
            "No roaming or eMSP prices used"
        ],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=SOURCE)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    with gzip.open(args.input,"rt",encoding="utf-8") as file:
        data=json.load(file)
    result=inventory(data)
    result["compressedInputSha256"]=hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "at":result["sourceGeneratedAt"],"sha":result["compressedInputSha256"],
        "total":result["totalActiveType2Ccs"],
        "candidateTiers":result["byUnassignedTariffCandidate"],
        "powerRows":result["byKindPower"],
        "contextFields":result["stationContextFieldsPresent"],
        "contextValues":result["stationContextValueCounts"],
        "sampleEvseSources":result["sampleEvseSources"][:4]
    },ensure_ascii=False))

if __name__=="__main__": main()
