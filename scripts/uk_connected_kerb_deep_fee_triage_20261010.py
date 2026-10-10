#!/usr/bin/env python3
"""Read-only detailed app evidence review for UK Connected Kerb 56 P1 connectors.

Inspect guest socket's full tariff slices, match by exact QR+operator location
and never conflate source socket, tariff option, or non-energy fee dimension.
No network fetch and no V9 tariff write.
"""
import collections,csv,gzip,json
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
def read(name):
    path=ROOT/name
    with (gzip.open(path,"rt",encoding="utf-8") if name.endswith(".gz") else open(path,encoding="utf-8")) as f:return json.load(f)
def key(s):return str(s or "").strip().upper()
def shape(row):
    return {k:v for k,v in row.items() if k not in ("lastUpdated","internalToken","customerId")}

def main():
    current=read("reports/uk/connected-kerb-app-collection-latest.json")
    raw=read("data/national/uk_connected_kerb_app_details.json.gz")
    baseline=read("data/national/uk_connected_kerb_locations.json.gz")
    raw_tariffs=read("data/national/uk_connected_kerb_tariffs.json.gz")
    assert current["collectedAt"]==raw["collectedAt"],"stale guest details"
    assert current["operatorBaselineCollectedAt"]==baseline["collectedAt"],"stale operator inventory"
    tar={str(x["id"]):x for x in raw_tariffs["tariffs"]}
    details={x["operatorLocationId"]:x for x in raw["records"]}
    locations={x["id"]:x for x in baseline["locations"] if x.get("publish")}
    scope=set()
    target=[]
    for issue in current["unresolved"]:
        if issue["reason"] not in {"multiple_energy_prices_without_windows","fee_unit_verification_pending"}:continue
        k=(issue["locationId"],issue["evseUid"],issue["connectorId"])
        assert k not in scope,"duplicate P1 identity"
        scope.add(k)
        target.append(issue)
    result=[]
    classifications=collections.Counter()
    tariff_ids=set()
    fees=collections.Counter()
    source_comparison=collections.Counter()
    for issue in target:
        loc=locations[issue["locationId"]]
        rec=details.get(issue["locationId"],{})
        app=rec.get("location") or {}
        matches=[s for s in app.get("sockets",[]) if key(s.get("qrCode"))==key(issue.get("physicalReference"))]
        evse=next(e for e in loc["evses"] if e["uid"]==issue["evseUid"])
        conn=next(c for c in evse["connectors"] if c["id"]==issue["connectorId"])
        ids=conn.get("tariff_ids") or []
        source=[]
        for tid in ids:
            for e in tar.get(tid,{}).get("elements",[]):
                source.append({"tariffId":tid,"restrictions":e.get("restrictions"),
                               "components":[{"type":p.get("type"),"price":p.get("price"),"step":p.get("step_size"),"vat":p.get("vat")} for p in e.get("price_components",[])]})
        app_sockets=[]
        for socket in matches:
            specs=socket.get("fullTariffSpecification") or []
            regular=[x for x in specs if x.get("tariffOption")=="REGULAR"]
            if len(regular)==1: selected=regular[0]
            elif len(specs)==1 and specs[0].get("tariffOption") in (None,"REGULAR"):selected=specs[0]
            else:selected=None
            unified=[x for x in socket.get("unifiedTariffs",[]) if selected and x.get("id")==selected.get("id")]
            for x in unified:tariff_ids.add(str(x.get("id")))
            app_sockets.append({"socketId":socket.get("id"),"qrCode":socket.get("qrCode"),
                "fullTariffSpecification":specs,"selectedSpecification":selected,
                "unifiedMatchingTariffs":unified,"unifiedAllSummary":[
                {"id":t.get("id"),"tariffOption":t.get("tariffOption"),"slices":t.get("slices")}
                for t in socket.get("unifiedTariffs",[])]})
        selected_unified=[x for socket in app_sockets for x in socket["unifiedMatchingTariffs"]]
        if len(matches)!=1 or len(selected_unified)!=1:
            category="requires_unique_guest_socket_or_tariff"
        else:
            slices=selected_unified[0].get("slices") or {}
            for kind,entries in slices.items():
                if kind!="ENERGY" and entries:fees[kind]+=len(entries)
            energy=slices.get("ENERGY") or []
            # Similar prices can be unified ONLY when all fields affecting charging
            # are identical except for source-internal IDs or presentation labels.
            comparable=[{k:v for k,v in e.items() if k not in ("id","title","name","description")} for e in energy]
            unique={json.dumps(x,sort_keys=True,default=str) for x in comparable}
            fees_present=any(kind!="ENERGY" and entries for kind,entries in slices.items())
            if issue["reason"]=="multiple_energy_prices_without_windows":
                if len(unique)==1 and not fees_present:
                    category="equivalent_energy_slices_candidate_for_exact_dedupe"
                elif len({(x.get("price"),x.get("stepSize"),json.dumps(x.get("dayOfWeek",[]),sort_keys=True)) for x in energy})==1 and not fees_present:
                    category="same_rate_different_fields_require_review"
                else:category="different_energy_rates_or_conditions_ambiguous"
            elif fees_present:
                category="additional_fee_unit_and_trigger_require_official_semantics"
            else:category="unexpected_missing_fee_evidence"
            gross=[]
            for component in source:
                for c in component["components"]:
                    if c["type"]=="ENERGY" and isinstance(c.get("price"),(int,float)):
                        gross.append(round(c["price"]*(1+(c.get("vat") or 0)/100),6))
            if gross and energy:
                valid=all(any(abs(float(x["price"])-g)<=.0002 for g in gross) for x in energy if isinstance(x.get("price"),(int,float)))
                source_comparison["all_guest_energy_prices_match_operator_source" if valid else "guest_energy_operator_source_disagreement"]+=1
            else:source_comparison["insufficient_source_energy_evidence"]+=1
        classifications[category]+=1
        result.append({"locationId":issue["locationId"],"stationName":loc.get("name"),
            "evseId":issue["evseId"],"connectorId":issue["connectorId"],
            "physicalReference":issue.get("physicalReference"),
            "reason":issue["reason"],"classification":category,
            "appLocationId":app.get("id"),"matchedSockets":len(matches),
            "socketEvidence":app_sockets,"operatorOcpiTariffElements":source})
    assert len(result)==56, f"P1 cohort changed {len(result)}"
    out={"schemaVersion":1,"generatedAt":datetime.now(timezone.utc).isoformat(),
      "baselineCollectedAt":baseline["collectedAt"],"appCollectedAt":current["collectedAt"],
      "source":"Connected Kerb guest app detailed location payload; exact physical QR evidence",
      "scope":"read-only evidence, no publishable tariff changes",
      "count":len(result),"classifications":dict(classifications),
      "feeKinds":dict(fees),"sourceCrosscheck":dict(source_comparison),
      "distinctTariffIds":len(tariff_ids),
      "records":result}
    folder=ROOT/"reports/uk"
    p=folder/"connected-kerb-deep-fee-evidence-2026-10-10.json"
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    csvp=folder/"connected-kerb-deep-fee-summary-2026-10-10.csv"
    with csvp.open("w",newline="",encoding="utf-8") as f:
        cols=["locationId","stationName","evseId","connectorId","physicalReference","reason","classification","appLocationId","matchedSockets"]
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
        writer.writerows({k:r.get(k) for k in cols} for r in result)
    print("CONNECTED_KERB_DEEP_FEE_TRIAGE="+json.dumps({k:v for k,v in out.items() if k!="records"},ensure_ascii=False))
if __name__=="__main__":main()
