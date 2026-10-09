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

# Staged V9 inventory, intentionally NOT rankable until operator identity,
# direct/ad-hoc channel and tax rules are independently demonstrated.
# Preserve the original full PCPR source separately for future reconciliation.
import copy
safe_locations=[]
excluded=collections.Counter()
source_tariff_refs=collections.Counter()
for loc in locations:
    if loc.get("publish") is not True:
        excluded["not_publicly_published"]+=1
        continue
    if text(loc.get("country")).upper() not in {"GB","GBR"}:
        excluded["wrong_country"]+=1
        continue
    try:
        latitude=float(loc["coordinates"]["latitude"])
        longitude=float(loc["coordinates"]["longitude"])
    except (KeyError,TypeError,ValueError):
        excluded["missing_location_coordinates"]+=1
        continue
    if not (49 <= latitude <= 61 and -9 <= longitude <= 3):
        excluded["outside_uk_bounds"]+=1
        continue
    cp=copy.deepcopy(loc)
    # Preserve the CPO/operator and owner identities exactly as declared
    # in the official PCPR feed. ChargePoint is both a possible CPO and
    # the CMS provider to other CPOs; third-party ownership is not inferred.
    cp["tccPcprAttribution"]={
        "declaredOperator":label(loc.get("operator")),
        "declaredOwner":label(loc.get("owner")),
        "platform":"ChargePoint CMS",
        "cpoVerification":"declared_in_pcpr_not_independently_verified"
    }
    for evse in rows(cp.get("evses")):
        for connector in rows(evse.get("connectors")):
            tids=uniq_ids(connector.pop("tariff_ids", []))
            connector["sourceTariffIdsUnverified"]=tids
            for tid in tids:
                source_tariff_refs[tid]+=1
    safe_locations.append(cp)
if len(safe_locations)!=len(locations):
    print("WARNING: PCPR UK staging excluded "+str(len(locations)-len(safe_locations))+" locations; see report.")
v9={
    "country":"GB",
    "collectedAt":data.get("retrievedAt"),
    "source":"Eco-Movement PCPR / ChargePoint CMS",
    "integrationStatus":"inventory_stage_unverified_cpo_direct_tariffs",
    "sources":[{
        "id":"eco-movement-pcpr-cms-unverified",
        "name":"ChargePoint (opérateur déclaré PCPR)",
        "partyIdsExpected":["CPI"],
        "country":"GB",
        "locations":safe_locations,
        "tariffs":[],
        "policy":"Preserve ChargePoint as the PCPR-declared operator. ChargePoint may operate its own charge points as CPO or serve another CPO as CMS; do not invent another operator. Connector tariffs remain non-rankable until public consumer ad-hoc payment and applicable VAT are verified."
    }]
}
staging_path=ROOT/"data/national/uk_eco_movement_pcpr_v9.json.gz"
staging_path.parent.mkdir(parents=True,exist_ok=True)
with gzip.open(staging_path,"wt",encoding="utf-8") as handle:
    json.dump(v9,handle,ensure_ascii=False,separators=(",",":"))
staged_connectors=sum(len(rows(e.get("connectors"))) for loc in safe_locations for e in rows(loc.get("evses")))
stage_report={
    "generatedAt":out["generatedAt"],
    "sourceCollectedAt":data.get("retrievedAt"),
    "sourceLocations":len(locations),
    "stagedPublicLocations":len(safe_locations),
    "stagedConnectors":staged_connectors,
    "stagedRankableDirectOffers":0,
    "sourceTariffReferencesPreserved":sum(source_tariff_refs.values()),
    "excluded":dict(excluded),
    "nonRankableReasons":["ChargePoint is the operator declared by PCPR, but independently operated third-party CMS sites are not distinguished","Raw OCPI CPO tariffs do not explicitly identify ad-hoc PAYG channel","One USD tariff among GBP tariffs; tax VAT field not consistently present"],
    "stagedDataset":"data/national/uk_eco_movement_pcpr_v9.json.gz",
    "readyForSnapshotInventoryStage":len(safe_locations)>0 and staged_connectors>0,
    "readyForTariffRanking":False
}
stage_path=ROOT/"reports/uk/eco-movement-pcpr-v9-staging.json"
stage_path.write_text(json.dumps(stage_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(stage_report,ensure_ascii=False,indent=2))
