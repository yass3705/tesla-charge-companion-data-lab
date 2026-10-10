#!/usr/bin/env python3
"""Evidence-first direct CPO ad-hoc payment verification for 25 ChargePoint UK guest-access locations.

Preserves one row per exact connector, no eMSP prices, no uniform VAT assumptions
and no promotion to V9 merely because physical access or contactless hardware is
confirmed. Crossmatches 10 Oct 2026 PCPR exact tariff_id and first-party venue
guest payment evidence, separate payment ability from current rate verification.
"""
from __future__ import annotations
import collections
import csv
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPS=ROOT/"reports/uk"
RAW=ROOT/"data/national/uk_eco_movement_pcpr.json.gz"
ACCESS=REPS/"chargepoint-site-access-resolution-latest.csv"
EVIDENCE=REPS/"chargepoint-direct-payg-evidence-2026-10-11.json"
OUTJ=REPS/"chargepoint-direct-payg-audit-2026-10-11.json"
OUTC=REPS/"chargepoint-direct-payg-exact-connectors-2026-10-11.csv"

def load(path):
    with (gzip.open(path,"rt",encoding="utf8") if path.suffix==".gz" else path.open("r",encoding="utf8")) as f:return json.load(f)

def seq(v):return v if isinstance(v,list) else []

def components(t):
    return [(str(p.get("type") or ""),p.get("price"),p.get("step_size"),p.get("vat"),e.get("restrictions") or {})
            for e in seq(t.get("elements")) for p in seq(e.get("price_components"))]

def main():
    with ACCESS.open("r",encoding="utf8",newline="") as f:
        all_sites=list(csv.DictReader(f))
    eligible=[r for r in all_sites if r["accessDecision"] in
              ("public_customer_access_documented","public_customer_advance_booking_required")]
    assert len(all_sites)==323 and len(eligible)==25,("scope changed",len(eligible))
    expected=sum(int(x["connectors"]) for x in eligible)
    assert expected==84,(expected,"source connector scope changed")
    raw=load(RAW)
    evidence=load(EVIDENCE)
    loc={str(l.get("id") or ""):l for l in seq(raw.get("locations"))}
    tariffs=collections.defaultdict(list)
    for t in seq(raw.get("tariffs")):
        tariffs[(str(t.get("country_code") or ""),str(t.get("party_id") or ""),str(t.get("id") or ""))].append(t)
    group={}
    for g in evidence["groups"]:
        for site in g["locationIds"]:
            assert site not in group,("duplicate proof",site)
            group[site]=g
    assert set(group)<=set(x["locationId"] for x in eligible),"Evidence must match one of the 25 exact public site IDs."
    rows=[]
    status=collections.Counter()
    sourceIssues=collections.Counter()
    for site in eligible:
        lid=site["locationId"]
        station=loc[lid]
        g=group.get(lid)
        category=(g or {}).get("paymentClassification","no_independent_payment_channel_evidence")
        if g and category=="operator_direct_contactless_hardware_verified_exact_guest_checkout_amount_missing":
            channel="contactless_confirmed"
        elif g and category in ("official_payg_rate_but_app_only_channel_conflict","hotel_exact_rate_and_cap_but_app_only_channel_conflict"):
            channel="operator_rate_claim_app_only_conflict"
        elif g and category=="portal_guest_tariff_visible_no_verified_payment_authorization":
            channel="portal_price_visible_checkout_unverified"
        else:
            channel="payment_channel_unverified"
        # Distinguish first-party public rate from verified working ad-hoc payment checkout.
        eligible_evses=seq(station.get("evses"))
        n_here=0
        for e in eligible_evses:
            evseid=str(e.get("evse_id") or e.get("uid") or "")
            for c in seq(e.get("connectors")):
                cid=str(c.get("id") or "")
                src=seq(c.get("tariff_ids"))
                refs=sorted(set(str(x) for x in src if x is not None))
                match={}
                if len(refs)!=1:
                    sourceIssues["missing_or_multiple_tariff_ids"]+=1
                else:
                    matches=tariffs.get((str(station.get("country_code") or ""),
                                         str(station.get("party_id") or ""),refs[0]),[])
                    if len(matches)==1:
                        match=matches[0]
                    else:
                        sourceIssues["tariff_id_unresolved"]+=1
                currency=str(match.get("currency") or "no_tariff")
                cs=components(match)
                kinds=sorted(set(k for k,*_ in cs))
                price_steps=[{"type":k,"sourcePrice":p,"step":st,"sourceVat":vat,"restrictions":restr} for k,p,st,vat,restr in cs]
                no_vat=bool(cs) and all(vat is None for _,_,_,vat,_ in cs)
                if no_vat:sourceIssues["pcpr_vat_unspecified_connector"]+=1
                if currency!="GBP":sourceIssues["non_gbp_connector"]+=1
                if any(k in ("TIME","PARKING_TIME") for k in kinds):sourceIssues["tariff_has_time_or_parking"]+=1
                if len(seq(match.get("elements")))>1:sourceIssues["multi_element_tariff"]+=1
                if not match.get("type"):sourceIssues["tariff_type_unspecified"]+=1
                n_here+=1
                # Nothing can enter direct CPO ranking until exact guest payment, inclusive VAT,
                # caps, station time rules, and connector identity are fully authenticated.
                rows.append({
                   "locationId":lid,"stationName":site["stationName"],
                   "city":site["city"],"evseId":evseid,"connectorId":cid,
                   "maxPowerKw":(float(c.get("max_electric_power") or 0)/1000),
                   "sourceTariffIds":";".join(refs),
                   "sourceTariffCurrency":currency,
                   "sourceTariffType":str(match.get("type") or ""),
                   "sourceComponentTypes":";".join(kinds),
                   "sourcePriceComponentsAndRestrictions":json.dumps(price_steps,ensure_ascii=False,separators=(",",":")),
                   "sourceAllComponentVatMissing":no_vat,
                   "paymentClassification":category,
                   "guestChannel":channel,
                   "venueOfficialGrossRateGbpPerKwh":g.get("officialGrossRateGbpPerKwh",g.get("officialGrossAmountPerKwhUnverifiedVat","")) if g else "",
                   "venueOfficialSessionCapGbp":g.get("officialSessionCapGbp","") if g else "",
                   "evidenceUrl":";".join(g.get("firstPartySources",[])) if g else "",
                   "pricingStatus":"direct_cpo_guest_price_unverified",
                   "rankableDirectOffer":False,
                   "notes":"Evidence of visitable premises, contactless hardware or a source tariff is not independent verification of exact payable gross guest price."
                })
        assert n_here==int(site["connectors"]),(lid,n_here,site["connectors"])
        status[(category,"stations")]+=1
        status[(category,"connectors")]+=n_here
    assert len(rows)==84
    assert all(r["rankableDirectOffer"] is False for r in rows)
    with OUTC.open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(sorted(rows,key=lambda r:(r["locationId"],r["evseId"],r["connectorId"])))
    summary={
      "generatedAt":datetime.now(timezone.utc).isoformat(),
      "collectedAt":raw.get("retrievedAt"),
      "country":"GB","source":"Eco-Movement PCPR (ChargePoint CPO physical public access subset)",
      "scope":{"stations":25,"connectors":84},
      "paymentEvidenceByType":{
        k:{"stations":status[(k,"stations")],"connectors":status[(k,"connectors")]}
        for k,typ in status if typ=="stations"
      },
      "sourceTariffIssueConnectorCounts":dict(sourceIssues),
      "exactConnectorPricePromoted":0,
      "sourceTariffGrossVATVerified":False,
      "operatorProof":"reports/uk/chargepoint-direct-payg-evidence-2026-10-11.json",
      "fullConnectorAudit":"reports/uk/chargepoint-direct-payg-exact-connectors-2026-10-11.csv",
      "decisionRules":{
        "contactless_hardware":"first-party statement confirms method at installation but tariff and checkout need validation; do not activate",
        "operator_rate_app_only_conflict":"retail PAYG price known, but ChargePoint passenger app limited to connected business/leasing program after 30 Jun 2026; confirm working card/QR method",
        "pcpr_vat":"Do not automatically mark all source VAT absent as exact gross guest fare; reconcile against actual operator quote",
        "operator_caps_minimum_time":"Time, caps, parking, minimum session fees and schedule require explicit tariff model; do not omit or double bill.",
        "direct_tariff":"No promotion to V9 until exact connector price including taxes AND independent accessible guest payment path are verified."
      },
      "policy":"No source tariff default, no invented prices, no changes to production V9; source inventory remains available in quarantine."
    }
    OUTJ.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
