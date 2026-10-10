#!/usr/bin/env python3
"""Evidence-first UK ChargePoint site-access resolution, entire 323-station PCPR scope.

Read-only for tariff V9 and source feed; creates exact site cross-check report
and one CSV row per station with exact connector counts.  Verified public
charging venues are distinguished from verified connector matching, guest
payment permission and operator attribution. No fees are copied into V9.
"""
from __future__ import annotations
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REP=ROOT/"reports/uk"
BASE=REP/"chargepoint-public-access-triage-2026-10-10.csv"
CROSS=REP/"chargepoint-external-access-crosscheck-2026-10-11.csv"
CURATED=REP/"chargepoint-curated-access-proofs-2026-10-11.json"
REPORT=REP/"chargepoint-site-access-resolution-latest.json"
CSV=REP/"chargepoint-site-access-resolution-latest.csv"

PUBLIC_STRONG={"public_venue_exact_chargepoint_evidence","public_venue_passersby_confirmed","public_venue_guest_evidence"}
PUBLIC_COND={"public_venue_booking_required"}
SOURCE_GAP={"public_venue_power_mismatch","public_venue_network_identity_conflict","venue_visitor_charging_evse_pending","operator_site_policy_conflict"}
NONPUBLIC_POLICY={"nonpublic_venue_policy"}
NONPUBLIC_RISK={"workplace_likely_nonpublic"}

def load_rows(path):
    with path.open("r",encoding="utf8",newline="") as f: return list(csv.DictReader(f))

def classify(row, doc, prior):
    if row["category"]=="nonpublic_explicit_onsite_rules":
        return "nonpublic_confirmed","Operator directions explicitly restrict charging to residents","PCPR site directions",[],"high"
    if prior and prior["accessDecision"]=="nonpublic_confirmed_exclude":
        return "nonpublic_confirmed",prior["officialVenueEvidence"],"prior audited venue and operator proof",prior["officialVenueEvidenceUrls"].split(";"),"high"
    if doc:
        label=doc["class"]
        if label in PUBLIC_STRONG:
            return "public_customer_access_documented",doc["scope"],doc["note"],doc["urls"],doc["confidence"]
        if label in PUBLIC_COND:
            return "public_customer_advance_booking_required",doc["scope"],doc["note"],doc["urls"],doc["confidence"]
        if label in NONPUBLIC_POLICY:
            return "nonpublic_venue_policy_applies_site",doc["scope"],doc["note"],doc["urls"],doc["confidence"]
        if label in NONPUBLIC_RISK:
            return "probable_restricted_workplace_evse_unverified",doc["scope"],doc["note"],doc["urls"],doc["confidence"]
        if label in SOURCE_GAP:
            return label,doc["scope"],doc["note"],doc["urls"],doc["confidence"]
        raise AssertionError(("unknown_class",label))
    if prior and prior["accessDecision"]=="physical_public_access_verified":
        return "public_customer_access_documented",prior["officialVenueEvidence"],"Operator first-party airport parking and EV use policy",prior["officialVenueEvidenceUrls"].split(";"),"high"
    if row["category"]=="visitor_public_verified":
        return "public_customer_access_documented","Operator hotel confirms charging for guests and visitors, first-party venue source",row["physicalVisitorEvidence"],[row["physicalVisitorEvidence"]],"high"
    if row["category"]=="priority_review_restricted_access":
        return "private_car_park_entry_unverified",row["directions"],"PCPR says private parking, no unconditional public access",[],"low"
    if row["category"]=="priority_review_site_conditions":
        return "site_access_conditions_unverified","Potential access restriction due to location type",row["hints"],[],"low"
    return "pcpr_operator_declared_public_only","No independent venue/physical evidence; not a confirmed tariff",row["category"],[],"low"

def main():
    source=list(load_rows(BASE))
    prior_rows={x["locationId"]:x for x in load_rows(CROSS)}
    defs=json.loads(CURATED.read_text(encoding="utf8"))
    ids={}
    for item in defs["groups"]:
        for lid in item["ids"]:
            if lid in ids: raise AssertionError(("duplicate curated location",lid))
            ids[lid]=item
    source_by_id={x["locationId"]:x for x in source}
    assert len(source)==len(source_by_id)==323
    assert sum(int(x["connectors"]) for x in source)==1142
    assert len(prior_rows)==100
    assert all(i in source_by_id for i in ids),(set(ids)-set(source_by_id))
    assert all(i in source_by_id for i in prior_rows)
    rows=[]
    c=Counter()
    for raw in source:
        lid=raw["locationId"]
        evse_n=int(raw["evses"])
        conn_n=int(raw["connectors"])
        group=ids.get(lid)
        decision,conditions,evidence,urls,confidence=classify(raw,group,prior_rows.get(lid))
        # Important: public access does not infer exact EVSE or first-party rate!
        direct_price_validated=False
        exact_scope=bool(group and group["class"]=="public_venue_exact_chargepoint_evidence")
        if decision=="public_customer_access_documented" and not exact_scope:
            exact_scope=False
        c[(decision,"stations")]+=1
        c[(decision,"connectors")]+=conn_n
        rows.append({
            "locationId":lid,"stationName":raw["stationName"],"city":raw["city"],
            "postalCode":raw["postalCode"],"evseCount":evse_n,"connectors":conn_n,
            "priorAccessClassification":raw["category"],"accessDecision":decision,
            "sourceGroup":group["group"] if group else "",
            "accessConditions":conditions,"evidenceConfidence":confidence,
            "chargerExactIdentitySupportedByIndependentVenue":exact_scope,
            "evidenceDetails":str(evidence)[:650],
            "venueEvidenceUrls":";".join(u for u in urls if u.startswith("https://")),
            "guestDirectPaygValidated":direct_price_validated,
            "promoteToV9Pricing":False,
            "sourceOperatorDeclaredPublic":raw["publish"]
        })
    assert sum(int(x["connectors"]) for x in rows)==1142
    assert all(not x["promoteToV9Pricing"] for x in rows)
    assert {x["locationId"] for x in rows}==set(source_by_id)
    assert any(x["sourceGroup"]=="evielife_powdermills" for x in rows)
    def bucket(k):
        if k in ("nonpublic_confirmed","nonpublic_venue_policy_applies_site"): return "nonpublic"
        if k in ("public_customer_access_documented","public_customer_advance_booking_required"): return "public_access_with_conditions"
        return "unresolved"
    top=Counter()
    for r in rows:
        top[(bucket(r["accessDecision"]),"stations")]+=1
        top[(bucket(r["accessDecision"]),"connectors")]+=r["connectors"]
    priority={x["locationId"] for x in source if x["category"].startswith("priority_review")}
    previous_unresolved={x["locationId"] for x in source if x["category"].startswith("priority_review")}
    new_resolved_prior=[r for r in rows if r["locationId"] in previous_unresolved and bucket(r["accessDecision"])!="unresolved"]
    bydecision={k:{"stations":c[(k,"stations")],"connectors":c[(k,"connectors")]} for k,typ in c if typ=="stations"}
    summary={
      "generatedAt":datetime.now(timezone.utc).isoformat(),
      "baselineCollectionAt":"2026-10-10T11:40:53.549601+00:00",
      "scope":{"stations":len(rows),"connectors":1142,
               "original100CaseReviewStations":len(priority)},
      "groupsWithNewEvidence":len(defs["groups"]),
      "curatedStationIds":len(ids),
      "bucketCounts":{k:{"stations":top[(k,"stations")],"connectors":top[(k,"connectors")]} for k in ("public_access_with_conditions","nonpublic","unresolved")},
      "byDecision":bydecision,
      "original100CasesNowResolved":len(new_resolved_prior),
      "original100CasesRemainUnresolved":len(priority)-len(new_resolved_prior),
      "original100CasesResolvedConnectors":sum(x["connectors"] for x in new_resolved_prior),
      "newlyResolvedSample":[{"id":x["locationId"],"name":x["stationName"],"decision":x["accessDecision"],"connectors":x["connectors"],"group":x["sourceGroup"]} for x in new_resolved_prior][:70],
      "onlyPcprPublishedNotConfirmed":bydecision.get("pcpr_operator_declared_public_only",{}),
      "criticalExceptions":[{"locationId":r["locationId"],"stationName":r["stationName"],"accessDecision":r["accessDecision"],"connectors":r["connectors"]} for r in rows if r["accessDecision"] in ("public_venue_power_mismatch","public_venue_network_identity_conflict","operator_site_policy_conflict","probable_restricted_workplace_evse_unverified")],
      "policy":"Physical/site visitor access is independent of exact EVSE identity, tariff type, VAT, payment authorization and eMSP overlays. No tariffs or source-inclusion flags changed.",
      "jurisdiction":"https://www.gov.uk/government/publications/the-public-charge-point-regulations-2023-guidance/public-charge-point-regulations-2023-guidance",
      "csv":"reports/uk/chargepoint-site-access-resolution-latest.csv"
    }
    with CSV.open("w",encoding="utf8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(sorted(rows,key=lambda x:(x["accessDecision"],x["city"],x["stationName"])))
    REPORT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"bucketCounts":summary["bucketCounts"],"original100CasesNowResolved":summary["original100CasesNowResolved"],"original100CasesRemainUnresolved":summary["original100CasesRemainUnresolved"],"groupsWithNewEvidence":len(defs["groups"]),"byDecision":bydecision},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
