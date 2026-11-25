#!/usr/bin/env python3
"""G6 FR Electroverse, phase 1: exhaustive raw tariff audit; no serving or identity changes."""
import collections
import json
import os
import pathlib
import re
import sqlite3
import sys
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import cached_connectors
from scripts.audit_irve_g5_final_tariff import verified,sk
from scripts.audit_irve_g5_restriction_replay import classify,details
from scripts.audit_irve_g5_v6_simulation import RULE,VERSION

AUDIT="g6-fr-electroverse-2026-11-25-inventory-v1"
DIMENSIONS={
    "ConsumptionRate":("energy",r"Consumption rate: €([0-9]+(?:\.[0-9]+)?) kWh"),
    "TimeRate":("time",r"Time rate: €([0-9]+(?:\.[0-9]+)?)/min"),
    "ParkingTimeRate":("parking",r"Time rate: €([0-9]+(?:\.[0-9]+)?)/min"),
    "ConnectionFee":("flat",r"Connection fee: €([0-9]+(?:\.[0-9]+)?)"),
    "VAT":("vat",r"VAT rate: ([0-9]+(?:\.[0-9]+)?)%"),
}
FIELDS={"dateRestrictions","timeRestrictions","durationRestrictions","weekdayRestrictions"}
def j(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def parse_components(items,label):
    result={};issues=[]
    if not isinstance(items,list):return result,[label+":COMPONENT_LIST_MISSING_OR_INVALID"]
    for c in items:
        if not isinstance(c,dict):
            issues.append(label+":COMPONENT_INVALID");continue
        typ=c.get("__typename")
        if typ not in DIMENSIONS:
            issues.append(label+":UNKNOWN_COMPONENT:"+str(typ));continue
        dim,pattern=DIMENSIONS[typ]
        val=c.get("formattedValue")
        m=re.fullmatch(pattern,val) if isinstance(val,str) else None
        if not m:
            issues.append(label+":INVALID_RATE_OR_UNIT:"+dim);continue
        if dim in result:
            issues.append(label+":DUPLICATE_DIMENSION:"+dim);continue
        result[dim]=Decimal(m[1])
    return result,issues
def inspect_tariff(c):
    schema,si,dims,conditions,types=classify(c)
    blockers=set(si)
    cx=c.get("complexPricingDetail")
    if not isinstance(cx,dict):cx={};blockers.add("COMPLEX_PRICE_STRUCTURE_MISSING")
    if cx.get("currency")!="EUR":blockers.add("CURRENCY_NOT_PROVEN_EUR")
    base,err=parse_components(c.get("priceComponents"),"BASE");blockers.update(err)
    if set(base)!=set(x[0] for x in DIMENSIONS.values()):blockers.add("BASE_COMPONENTS_INCOMPLETE")
    if base.get("vat")!=0:blockers.add("VAT_TREATMENT_REVIEW")
    restrictions=cx.get("restrictions")
    if not isinstance(restrictions,list):restrictions=[];blockers.add("RESTRICTION_LIST_MISSING_OR_INVALID")
    normalized=[];tokens=set();fields=set()
    for idx,r in enumerate(restrictions):
        if not isinstance(r,dict):blockers.add("INVALID_RESTRICTION");continue
        kinds=r.get("restrictionTypes")
        if not isinstance(kinds,list):blockers.add("RESTRICTION_TYPES_INVALID");kinds=[]
        tokens.update(str(x) for x in kinds)
        present={k for k in FIELDS if r.get(k) is not None};fields.update(present)
        rates,errors=parse_components(r.get("priceComponents"),"RULE");blockers.update(errors)
        normalized.append({"index":idx,"types":kinds,"conditions":{k:r.get(k) for k in sorted(present)},
                           "rates":{k:str(v) for k,v in rates.items()}})
        if kinds or present:
            blockers.add("CONDITIONAL_RULE_ENGINE_AND_ORACLE_REQUIRED")
        elif any(base.get(k)!=v for k,v in rates.items()):
            blockers.add("BASE_UNRESTRICTED_RULE_DISAGREEMENT")
    if "dateRestrictions" in fields or "DATE_BASED" in tokens:blockers.add("DATE_APPLICABILITY_AND_BOUNDARY_REVIEW")
    if "timeRestrictions" in fields or "TIME_BASED" in tokens:blockers.add("TIMEZONE_WINDOW_AND_DST_REVIEW")
    if "durationRestrictions" in fields or "DURATION_BASED" in tokens:blockers.add("DURATION_BILLING_CLOCK_AND_BOUNDARY_REVIEW")
    if "weekdayRestrictions" in fields or "WEEKDAY_BASED" in tokens:blockers.add("WEEKDAY_APPLICABILITY_REVIEW")
    if c.get("isChargingFree") is True:
        blockers.add("FREE_FLAG_AND_COMPONENTS_REVIEW")
        if any(v>0 for k,v in base.items() if k!="vat") or any(Decimal(v)>0 for r in normalized for k,v in r["rates"].items() if k!="vat"):
            blockers.add("FREE_FLAG_POSITIVE_PRICE_CONTRADICTION")
    elif c.get("isChargingFree") is not False:blockers.add("FREE_FLAG_UNPROVEN")
    if base.get("time",0)>0 or base.get("parking",0)>0:
        blockers.add("CHARGING_PARKING_CLOCK_AND_ROUNDING_REVIEW")
    if base.get("energy",0)==0 and base.get("flat",0)==0 and not blockers:
        blockers.add("ZERO_PRICE_WITHOUT_FREE_FLAG")
    # This is an independent arithmetic fixture, not a bill or engine approval.
    status="REVIEW_REQUIRED" if blockers else "SIMPLE_ENERGY_FLAT_ORACLE_CANDIDATE"
    amount=str(base["energy"]*Decimal(10)+base["flat"]) if not blockers else ""
    return dict(schema=schema,schema_issues=si,dimensions=dims,conditions=conditions,restriction_types=sorted(tokens),
        condition_fields=sorted(fields),base_rates={k:str(v) for k,v in base.items()},normalized_rules=normalized,
        restriction_diagnostics=json.loads(details(c)["restriction_diagnostics"]),
        reasons=sorted(blockers),audit_status=status,fixture_10kwh_eur_unrounded=amount)

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_electroverse_inventory" or pin["auditVersion"]!=AUDIT or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False or pin["identityChanges"] is not False:raise ValueError("Scope")
    ledger=download(root/"v6",pin["ledger"],{"db.sqlite":("g5-matching-v6.sqlite",),"report.json":("v6-consolidation-report.json",)})
    verify(ledger["db.sqlite"],pin["sqliteSha256"])
    report=json.loads(ledger["report.json"].read_text())
    if report["codeSha"]!=pin["ledger"]["codeSha"] or report["sqliteSha256"]!=pin["sqliteSha256"] or report["ruleVersion"]!=VERSION or report["validatedIdentityPairs"]!=24115 or report["sourcePin"]["simulationSourcePin"]["tariff"]!=pin["tariff"] or report["pricesPromoted"]!=0:raise ValueError("Ledger lineage")
    db=sqlite3.connect(ledger["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["tariffManifestSha256"]!=pin["tariffManifestSha256"]:raise ValueError("Tariff manifest lineage")
    pairs=[dict(x) for x in db.execute("""SELECT m.national_id,m.source_id,m.identity_rule,m.tariff_state,
        n.station_id,n.evse_id,n.plug AS national_plug,n.kw AS national_kw,n.mode AS national_mode
        FROM v6_identity_matches m JOIN national_connector n ON n.id=m.national_id ORDER BY m.national_id""")]
    sources={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_connector")}
    if len(pairs)!=24115 or len({x["national_id"] for x in pairs})!=24115 or len({x["source_id"] for x in pairs})!=24115 or dict(collections.Counter(x["identity_rule"] for x in pairs))!={RULE:14968,VERSION:9147}:raise ValueError("Identity scope")
    wanted={sk(sources[x["source_id"]]) for x in pairs}
    if len(wanted)!=24115:raise ValueError("Raw connector key uniqueness")
    raw=cached_connectors(root/"tariff",pin["tariff"],pin["tariffManifestSha256"],wanted)
    out=[];stats=collections.Counter();reasons=collections.Counter();families=collections.Counter();byrule=collections.Counter();schema=collections.Counter();byfamily=collections.Counter();date_count=collections.Counter();sig=set()
    for x in pairs:
        s=sources[x["source_id"]];obs=raw.get(sk(s));ok=verified(s,obs)
        payload=None;d=dict(schema="RAW_CONNECTOR_NOT_VERIFIED",schema_issues=[],dimensions=[],conditions=[],restriction_types=[],condition_fields=[],base_rates={},normalized_rules=[],restriction_diagnostics=[],reasons=["RAW_CONNECTOR_NOT_VERIFIED"],audit_status="REVIEW_REQUIRED",fixture_10kwh_eur_unrounded="")
        if ok:
            c=obs[1];payload={k:c.get(k) for k in ("isChargingFree","priceComponents","complexPricingDetail")}
            d=inspect_tariff(c);sig.add(s["tariff_signature"])
        if not s["has_price"]:
            d["reasons"]=sorted(set(d["reasons"]+["SOURCE_PRICE_NOT_PRESENT"]))
            d["audit_status"]="REVIEW_REQUIRED";d["fixture_10kwh_eur_unrounded"]=""
        family="+".join(d["restriction_types"]) or "NO_DECLARED_RESTRICTIONS"
        stats[d["audit_status"]]+=1;reasons.update(d["reasons"]);families[family]+=1
        byrule[x["identity_rule"],d["audit_status"]]+=1;schema[d["schema"]]+=1;byfamily[family,d["audit_status"]]+=1
        if "DATE_BASED" in d["restriction_types"]:date_count[x["identity_rule"]]+=1
        out.append({**x,"location_pk":s["location_pk"],"source_evse_pk":s["evse_pk"],"source_connector_pk":s["connector_pk"],"source_plug":s["plug"],"source_kw":s["kw"],"tariff_signature":s["tariff_signature"],"raw_verified":ok,"raw_price_payload":j(payload),"family":family,
            **{k:j(v) if isinstance(v,(dict,list)) else v for k,v in d.items()},"g6_calculability":"NOT_YET_CERTIFIED"})
    db.close();verify(ledger["db.sqlite"],pin["sqliteSha256"])
    if len(out)!=24115 or sum(stats.values())!=24115 or sum(families.values())!=24115:raise ValueError("Output coverage")
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-tariff-audit.csv.gz",out,list(out[0]))
    def tally(c,keys):return [{**dict(zip(keys,k)),"count":v} for k,v in sorted(c.items())]
    result=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=AUDIT,sourcePin=pin,identityPairs=len(out),
        rawVerified=sum(x["raw_verified"] for x in out),uniqueRawSignatures=len(sig),auditStatuses=dict(stats),schema=dict(schema),
        families=dict(families),reasonsNonExclusive=dict(reasons),byIdentityRule=tally(byrule,["rule","status"]),
        byFamily=tally(byfamily,["family","status"]),dateBasedByRule=dict(date_count),
        identityChanges=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,certifiedCalculable=0,
        limitations=["Phase 1 exhaustive input audit; independent 10 kWh arithmetic fixtures only for strict simple candidates, not an engine result or billing validation",
            "Conditional tariffs kept intact; no assumption about date applicability, time-zone, phase clock, rounding, or additive restriction semantics",
            "Historical Production oracles pinned as references, not replayed by this run",
            "No modification of G5, supplier calls, Production or ranking"])
    result["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-tariff-audit-report.json").write_text(j(result))
    print("G6_FR_ELECTROVERSE_AUDIT "+j({k:v for k,v in result.items() if k!="sourcePin"}))
if __name__=="__main__":main()
