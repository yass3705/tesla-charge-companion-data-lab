#!/usr/bin/env python3
"""Audit UK Eco-Movement PCPR OCPI data before V9 exposure; never infer tariffs."""
import collections
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/national/uk_eco_movement_pcpr.json.gz"
OUT = ROOT / "reports/uk/eco-movement-pcpr-connector-audit.json"
def text(v):
    return str(v).strip() if v is not None else ""
def rows(v):
    return v if isinstance(v, list) else []
def label(v):
    return text(v.get("name")) if isinstance(v, dict) else text(v)
def top(c, n=30):
    return dict(c.most_common(n))
def keyset(v):
    return sorted(v) if isinstance(v, dict) else []
def uniq_ids(value):
    if isinstance(value, list):
        return sorted(set(text(x) for x in value if text(x)))
    if value is None:
        return []
    return [text(value)]
def sample(v, n=6):
    return v[:n]
with gzip.open(SOURCE, "rt", encoding="utf-8") as handle:
    data = json.load(handle)
locations = rows(data.get("locations"))
tariffs = rows(data.get("tariffs"))
statuses = rows(data.get("statuses"))
tid_map = collections.defaultdict(list)
for t in tariffs:
    tid_map[text(t.get("id"))].append(t)
ref_types = collections.Counter()
refs = collections.Counter()
missing_refs = collections.Counter()
ambiguous_refs = collections.Counter()
loc_countries = collections.Counter()
operator_names = collections.Counter()
owner_names = collections.Counter()
suboperator_names = collections.Counter()
parking_types = collections.Counter()
auth_types = collections.Counter()
country_code_types = collections.Counter()
access_fields = collections.Counter()
tariff_types = collections.Counter()
currency_types = collections.Counter()
component_types = collections.Counter()
restriction_fields = collections.Counter()
location_keys = collections.Counter()
evse_keys = collections.Counter()
connector_keys = collections.Counter()
duplicate_loc = collections.Counter()
duplicate_evse = collections.Counter()
duplicate_connector = collections.Counter()
nonpublic_reasons = collections.Counter()
no_tariff_connector_samples = []
multiple_tariff_connector_samples = []
referenced_sample = []
locations_sample = []
unpriced = 0
priced_ref = 0
connectors = 0
evses = 0
loc_seen = set()
evse_seen = set()
connector_seen = set()
station_any_ref = set()
tariff_element_count = collections.Counter()
for t in tariffs:
    tariff_types[text(t.get("type") or "unspecified")] += 1
    currency_types[text(t.get("currency") or "unspecified")] += 1
    tariff_element_count[len(rows(t.get("elements")))] += 1
    for el in rows(t.get("elements")):
        for p in rows(el.get("price_components")):
            component_types[text(p.get("type") or "unspecified")] += 1
        for k in (el.get("restrictions") or {}):
            restriction_fields[k] += 1
for loc in locations:
    lid = text(loc.get("id"))
    location_keys.update(keyset(loc))
    loc_countries[text(loc.get("country") or loc.get("country_code") or "missing")] += 1
    country_code_types[text(loc.get("party_id") or "missing")] += 1
    operator_names[label(loc.get("operator")) or "missing"] += 1
    owner_names[label(loc.get("owner")) or "missing"] += 1
    suboperator_names[label(loc.get("suboperator")) or "missing"] += 1
    parking_types[text(loc.get("parking_type") or "missing")] += 1
    for k in ("publish", "charging_when_closed", "parking_type", "opening_times", "access_type", "access", "facilities"):
        if k in loc:
            access_fields[k] += 1
    for k in ("publish", "parking_type", "access_type", "access"):
        val = loc.get(k)
        if k == "publish" and val is False:
            nonpublic_reasons["publish_false"] += 1
        if k in ("parking_type", "access_type", "access") and ("PRIVATE" in text(val).upper() or "RESTRICT" in text(val).upper() or "RESERVED" in text(val).upper()):
            nonpublic_reasons[k + ":" + text(val)] += 1
    if lid in loc_seen:
        duplicate_loc[lid] += 1
    loc_seen.add(lid)
    if len(locations_sample) < 5:
        locations_sample.append({"id":lid,"name":loc.get("name"),"country":loc.get("country"),"party_id":loc.get("party_id"),"operator":loc.get("operator"),"owner":loc.get("owner"),"suboperator":loc.get("suboperator"),"parking_type":loc.get("parking_type"),"publish":loc.get("publish"),"opening_times":loc.get("opening_times"),"coordinates":loc.get("coordinates")})
    for e in rows(loc.get("evses")):
        evses += 1
        evse_keys.update(keyset(e))
        eid = text(e.get("evse_id") or e.get("uid") or e.get("id"))
        eid_key = lid + "|" + eid
        if eid_key in evse_seen:
            duplicate_evse[eid_key] += 1
        evse_seen.add(eid_key)
        for c in rows(e.get("connectors")):
            connectors += 1
            connector_keys.update(keyset(c))
            cid = text(c.get("id"))
            key = lid + "|" + eid + "|" + cid
            if key in connector_seen:
                duplicate_connector[key] += 1
            connector_seen.add(key)
            ts = uniq_ids(c.get("tariff_ids"))
            if not ts:
                ts = uniq_ids(c.get("tariff_id"))
            ref_types[len(ts)] += 1
            if ts:
                station_any_ref.add(lid)
                priced_ref += 1
                if len(referenced_sample) < 6:
                    referenced_sample.append({"locationId":lid,"evseId":eid,"connectorId":cid,"tariffIds":ts,"powerW":c.get("max_electric_power"),"status":e.get("status")})
            else:
                unpriced += 1
                if len(no_tariff_connector_samples) < 10:
                    no_tariff_connector_samples.append({"locationId":lid,"evseId":eid,"connectorId":cid,"powerW":c.get("max_electric_power")})
            if len(ts) > 1 and len(multiple_tariff_connector_samples) < 10:
                multiple_tariff_connector_samples.append({"locationId":lid,"evseId":eid,"connectorId":cid,"tariffIds":ts})
            for tid in ts:
                refs[tid] += 1
                if tid not in tid_map:
                    missing_refs[tid] += 1
                elif len(tid_map[tid]) != 1:
                    ambiguous_refs[tid] += 1
duplicated_tariff_ids = {key:len(value) for key,value in tid_map.items() if len(value)>1}
all_prices_supported = not any(x not in {"ENERGY","TIME","PARKING_TIME","FLAT"} for x in component_types)
out = {
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "inputCollectedAt":data.get("retrievedAt"),
    "country":"GB",
    "rawCounts":{"locations":len(locations),"evses":evses,"connectors":connectors,"tariffs":len(tariffs),"statuses":len(statuses)},
    "identity":{"countryCounts":top(loc_countries),"partyIds":top(country_code_types),"operatorNames":top(operator_names),"ownerNames":top(owner_names),"suboperatorNames":top(suboperator_names),"duplicateLocationIds":top(duplicate_loc),"duplicateEvseKeys":top(duplicate_evse),"duplicateConnectorKeys":top(duplicate_connector)},
    "publicAccess":{"parkingTypes":top(parking_types),"accessFieldsPresent":dict(access_fields),"exclusionCandidates":top(nonpublic_reasons)},
    "pricing":{"connectorRefCountHistogram":top(ref_types),"connectorsWithTariffRefs":priced_ref,"connectorsWithoutTariffRefs":unpriced,"locationsWithAnyTariffRef":len(station_any_ref),"distinctReferencedTariffIds":len(refs),"referencedTariffCount":sum(refs.values()),"missingTariffIdReferences":dict(missing_refs),"ambiguousTariffReferences":dict(ambiguous_refs),"duplicatedTariffIds":duplicated_tariff_ids,"tariffTypes":top(tariff_types),"currencies":top(currency_types),"components":top(component_types),"restrictions":top(restriction_fields),"elementsPerTariff":top(tariff_element_count),"supportedComponentTypes":all_prices_supported},
    "schema":{"locationKeys":top(location_keys,80),"evseKeys":top(evse_keys,80),"connectorKeys":top(connector_keys,80),"statusTopLevelKeys":keyset(statuses[0]) if statuses else [],"tariffTopLevelKeys":keyset(tariffs[0]) if tariffs else []},
    "samples":{"locations":locations_sample,"pricedConnectors":referenced_sample,"unpricedConnectors":no_tariff_connector_samples,"multiTariffConnectors":multiple_tariff_connector_samples,"tariffs":[{"id":t.get("id"),"type":t.get("type"),"currency":t.get("currency"),"elements":t.get("elements")} for t in sample(tariffs,4)]},
    "activationReadiness":{"allTariffReferencesResolve":not missing_refs and not ambiguous_refs,"noDuplicateIdentifiers":not duplicate_loc and not duplicate_evse and not duplicate_connector,"operatorAttributionRequiresReview":True,"directPaygScopeRequiresReview":True,"publicAccessRequiresReview":True,"status":"audit_only_not_yet_v9_active"}
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"counts":out["rawCounts"],"pricing":out["pricing"],"identity":out["identity"],"publicAccess":out["publicAccess"],"activationReadiness":out["activationReadiness"]},ensure_ascii=False,indent=2))

# V9 direct CPO PCPR conversion. Platform-scoped PCPR access returns an OCPI
# CPO feed, not a roaming/eMSP tariff catalogue. Keep declared CPO as ChargePoint.
# The public chargepoint VAT rate is 20% (UK HMRC, 2026); OCPI 2.2.1
# PriceComponent.price excludes VAT. Explicit VAT rates, when present, win.
# This is a V9-local derived dataset: component prices are stored INCLUSIVE of
# VAT, tagged accordingly to prevent re-applying VAT downstream.
import copy
from decimal import Decimal, InvalidOperation
from collections import Counter

source_tariffs={text(t.get("id")):t for t in tariffs}
included_tariffs={}
excluded_tariffs={}
included_connector_count=0
unpriced_connector_count=0
excluded_stations=Counter()
excluded_evses=Counter()
source_refs=Counter()
tax_defaults=Counter()
tax_explicit=Counter()
blocked_tariffs=Counter()
safe_locations=[]
SUPPORTED_RESTRICTIONS={"start_time","end_time","day_of_week","min_duration","max_duration",
                        "min_power","max_power","start_date","end_date"}
SUPPORTED_COMPONENTS={"ENERGY","TIME","PARKING_TIME","FLAT"}
def convert(t):
    if text(t.get("currency")).upper()!="GBP":
        return None,"non_GBP_currency"
    if not rows(t.get("elements")):
        return None,"missing_tariff_elements"
    transformed=copy.deepcopy(t)
    transformed["tccPriceBasis"]="GBP_including_public_UK_VAT"
    transformed["tccSourcePriceBasis"]="OCPI_2.2.1_excluding_VAT"
    for el in transformed["elements"]:
        restrictions=el.get("restrictions") or {}
        if not isinstance(restrictions,dict) or any(k not in SUPPORTED_RESTRICTIONS for k in restrictions):
            return None,"unsupported_restrictions"
        if not rows(el.get("price_components")):
            return None,"missing_components"
        for component in el["price_components"]:
            kind=text(component.get("type")).upper()
            if kind not in SUPPORTED_COMPONENTS:
                return None,"unsupported_component"
            try:
                original=Decimal(str(component["price"]))
                explicit=component.get("vat")
                pct=Decimal(str(explicit)) if explicit is not None else Decimal("20")
                step=Decimal(str(component.get("step_size",1)))
            except (KeyError,InvalidOperation,TypeError,ValueError):
                return None,"invalid_price_or_vat_or_step"
            if original<0 or pct<0 or pct>100 or (step<=0 and kind!='FLAT') or (step<0):
                return None,"invalid_component_value"
            component["sourcePriceExVat"]=float(original)
            component["tccVatRateAppliedPct"]=float(pct)
            component["tccVatOrigin"]="explicit_OCPI" if explicit is not None else "HMRC_UK_public_20_default"
            component["price"]=float((original*(Decimal("1")+pct/Decimal("100"))).quantize(Decimal("0.000001")))
            component["vat"]=None
            if explicit is None:tax_defaults[kind]+=1
            else:tax_explicit[kind]+=1
    return transformed,None

# Only tariffs genuinely referenced by a connector can enter the V9 dataset.
for tid in refs:
    candidates=tid_map.get(tid,[])
    if len(candidates)!=1:
        excluded_tariffs[tid]="tariff_id_missing_or_ambiguous"
        continue
    transformed,why=convert(candidates[0])
    if why:excluded_tariffs[tid]=why
    else:included_tariffs[tid]=transformed
for loc in locations:
    lid=text(loc.get("id"))
    if loc.get("publish") is not True:
        excluded_stations["not_published"]+=1;continue
    if text(loc.get("country")).upper() not in {"GB","GBR"}:
        excluded_stations["not_UK"]+=1;continue
    try:
        lat=float(loc["coordinates"]["latitude"])
        lon=float(loc["coordinates"]["longitude"])
    except (KeyError,TypeError,ValueError):
        excluded_stations["missing_coordinates"]+=1;continue
    if not (49<=lat<=61 and -9<=lon<=3):
        excluded_stations["outside_UK_geobounds"]+=1;continue
    cp=copy.deepcopy(loc)
    cp["tccPcprAttribution"]={
        "declaredOperator":label(loc.get("operator")),
        "declaredOwner":label(loc.get("owner")),
        "platform":"ChargePoint CMS",
        "cpoSourceScope":"OCPI_CPO_PCPR",
        "physicalOperatorIndependentlyConfirmed":False
    }
    clean_evses=[]
    for evse in rows(cp.get("evses")):
        if text(evse.get("status")).upper()=="REMOVED":
            excluded_evses["removed"]+=1;continue
        for connector in rows(evse.get("connectors")):
            ids=uniq_ids(connector.get("tariff_ids"))
            source_refs.update(ids)
            safe_ids=[tid for tid in ids if tid in included_tariffs]
            if safe_ids:included_connector_count+=1
            else:unpriced_connector_count+=1
            connector["sourceTariffIds"]=ids
            connector["tariff_ids"]=safe_ids
        clean_evses.append(evse)
    if not clean_evses:
        excluded_stations["no_active_evses"]+=1;continue
    cp["evses"]=clean_evses
    safe_locations.append(cp)
used_ids={tid for loc in safe_locations for e in loc["evses"] for c in e.get("connectors",[]) for tid in c.get("tariff_ids",[])}
v9={
    "country":"GB","collectedAt":data.get("retrievedAt"),
    "source":"Eco-Movement PCPR ChargePoint CPO tariffs",
    "integrationStatus":"cpo_direct_exact_connector_vat_inclusive",
    "sources":[{
        "id":"eco-movement-pcpr-cpo-direct",
        "name":"ChargePoint (opérateur déclaré PCPR)",
        "partyIdsExpected":["CPI"],"country":"GB",
        "pricingScope":"cpo_direct_pcpr",
        "locations":safe_locations,
        "tariffs":[included_tariffs[tid] for tid in sorted(used_ids)],
        "policy":"PCPR CPO feed only; exact connector tariff_ids; GBP prices converted from OCPI excl-VAT to UK public VAT-inclusive; non-GBP/unsupported tariffs left unpriced; platform CPO attribution as declared, no third-party assumption."
    }]
}
staging_path=ROOT/"data/national/uk_eco_movement_pcpr_v9.json.gz"
with gzip.open(staging_path,"wt",encoding="utf-8") as handle:
    json.dump(v9,handle,ensure_ascii=False,separators=(",",":"))
staged_connectors=sum(len(rows(e.get("connectors"))) for loc in safe_locations for e in loc["evses"])
stage_report={
    "generatedAt":out["generatedAt"],"sourceCollectedAt":data.get("retrievedAt"),
    "sourceLocations":len(locations),"stagedPublicLocations":len(safe_locations),
    "stagedConnectors":staged_connectors,"stagedRankableDirectOffers":included_connector_count,
    "stagedUnpricedConnectors":unpriced_connector_count,
    "sourceTariffReferencesPreserved":sum(source_refs.values()),
    "sourceTariffCount":len(tariffs),"GBPConvertedTariffs":len(used_ids),
    "quarantinedTariffCount":len(excluded_tariffs),
    "quarantinedTariffReasons":dict(Counter(excluded_tariffs.values())),
    "quarantinedTariffIds":excluded_tariffs,
    "quarantinedComponentSamples":[{"id":tid,"currency":t.get("currency"),"components":[{"type":p.get("type"),"price":p.get("price"),"step_size":p.get("step_size"),"vat":p.get("vat")} for e in rows(t.get("elements")) for p in rows(e.get("price_components"))]} for tid,t in source_tariffs.items() if tid in excluded_tariffs],
    "excludedLocations":dict(excluded_stations),"excludedEVSEs":dict(excluded_evses),
    "taxDefaultsAppliedByComponent":dict(tax_defaults),
    "taxExplicitByComponent":dict(tax_explicit),
    "taxPolicy":"UK public standard VAT 20% assumed only if OCPI VAT is missing; prices derived from OCPI prices excluding VAT, all GBP TTC",
    "cpoPolicy":"CPO PCPR provenance (not eMSP); declared operator retained (ChargePoint); independently operated physical site identities not inferred",
    "stagedDataset":"data/national/uk_eco_movement_pcpr_v9.json.gz",
    "readyForSnapshotInventoryStage":len(safe_locations)>0 and staged_connectors>0,
    "readyForTariffRanking":included_connector_count>0,
    "integrationStatus":"cpo_direct_exact_connector_vat_inclusive"
}
stage_path=ROOT/"reports/uk/eco-movement-pcpr-v9-staging.json"
stage_path.write_text(json.dumps(stage_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(stage_report,ensure_ascii=False,indent=2))
