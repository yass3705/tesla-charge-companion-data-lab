#!/usr/bin/env python3
"""Exact-ID batch cross-check of UK ChargePoint physical accessibility.

Reviews all 100 flagged sites from the prior 323-station public-access triage.
Strict source provenance: public PCPR flag, independent first-party venue
evidence, physical parking restrictions and optional Shell cross-check remain
distinct, never conflated with a verified ad-hoc tariff or payment method.
"""
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports/uk"
PREFIX="chargepoint-external-access-crosscheck-2026-10-11"

def load(p):
    path=ROOT/p
    with (gzip.open(path,"rt",encoding="utf8") if path.suffix==".gz" else path.open("r",encoding="utf8")) as f:
        return json.load(f)

def normalize(s):
    return re.sub(r"\s+"," ",str(s or "")).strip()

def main():
    prior=list(csv.DictReader((REPORTS/"chargepoint-public-access-triage-2026-10-10.csv").open(encoding="utf8",newline="")))
    flagged=[x for x in prior if x["category"].startswith("priority_review")]
    all_sites=load("data/national/uk_eco_movement_pcpr.json.gz")["locations"]
    raw={str(s["id"]):s for s in all_sites}
    source=load("reports/uk/chargepoint-official-site-access-evidence-2026-10-11.json")
    groups={sid:g for g in source["groups"] for sid in g["stationIds"]}
    assert len(groups)==len(set(sid for g in source["groups"] for sid in g["stationIds"]))
    assert len(prior)==len(all_sites)==323
    assert len(flagged)==100,"Upstream review list changed; reconcile rather than guessing"
    historic=load("reports/uk/chargepoint-residual-classification-latest.json")
    shell={}
    for x in historic.get("rows",[]):
        loc=x.get("inventory") or {}
        lid=str(loc.get("externalId") or "")
        if lid:
            shell[lid]={
                "status":(loc.get("accessibility") or {}).get("status"),
                "authorizationMethods":sorted({str(m) for e in loc.get("evses") or [] for m in e.get("authorizationMethods") or []}),
                "updated":loc.get("updated")
            }
    results=[]
    totals=Counter()
    signals=Counter()
    unaccounted=[]
    for p in flagged:
        lid=p["locationId"]
        row=raw.get(lid)
        assert row is not None,lid
        n_conn=sum(len(e.get("connectors") or []) for e in row.get("evses") or [])
        assert n_conn==int(p["connectors"]),(lid,n_conn,p["connectors"])
        doc=groups.get(lid)
        description=" ".join([normalize(row.get("name")), normalize(row.get("city")), 
          " ".join(normalize(v) for v in (row.get("directions") or {}).values()) if isinstance(row.get("directions"),dict) else normalize(row.get("directions"))])
        text=description.lower()
        exact_staff_fleet=bool(re.search(
          r"\b(?:fleet\s*,?\s*staff\s+and\s+contractors\s+only|fleet\s+and\s+brs\s+staff\s+use\s+only|staff\s+only|employees\s+only|residents\s+only)\b",text))
        only_visitor_authorized=bool(re.search(r"\b(?:staff\s+and\s+visitors\s+only|fleet\s*,?\s*staff\s+and\s+visitors\s+only)\b",text))
        private_car_park=bool(re.search(r"\bprivate\s+car\s+park\b",text))
        if doc is not None:
            flag=doc["classification"]
            if flag=="public_physical_access_confirmed_with_parking_conditions":
                decision="physical_public_access_verified"
                priority="resolved"
            elif flag in ("nonpublic_staff_only","nonpublic_explicit_operator_site_directions"):
                decision="nonpublic_confirmed_exclude"
                priority="resolved"
            elif flag=="nonpublic_university_chargepoint_site":
                decision="nonpublic_venue_chargers_match_pending"
                priority="P1"
            elif flag=="campus_visitors_charging_exists_exact_evse_not_confirmed":
                decision="visitor_site_available_exact_EVSE_pending"
                priority="P2"
            else:
                raise ValueError(flag)
            refs=doc["source"]
            source_evidence=doc["evidence"]
            confidence=doc["confidence"]
        elif exact_staff_fleet:
            decision="nonpublic_confirmed_exclude"
            priority="resolved"
            refs=["data/national/uk_eco_movement_pcpr.json.gz"]
            source_evidence="Exact operator site directions explicitly restrict charging to a nonpublic fleet, staff, or resident group"
            confidence="high"
        elif only_visitor_authorized:
            decision="site_visitor_authorization_required"
            priority="P1"
            refs=["data/national/uk_eco_movement_pcpr.json.gz"]
            source_evidence="Operator directions authorize only staff/fleet and visitors; public walk-in charging not established"
            confidence="high"
        elif private_car_park:
            decision="private_car_park_access_unverified"
            priority="P1"
            refs=["data/national/uk_eco_movement_pcpr.json.gz"]
            source_evidence="Private Car Park in source directions; entrance restrictions unspecified"
            confidence="high"
        else:
            decision="public_pcpr_no_independent_site_confirmation"
            priority="P3"
            refs=["data/national/uk_eco_movement_pcpr.json.gz"]
            source_evidence="PCPR publish:true only; site/name heuristic alone cannot prove public EVSE access"
            confidence="low"
        if exact_staff_fleet:
            signals["exact_staff_fleet_restriction"]+=1
        if only_visitor_authorized:
            signals["visitors_only_with_staff_or_fleet"]+=1
        if private_car_park:
            signals["private_car_park"]+=1
        ext=shell.get(lid) or {}
        if ext.get("status") and decision=="public_pcpr_no_independent_site_confirmation":
            decision="pcpr_plus_shell_declared_public_no_physical_proof"
            priority="P3"
        totals[(decision,"locations")]+=1
        totals[(decision,"connectors")]+=n_conn
        results.append({
            "locationId":lid,
            "stationName":p["stationName"],
            "city":p["city"],
            "postalCode":p["postalCode"],
            "evseIds":";".join(sorted({str(e.get("evse_id") or "") for e in row.get("evses") or []})),
            "connectorCount":n_conn,
            "operatorPublishPublic":bool(row.get("publish")),
            "accessDecision":decision,
            "reviewPriority":priority,
            "evidenceConfidence":confidence,
            "sourceDirections":description[:380],
            "crossSourceShellAccessibility":str(ext.get("status") or ""),
            "crossSourceShellAuthMethods":";".join(ext.get("authorizationMethods") or []),
            "officialVenueEvidence":source_evidence,
            "officialVenueEvidenceUrls":";".join(x for x in refs if x.startswith("https://")),
            "requiresExactEVSEAccessProof":priority!="resolved",
            "publicPriceReadyForV9":False
        })
    covered=set(groups)
    asserted={r["locationId"] for r in results}
    assert covered <= asserted,(covered-asserted)
    airport_public=[r for r in results if r["accessDecision"]=="physical_public_access_verified" and r["stationName"].startswith("BRISTOL AIRPORT MSCP")]
    assert len(airport_public)==3 and sum(r["connectorCount"] for r in airport_public)==20, "The 20 exact airport connectors must agree with official operator site and Zapmap"
    assert all(r["publicPriceReadyForV9"] is False for r in results)
    csv_path=REPORTS/(PREFIX+".csv")
    with csv_path.open("w",encoding="utf8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(sorted(results,key=lambda x:({"resolved":0,"P1":1,"P2":2,"P3":3}.get(x["reviewPriority"],9),x["city"],x["stationName"])))
    categories={key.replace("locations","stations"):val for (key,kind),val in totals.items() if kind=="locations"}
    # Build compact breakdown without losing native exact-source decision labels.
    by_decision={k:{"stations":totals[(k,"locations")],"connectors":totals[(k,"connectors")]} for k,kind in totals if kind=="locations"}
    summary={
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "dataCollectedAt":load("reports/uk/eco-movement-pcpr-latest.json").get("retrievedAt"),
        "scope":{"allPcprStations":323,"allPcprConnectors":1142,"flaggedStations":len(results),
                 "flaggedConnectors":sum(r["connectorCount"] for r in results)},
        "priorOperatorPublicEvidence":"Every source location publishes true but this does not prove unrestricted physical access or tariff PAYG.",
        "method":"Join 100 flagged exact ChargePoint PCPR station IDs with independent official venue pages, direct on-site operator restrictions and historical Shell accessibility tags; never infer exact charger access from a venue-wide parking policy.",
        "byDecision":by_decision,
        "validatedPublicAccessExactStations":sum(x["accessDecision"]=="physical_public_access_verified" for x in results),
        "confirmedNonpublicExactStations":sum(x["accessDecision"]=="nonpublic_confirmed_exclude" for x in results),
        "remainingReviewStations":sum(x["reviewPriority"]!="resolved" for x in results),
        "remainingReviewConnectors":sum(x["connectorCount"] for x in results if x["reviewPriority"]!="resolved"),
        "manualP1Stations":[{"locationId":r["locationId"],"stationName":r["stationName"],"reason":r["accessDecision"],"connectors":r["connectorCount"]} for r in results if r["reviewPriority"]=="P1"],
        "sourceAccessFlags":dict(signals),
        "officialSourceRegister":"reports/uk/chargepoint-official-site-access-evidence-2026-10-11.json",
        "fullMatrixCsv":str(csv_path.relative_to(ROOT)),
        "pricingImpact":"No unverified ChargePoint direct tariff promoted; access classification alone does not verify ad-hoc guest checkout/VAT.",
        "nonpublicFilterPolicy":"Exclude confirmed staff-only/fleet-only public access. Site-level university association requires exact EVSE/venue membership verification before permanent removal.",
        "releaseStatus":"access_triage_only_not_live_tariff"
    }
    (REPORTS/(PREFIX+".json")).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"scope":summary["scope"],"byDecision":summary["byDecision"],"remainingReviewStations":summary["remainingReviewStations"],"remainingReviewConnectors":summary["remainingReviewConnectors"],"manualP1Stations":summary["manualP1Stations"]},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
