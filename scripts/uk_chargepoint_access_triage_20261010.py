#!/usr/bin/env python3
"""Evidence-preserving ChargePoint UK access triage for ALL PCPR locations.

No fabricated classification: public PCPR publication is a regulatory/source
claim, not proof of public physical entry, open barriers, or PAYG. Source
status does not promote V9 price offers.
"""
from __future__ import annotations
import csv
import gzip
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "uk"
SRC = ROOT / "data/national/uk_eco_movement_pcpr.json.gz"
EXT = OUT / "chargepoint-residual-classification-latest.json"
PRIOR = OUT / "chargepoint-public-access-evidence-2026-10-10.json"
WORDS = [
    ("business_or_office", r"\b(?:office|headquarters|hq|business\s+park|industrial\s+estate|warehouse|factory|depot|logistics|corporate|enterprise|science\s+park)\b"),
    ("hotel_or_hospitality", r"\b(?:hotel|inn|resort|lodge|grange|spa|pub|restaurant|holiday\s+inn|guest)\b"),
    ("education_or_campus", r"\b(?:university|school|college|campus|academy|education)\b"),
    ("controlled_parking", r"\b(?:private\s+car\s+park|permit\s+only|permit\s+holders|barrier|gated|gate\s+code|security\s+gate|restricted\s+access|members\s+only|staff\s+only|employees\s+only|residents\s+only|authorization\s+required|authorisation\s+required)\b"),
    ("special_venue", r"\b(?:hospital|airport|sports\s+club|golf\s+club|marina|military|airbase|barracks|government\s+building|business\s+centre)\b"),
]

def load_json(path):
    with (gzip.open(path,"rt",encoding="utf8") if path.suffix==".gz" else path.open("r",encoding="utf8")) as f:
        return json.load(f)

def flatten(val):
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple)):
        return " ".join(flatten(x) for x in val)
    if isinstance(val, dict):
        return " ".join(flatten(x) for x in val.values())
    return "" if val is None else str(val)

def main():
    src = load_json(SRC)
    locations = src.get("locations") or []
    other = load_json(EXT) if EXT.exists() else {}
    previous = load_json(PRIOR) if PRIOR.exists() else {}
    confirmed = {x["locationId"]: x for x in previous.get("verifiedLocations",[]) if x.get("promotePhysicalPublicAccess") is True}
    external = {}
    for item in other.get("rows") or []:
        inventory = item.get("inventory") or {}
        id_ = str(inventory.get("externalId") or "")
        if id_:
            external[id_] = {
                "status":str((inventory.get("accessibility") or {}).get("status") or ""),
                "lastUpdated":inventory.get("updated"),
                "source":"ChargePoint Shell inventory (historical cross-check)"
            }
    rows=[]
    counts=Counter()
    signals=Counter()
    connector_total=0
    for loc in locations:
        lid = str(loc.get("id") or "")
        evses = loc.get("evses") or []
        connectors = sum(len(e.get("connectors") or []) for e in evses)
        connector_total+=connectors
        name=str(loc.get("name") or "")
        public_flag=loc.get("publish") is True
        text = " ".join([name, flatten(loc.get("directions")), flatten(loc.get("address")), flatten(loc.get("opening_times"))])
        # EVSE parking restrictions can describe a charging bay, not entry.
        # Include for reviewer but never auto-exclude a station on this alone.
        parking=sorted(set(flatten(e.get("parking_restrictions")) for e in evses if e.get("parking_restrictions")))
        hints=sorted({label for label,rx in WORDS if re.search(rx,text,re.I)})
        for h in hints:
            signals[h]+=1
        ext=external.get(lid,{})
        ext_status=ext.get("status","")
        if not public_flag:
            category="operator_not_public"
            reason="PCPR publish flag is false; not eligible for public V9"
        elif re.search(r"\\b(?:residents\\s+only|employees\\s+only|staff\\s+only|members\\s+only)\\b",text,re.I):
            category="nonpublic_explicit_onsite_rules"
            reason="Source location directions explicitly restrict access to residents, employees, staff or members; exclude from general-public charging"
        elif lid in confirmed:
            category="visitor_public_verified"
            reason="Independently documented venue guest/visitor access"
        elif "controlled_parking" in hints:
            category="priority_review_restricted_access"
            reason="Explicit words indicating potentially restricted physical entry; not a confirmed exclusion"
        elif any(h in hints for h in ["business_or_office","education_or_campus","hotel_or_hospitality","special_venue"]):
            category="priority_review_site_conditions"
            reason="Operator declares public, but premises may have visitor or parking conditions"
        elif ext_status.lower() in ("freepublic","public"):
            category="public_multi_source_declared"
            reason="PCPR published + independently sourced public-access label; no onsite gate verification"
        else:
            category="public_pcpr_declared"
            reason="Public PCPR location; no explicit private-access evidence in available fields"
        counts[category]+=1
        rows.append({
            "locationId":lid,"stationName":name,"city":loc.get("city") or "",
            "postalCode":loc.get("postal_code") or "","connectors":connectors,"evses":len(evses),
            "publish":public_flag,"category":category,"accessReason":reason,
            "hints":";".join(hints),"externalAccessStatus":ext_status,"externalSourceUpdated":ext.get("lastUpdated") or "",
            "parkingRestrictions":";".join(parking),
            "directions":flatten(loc.get("directions"))[:300],
            "physicalVisitorEvidence":(confirmed.get(lid) or {}).get("officialHotelFaq") or "",
            "operatorDeclaresPublic":public_flag,
            "directPAYGVerified":False
        })
    assert len(locations)==323, "Unexpected ChargePoint UK location count: re-audit baseline before staging"
    assert connector_total==1142, "Unexpected ChargePoint UK connector total: re-audit baseline before staging"
    assert len(rows)==len({r["locationId"] for r in rows})
    review=[r for r in rows if r["category"].startswith("priority_review")]
    summary={
      "generatedAt":datetime.now(timezone.utc).isoformat(),
      "inputCollectedAt":src.get("retrievedAt"),
      "country":"GB","operator":"ChargePoint CMS / Eco-Movement PCPR",
      "scope":{"stationCount":len(rows),"connectorCount":connector_total},
      "methodology":"Station-by-station machine classification using published PCPR metadata, location names, directions and known independent visitor evidence. Cross-check historical Shell access signals. No live physical access or direct payment is invented.",
      "categories":dict(counts),
      "priorityReviewStationCount":len(review),
      "priorityReviewConnectorCount":sum(r["connectors"] for r in review),
      "crossSourceAccessStatuses":dict(Counter(r["externalAccessStatus"] or "not_present" for r in rows)),
      "nameAndDirectionsSignals":dict(signals),
      "declaredPublicCount":sum(r["publish"] for r in rows),
      "confirmedNonPublicCount":sum(r["category"] in ("operator_not_public","nonpublic_explicit_onsite_rules") for r in rows),
      "confirmedNonPublicConnectorCount":sum(r["connectors"] for r in rows if r["category"] in ("operator_not_public","nonpublic_explicit_onsite_rules")),
      "directPAYGPromoted":0,
      "manualReviewPolicy":"Review ONLY priority classes and exceptions; PCPR public declaration alone does not justify direct price ranking or universal 24/7 physical access.",
      "prioritySamples":review[:35],
      "csv":"reports/uk/chargepoint-public-access-triage-2026-10-10.csv"
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"chargepoint-public-access-triage-2026-10-10.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    with (OUT/"chargepoint-public-access-triage-2026-10-10.csv").open("w",encoding="utf8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(sorted(rows,key=lambda x:(0 if x["category"].startswith("priority_review_restricted") else 1 if x["category"].startswith("priority_review") else 2,x["city"],x["stationName"])))
    print(json.dumps({"stations":len(rows),"connectors":connector_total,"categories":dict(counts),
     "crossSourceAccessStatuses":summary["crossSourceAccessStatuses"],"priorityReviews":len(review),"prioritySamples":review[:6]},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
