#!/usr/bin/env python3
"""G5 offline comparison on immutable national/cache snapshots, never publishes.

SQLite keeps both sides and all candidate decisions with reproducible values.
The historic overlay is a candidate source, NOT independent identity proof.
No network, no price changes. No match is declared if proof is missing.
"""
import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import unicodedata

RULE_VERSION = "g5-fr-2026-11-24-v2"
def norm(value):
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().upper())
def ident(value):
    return re.sub(r"[\s*\-]", "", str(value or "").strip().upper())
def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None
def text(value):
    return str(value) if value is not None else ""
def aslist(value):
    return value if isinstance(value,list) else []
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        return json.load(f)
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()
def dump(value):
    return json.dumps(value,ensure_ascii=False,separators=(",",":"),sort_keys=True)
def plug(value):
    if isinstance(value,dict):
        value=value.get("name") or value.get("standard")
    k=norm(value)
    if k.startswith("IRVE"):
        k=k[4:]
        if k.startswith("TYPE2"): return "TYPE2"
        if k.startswith("CCS"): return "CCS"
        if k.startswith("EF"): return "EF"
    return {"IEC62196T2":"TYPE2","TYPE2":"TYPE2","T2":"TYPE2",
            "IEC62196T2COMBO":"CCS","CCS":"CCS","CCS2":"CCS","COMBO2":"CCS",
            "DOMESTICF":"EF","DOMESTICE":"EF","EF":"EF","TYPEEF":"EF",
            "CHADEMO":"CHADEMO","CHA":"CHADEMO","TYPE1":"TYPE1",
            "IEC62196T1":"TYPE1"}.get(k)
def mode(p):
    return {"TYPE2":"AC","EF":"AC","TYPE1":"AC","CCS":"DC","CHADEMO":"DC"}.get(p)
def distance(a,b):
    if any(v is None for v in (*a,*b)): return None
    lat,lon,lat2,lon2=map(math.radians,(*a,*b))
    return round(6371000*2*math.asin(min(1,math.sqrt(math.sin((lat2-lat)/2)**2+math.cos(lat)*math.cos(lat2)*math.sin((lon2-lon)/2)**2))),3)
def state(a,b):
    if a is None or b is None or a=="" or b=="": return "MISSING"
    return "PASS" if a==b else "FAIL"
def power_check(a,b,acdc):
    if a is None or b is None or a<=0 or b<=0: return "MISSING",None
    delta=round(abs(a-b),6)
    if delta==0: return "PASS",delta
    # The one-decimal national builder permits a provable rounding difference.
    if round(a,1)==round(b,1): return "PASS",delta
    # The 15 kW DC search band is explicitly NOT an acceptance tolerance.
    return "FAIL",delta

POWER_SCOPE_RULE = "g5-fr-2026-11-24-v3-exact-power-scope"
POWER_SCOPE_SHA256 = "196bb587904635159e7d5bbc774a9cd931d7903320ff0b177cf51df59d0637a3"
POWER_SCOPE_NATIONAL_ARTIFACT = 14937133575
MULTITYPE = "MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN"

def read_power_scope(path, expected_sha, national_artifact):
    if expected_sha!=POWER_SCOPE_SHA256 or national_artifact!=POWER_SCOPE_NATIONAL_ARTIFACT or sha(path)!=expected_sha:
        raise ValueError("Unverified power scope evidence")
    result={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            k=(row["station_id"],row["evse_id"])
            if k in result: raise ValueError("Duplicate PDC in power scope")
            if row["scope"] not in (MULTITYPE,"SINGLE_DECLARED_TYPE_NOMINAL_ONLY","PDC_NOMINAL_MISSING_OR_CONFLICTING"):
                raise ValueError("Unknown power scope")
            result[k]=row
    if len(result)!=101856: raise ValueError("Power scope coverage mismatch")
    return result

def scoped_power_check(s,n,enabled=False):
    status,delta=power_check(s["kw"],n["kw"],n["mode"])
    # Exact match only. Preserve source/nominal values and all other checks.
    # Even equal nominal is not proof of an individual socket rating.
    if (enabled and n.get("power_scope")==MULTITYPE
        and state(s["plug"],n["plug"])=="PASS" and state(s["mode"],n["mode"])=="PASS"
        and s["kw"] is not None and n["kw"] is not None and 0<s["kw"]<=n["kw"]):
        return "MISSING",delta,"POWER_SCOPE_NOT_COMPARABLE"
    return status,delta,("same_one_decimal_nominal_rounding" if status=="PASS" and delta else None)

def exact_scope_check(src,dst,profiles,siblings,enabled=False):
    if not src["pk"] or not src["connector"] or not src["price"]:
        return "MISSING","MISSING","NOT_APPLICABLE"
    if len({x["connector"] for x in siblings})!=len(siblings):
        return "NOT_EVALUATED","FAIL","NOT_APPLICABLE"
    def compatible(s,n):
        return (state(s["plug"],n["plug"])!="FAIL" and state(s["mode"],n["mode"])!="FAIL"
                and scoped_power_check(s,n,enabled)[0]!="FAIL")
    plausible=[x for x in profiles if compatible(src,x)]
    reverse=[x for x in siblings if compatible(x,dst)]
    if (len(plausible)==1 and plausible[0] is dst and len(reverse)==1 and reverse[0] is src
        and (src["plug"] is not None or (len(profiles)==1 and len(siblings)==1))):
        return "PASS","PASS","NOT_APPLICABLE"
    return "NOT_EVALUATED","NOT_EVALUATED","NOT_EVALUATED"

CRITERION_ORDER=("country","operator","station_identity","station_uniqueness","evse_identity","evse_uniqueness",
                 "current","plug","power","cardinality","tariff_scope","tariff_homogeneity","address","gps")
def decision_from_criteria(criteria):
    if set(criteria)!=set(CRITERION_ORDER): raise ValueError("Unexpected criterion vector")
    criteria={k:criteria[k] for k in CRITERION_ORDER}
    missing=[k for k,v in criteria.items() if v=="MISSING"]
    pending=[k for k,v in criteria.items() if v=="NOT_EVALUATED"]
    contradictions=[k+":FAIL" for k,v in criteria.items() if v=="FAIL" and k not in ("station_uniqueness","evse_uniqueness")]
    ambiguity=[k+":FAIL" for k in ("station_uniqueness","evse_uniqueness") if criteria[k]=="FAIL"]
    required=("station_identity","station_uniqueness","evse_identity","evse_uniqueness","tariff_scope","cardinality")
    insufficient=[k+":INSUFFICIENT_EVIDENCE" for k in required if criteria[k] not in ("PASS","FAIL")]
    if criteria["tariff_homogeneity"] not in ("PASS","NOT_APPLICABLE","FAIL"):
        insufficient.append("tariff_homogeneity:INSUFFICIENT_EVIDENCE")
    blocked=contradictions+ambiguity+insufficient
    decision=("REJECTED_CONTRADICTION" if contradictions else ("REJECTED_AMBIGUITY" if ambiguity else
              ("UNRESOLVED_INSUFFICIENT_EVIDENCE" if insufficient or pending else "MATCH_VALIDATED")))
    return {"criteria":criteria,"blocking":blocked,"missing":missing,"not_evaluated":pending,
            "first_blocker":blocked[0] if blocked else (pending[0]+":NOT_EVALUATED" if pending else None),"decision":decision}

def parse_address(value):
    if isinstance(value,str): return value.strip()
    if isinstance(value,dict):
        return ", ".join(text(value.get(k)) for k in ("addressLine1","addressLine2","street","postalCode","city") if value.get(k))
    return ""
def validate_national_projection(national, dynamic, static_manifest, source_report):
    """Exact raw PDC keys; never infer operational status from normalized IDs."""
    owners = {}
    for row in national:
        for g in aslist(row[8]):
            for pdc in aslist(g[6]):
                if pdc in owners and owners[pdc] != row[0]:
                    raise ValueError("National PDC belongs to two stations")
                owners[pdc] = row[0]
    if len(owners) != static_manifest["pdcCount"]:
        raise ValueError("Static PDC count mismatch")
    if (dynamic.get("schemaVersion") != 1 or dynamic.get("country") != "FR"
        or not dynamic.get("generatedAt") or not dynamic.get("sourceSha256")
        or source_report["static"]["sourceSha256"] != static_manifest["sourceSha256"]
        or source_report["dynamic"]["sha256"] != dynamic["sourceSha256"]):
        raise ValueError("National static/dynamic provenance mismatch")
    dt.datetime.fromisoformat(dynamic["generatedAt"].replace("Z","+00:00"))
    raw_active = dynamic["enServicePdcIds"]
    records = dynamic["records"]
    active = set(raw_active)
    excluded = {r["id_pdc_itinerance"]:r for r in records}
    if (len(active) != len(raw_active) or len(excluded) != len(records)
        or active & set(excluded) or not (active | set(excluded)).issubset(owners)
        or any(r.get("etat_pdc") not in ("hors_service","inconnu") or
               r.get("id_station_itinerance") != owners[pdc] for pdc,r in excluded.items())
        or dynamic["matchedPdc"] != len(active)+len(excluded)
        or dynamic["displayExcludedPdc"] != len(excluded)
        or dynamic["states"].get("en_service") != len(active)):
        raise ValueError("National dynamic identity/count mismatch")
    for state_ in ("hors_service","inconnu"):
        if dynamic["states"].get(state_) != sum(r["etat_pdc"] == state_ for r in records):
            raise ValueError("National dynamic state count mismatch")
    if not active:
        raise ValueError("Empty active national snapshot: retain last-good, investigate source")
    disposition = {pdc:("en_service" if pdc in active else excluded.get(pdc,{}).get("etat_pdc","MISSING")) for pdc in owners}
    return active, owners, disposition

def candidate_checks(s,n,loc,nsite,exact,alias,owner_unique,source_unique,site_count,approved,scope,cardinality="NOT_EVALUATED",homogeneity="NOT_EVALUATED",power_scope_enabled=False):
    dist=distance(loc["coords"],nsite["coords"])
    address=state(norm(loc["address"]),norm(nsite["address"]))
    gps="MISSING" if dist is None else ("PASS" if dist<=10 else "FAIL")
    source_country=loc["country"]
    ctry=state(source_country,"FR")
    if loc["foreign_be"]: ctry="FAIL"
    # Country and CPO name equality must come from independent reviewed evidence;
    # a label copied from the legacy spatial join is not a supplier assertion.
    pair=(loc["operator_id"],norm(nsite["operator"]))
    cpo="PASS" if pair in approved and nsite["operator"] not in ("","AUTRE") else "MISSING"
    # Do not infer a contradiction from mere differences of spelling. If the
    # same supplier ID has reviewed, incompatible identities, flag conflict
    # only where the source explicitly contradicts a reviewed national identity.
    reviewed_names={name for supplier,name in approved if supplier==pair[0]}
    if reviewed_names and pair[1] not in reviewed_names and pair[1] and loc["operator_name"] and norm(loc["operator_name"])!=pair[1]:
        cpo="FAIL"
    # A conflicting observed supplier label is a diagnostic, not an automatic
    # CPO contradiction unless independent proof establishes the association.
    name_compare=state(norm(loc["operator_name"]),norm(nsite["operator"]))
    base_method="exact" if exact else ("validated_alias" if alias else ("address" if address=="PASS" else "gps"))
    method=base_method+("+operator" if cpo=="PASS" else "+operator_unverified")
    site="PASS" if exact or alias else ("PASS" if address=="PASS" or gps=="PASS" else ("FAIL" if address=="FAIL" and gps=="FAIL" else "MISSING"))
    # Both source and target must have unique official identity. A legacy
    # grouping / nearby site never supplies EVSE identity by itself.
    identity="PASS" if exact or alias else "MISSING"
    p=state(s["plug"],n["plug"])
    current=state(s["mode"],n["mode"])
    kw,delta,power_reason=scoped_power_check(s,n,power_scope_enabled and exact)
    unique="PASS" if owner_unique and source_unique else "FAIL"
    site_unique="PASS" if (exact or alias) and owner_unique else ("PASS" if site_count==1 else ("FAIL" if site_count>1 else "MISSING"))
    criteria={"country":ctry,"operator":cpo,"station_identity":site,"station_uniqueness":site_unique,
        "evse_identity":identity,"evse_uniqueness":unique,"current":current,"plug":p,
        "power":kw,"cardinality":cardinality,"tariff_scope":scope,
        "tariff_homogeneity":homogeneity}
    # Address/GPS are observed even for exact IDs but don't block that branch.
    if exact or alias:
        criteria["address"]="NOT_APPLICABLE"
        criteria["gps"]="NOT_APPLICABLE"
    else:
        criteria["address"]="PASS" if address=="PASS" else ("NOT_APPLICABLE" if gps=="PASS" else address)
        criteria["gps"]="PASS" if gps=="PASS" else ("NOT_APPLICABLE" if address=="PASS" else gps)
    result=decision_from_criteria(criteria)
    return {**result,"method":method,"distance_m":dist,
            "gps_limit_m":10,"address_observation":address,"gps_observation":gps,
            "operator_name_observation":name_compare,"power_delta_kw":delta,
            "dc_candidate_band_kw":15 if n["mode"]=="DC" else None,
            "dc_within_candidate_band":delta<=15 if delta is not None and n["mode"]=="DC" else None,
            "power_justification":power_reason}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workspace",type=Path,required=True)
    parser.add_argument("--checkout",type=Path,required=True)
    parser.add_argument("--national-root",type=Path,required=True)
    parser.add_argument("--national-provenance",type=Path,required=True)
    parser.add_argument("--overlay",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--power-scope",type=Path)
    args=parser.parse_args()
    work,repo,overlay,out=args.workspace,args.checkout,args.overlay,args.out
    out.mkdir(parents=True,exist_ok=False)
    national_root=args.national_root.resolve()
    national_proof=read(args.national_provenance)
    power_scope=read_power_scope(args.power_scope,POWER_SCOPE_SHA256,national_proof["nationalArtifact"]) if args.power_scope else {}
    master=national_root/"data/national/france-irve-static-v9"
    mm=read(master/"manifest.json")
    if mm.get("allFile")!="all.json.gz" or sha(master/"all.json.gz")!=mm["allSha256"]:
        raise ValueError("Unverified national master file")
    national=gz(master/"all.json.gz")
    if len(national)!=mm["stationCount"]: raise ValueError("National station count mismatch")
    dynamic_path=national_root/"data/national/france-irve-dynamic-status-v9.json.gz"
    if mm["allSha256"]!=national_proof["nationalAllSha256"] or sha(dynamic_path)!=national_proof["nationalDynamicFileSha256"]:
        raise ValueError("National pinned snapshot mismatch")
    dynamic=gz(dynamic_path)
    source_report_path=national_root/"reports/france/irve/irve-residual-crosswalk-latest.json"
    active,all_owners,national_state=validate_national_projection(national,dynamic,mm,read(source_report_path)["sources"])
    global_owners=collections.defaultdict(set)
    for pdc,sid in all_owners.items():
        global_owners[ident(pdc)].add((sid,pdc))
    cache=work/"data/electroverse/tariff_cache"
    manifest=read(cache/"manifest.json")
    map_path=work/"data/electroverse/irve_location_mapping.json"
    mapping=read(map_path)["mappings"]
    mapped={text(r["electroverseLocationPk"]):r for r in mapping}
    if len(mapped)!=len(mapping): raise ValueError("Duplicate mapping source location")
    review=repo/"data/platforms/electroverse/validated-mappings"
    registry=read(review/"g5-operator-crosswalk-review.json")
    approved=set()
    for pair in registry["approvedPairs"]:
        ev=pair.get("evidence") or {}
        if (pair.get("reviewStatus")=="INDEPENDENT_REVIEW_APPROVED" and pair.get("country")=="FR"
            and ev.get("kind")=="explicit_supplier_operator_to_cpo_link" and ev.get("sourceOperatorIdExplicit")
            and ev.get("nationalCpoIdentityExplicit") and ev.get("supplierRecord") and ev.get("nationalRecord")
            and ev["supplierRecord"]!=ev["nationalRecord"]):
            approved.add((text(pair["supplierOperatorId"]),norm(pair["nationalOperator"])))
        else: raise ValueError("Unapproved crosswalk entry")
    alias_by_source=collections.defaultdict(set)
    alias_provenance={}
    for filename in ("numeric-residual.json","s82-residual.json","mgp-residual.json","le2-residual.json","adp-structured-residual.json","p01-structured-residual.json","b-residual.json","sae-structured-residual.json","h01-structured-residual.json","generic-small-buckets.json"):
        doc=read(review/filename)
        alias_provenance[filename]=sha(review/filename)
        for row in doc.get("mappings",[]):
            loc,pk,ref,target=(text(row.get(k)) for k in ("electroverseLocationPk","electroverseEvsePk","physicalReference","targetPdc"))
            if loc and pk and ref and target and row.get("evidence"):
                alias_by_source[(loc,pk,ident(ref))].add((ident(target),filename))
    # Preserve current tariff overlay as prior candidate evidence only.
    om=read(overlay/"manifest.json")
    links=collections.defaultdict(set)
    old_target=collections.defaultdict(set)
    for tile in om["tiles"]:
        path=overlay/tile["file"]
        if sha(path)!=tile["sha256"]: raise ValueError("Overlay tile SHA mismatch")
        for offer in gz(path).get("emspOffers",[]):
            md=offer.get("metadata") or {}
            loc=text(md.get("electroverseLocationPk"))
            pks=set(map(text,aslist(md.get("electroverseEvsePks"))+aslist(md.get("electroverseAliasEvsePks"))+[md.get("electroverseEvsePk")]))-{""}
            for target in offer.get("evseIds",[]):
                key=ident(target)
                old_target[key].add(offer["id"])
                for pk in pks: links[(loc,pk)].add((key,offer["id"],text(md.get("identityMode"))))
    status=work/"data/electroverse/live_statuses"
    sm=read(status/"manifest.json")
    status_doc=gz(status/sm["ledger"])
    screened=dt.datetime.fromisoformat(om["statusGate"]["faultCheckedAt"].replace("Z","+00:00"))
    def fault(loc,pk):
        value=text(status_doc.get("locations",{}).get(loc,{}).get(pk)).upper() or "MISSING"
        ts=status_doc.get("observedAtByLocation",{}).get(loc)
        recent=False
        if ts and value in ("OUTOFORDER","INOPERATIVE"):
            age=(screened-dt.datetime.fromisoformat(ts.replace("Z","+00:00"))).total_seconds()
            recent=0<=age<=86400
        return value,ts,recent
    db=sqlite3.connect(out/"g5-matching.sqlite")
    db.executescript("""
    PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=MEMORY;
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE national_station(id TEXT PRIMARY KEY,name TEXT,address TEXT,operator TEXT,lat REAL,lon REAL,pdc_count INTEGER);
    CREATE TABLE national_connector(id INTEGER PRIMARY KEY,station_id TEXT,evse_id TEXT,evse_normalized TEXT,plug_raw TEXT,plug TEXT,mode TEXT,kw REAL);
    CREATE TABLE source_location(id TEXT PRIMARY KEY,mapped_station TEXT,address TEXT,operator_id TEXT,operator_name TEXT,country TEXT,lat REAL,lon REAL,source_evse_count INTEGER);
    CREATE TABLE source_connector(id INTEGER PRIMARY KEY,location_pk TEXT,evse_pk TEXT,connector_pk TEXT,physical_reference TEXT,reference_normalized TEXT,plug_raw TEXT,plug TEXT,mode TEXT,kw REAL,has_price INTEGER,tariff_signature TEXT,technical_status TEXT,status_at TEXT,recent_fault INTEGER);
    CREATE TABLE candidate(national_id INTEGER,source_id INTEGER,method TEXT,decision TEXT,first_blocker TEXT,details TEXT,prior_offer_ids TEXT,alias_files TEXT,pattern_id INTEGER,PRIMARY KEY(national_id,source_id)) WITHOUT ROWID;
    CREATE TABLE national_disposition(national_id INTEGER PRIMARY KEY,candidate_count INTEGER,validated_count INTEGER,prior_offer_count INTEGER,result TEXT);
    CREATE TABLE national_operational_scope(evse_id TEXT PRIMARY KEY,station_id TEXT,state TEXT,eligible INTEGER);
    CREATE TABLE criterion_pattern(id INTEGER PRIMARY KEY,criteria TEXT NOT NULL UNIQUE);
    CREATE TABLE source_disposition(source_id INTEGER PRIMARY KEY,candidate_count INTEGER,validated_count INTEGER,result TEXT);
    """)
    sites={}; target={}; by_ref=collections.defaultdict(list); by_site=collections.defaultdict(list)
    address_index=collections.defaultdict(set); grid=collections.defaultdict(set)
    def cell(lat,lon):
        return (math.floor(lat/.001),math.floor(lon/.001))
    db.executemany("INSERT INTO national_operational_scope VALUES(?,?,?,?)",[(pdc,sid,national_state[pdc],int(pdc in active)) for pdc,sid in all_owners.items()])
    nr=[]
    for row in national:
        sid=text(row[0]); lat,lon=number(row[3]),number(row[4])
        active_pdc={pdc for g in aslist(row[8]) for pdc in aslist(g[6]) if pdc in active}
        if not active_pdc: continue
        site={"name":text(row[1]),"address":text(row[2]),"operator":text(row[5]),"coords":(lat,lon),"pdc_count":len(active_pdc)}
        if sid in sites: raise ValueError("Duplicate national station")
        sites[sid]=site
        if norm(site["address"]): address_index[norm(site["address"])].add(sid)
        if lat is not None and lon is not None: grid[cell(lat,lon)].add(sid)
        for g in aslist(row[8]):
            for pdc in aslist(g[6]):
                if pdc not in active: continue
                rid=len(target)+1
                item={"station":sid,"evse":text(pdc),"norm":ident(pdc),"plug":plug(g[1]),"mode":text(g[2]) or None,"kw":number(g[3])}
                if args.power_scope: item["power_scope"]=power_scope[(sid,text(pdc))]["scope"]
                target[rid]=item
                by_ref[item["norm"]].append(rid); by_site[sid].append(rid)
                nr.append((rid,sid,item["evse"],item["norm"],text(g[1]),item["plug"],item["mode"],item["kw"]))
    if args.power_scope and set(power_scope)!={(x["station"],x["evse"]) for x in target.values()}:
        raise ValueError("Power scope identity mismatch")
    if {x["evse"] for x in target.values()}!=active:
        raise ValueError("National active projection mismatch")
    db.executemany("INSERT INTO national_station VALUES(?,?,?,?,?,?,?)",[(k,x["name"],x["address"],x["operator"],*x["coords"],x["pdc_count"]) for k,x in sites.items()])
    db.executemany("INSERT INTO national_connector VALUES(?,?,?,?,?,?,?,?)",nr)
    del nr
    refowners=collections.defaultdict(set)
    locations={}; sources=[]; metadata_keys=collections.Counter(); source_groups=collections.defaultdict(list)
    seenloc=set()
    for sh in manifest["shards"]:
        doc=read(cache/sh["file"])
        if len(doc["stations"])!=sh["count"]: raise ValueError("Invalid shard count")
        for key,row in doc["stations"].items():
            loc=text(row.get("electroverseLocationPk"))
            if not loc or loc!=key or loc in seenloc: raise ValueError("Duplicate/inconsistent source location")
            seenloc.add(loc)
            m=mapped.get(loc,{})
            el=m.get("electroverse") or {}
            ir=m.get("irve") or {}
            metadata_keys.update(el.keys())
            coords=(number(el.get("lat",el.get("latitude"))),number(el.get("lon",el.get("longitude"))))
            country=el.get("countryCode",el.get("country"))
            if isinstance(country,dict): country=country.get("code")
            country=norm(country)
            if country=="FRANCE":country="FR"
            if country in ("BELGIUM","BELGIQUE"):country="BE"
            operator=el.get("operatorName")
            if not operator and isinstance(el.get("operator"),dict): operator=el["operator"].get("name")
            st=text(m.get("irveStationId"))
            nl,nn=number(ir.get("lat")),number(ir.get("lon"))
            foreign=bool(ident(st).startswith("BE") and m.get("irvePdcIds") and all(ident(x).startswith("BE") for x in m["irvePdcIds"]) and nl is not None and nn is not None and 49.45<=nl<=51.65 and 2.5<=nn<=6.5)
            evses=aslist((row.get("tariff") or {}).get("evses"))
            locations[loc]={"mapped":st,"address":parse_address(el.get("address") or el.get("formattedAddress")),"operator_id":text(el.get("operatorId")),"operator_name":text(operator),"country":country,"coords":coords,"foreign_be":foreign,"evse_count":len(evses)}
            for e in evses:
                pk=text(e.get("pk")); ref=text(e.get("physicalReference")); rkey=ident(ref)
                if rkey: refowners[rkey].add((loc,pk))
                connectors=aslist(e.get("connectors"))
                # Explicit no-connector row preserves source coverage.
                for c in connectors or [{}]:
                    raw=c.get("standard")
                    p=plug(raw); sig=hashlib.sha256(dump({k:c.get(k) for k in ("isChargingFree","priceComponents","complexPricingDetail")}).encode()).hexdigest()
                    source={"id":len(sources)+1,"loc":loc,"pk":pk,"connector":text(c.get("pk")),"ref":ref,"norm":rkey,"plug_raw":dump(raw),"plug":p,"mode":mode(p),"kw":number(c.get("kilowatts")),"price":bool(c.get("isChargingFree") is True or c.get("priceComponents") or (c.get("complexPricingDetail") or {}).get("restrictions")),"sig":sig}
                    source["status"],source["status_at"],source["fault"]=fault(loc,pk)
                    sources.append(source)
                    source_groups[(loc,pk)].append(source)
    if len(seenloc)!=manifest["totalStations"]: raise ValueError("Source count mismatch")
    db.executemany("INSERT INTO source_location VALUES(?,?,?,?,?,?,?,?,?)",[(k,x["mapped"],x["address"],x["operator_id"],x["operator_name"],x["country"],*x["coords"],x["evse_count"]) for k,x in locations.items()])
    db.executemany("INSERT INTO source_connector VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[(s["id"],s["loc"],s["pk"],s["connector"],s["ref"],s["norm"],s["plug_raw"],s["plug"],s["mode"],s["kw"],int(s["price"]),s["sig"],s["status"],s["status_at"],int(s["fault"])) for s in sources])
    # Station candidates discovered independently by strict address / GPS, plus
    # the historic mapped station (even if too distant) for reason tracing.
    candidates_by_loc={}
    for loc,x in locations.items():
        c=set()
        adr=norm(x["address"])
        if adr:c.update(address_index.get(adr,()))
        lat,lon=x["coords"]
        if lat is not None and lon is not None:
            i,j=cell(lat,lon)
            radius=max(1,math.ceil(.0001/max(.01,abs(math.cos(math.radians(lat))))/.001))
            for a in range(i-1,i+2):
                for b in range(j-radius,j+radius+1):
                    for sid in grid.get((a,b),()):
                        if distance(x["coords"],sites[sid]["coords"])<=10:c.add(sid)
        close=set(c)
        if x["mapped"] in sites:c.add(x["mapped"])
        candidates_by_loc[loc]=(c,close)
    nc=collections.Counter(); nv=collections.Counter(); sc=collections.Counter(); sv=collections.Counter()
    blockers=collections.Counter(); first=collections.Counter(); outcomes=collections.Counter()
    missing_counts=collections.Counter(); patterns={}; verified_exact=0
    recent_fault_matches=0; exact_outcomes=collections.Counter()
    # Only exact source EVSE references can currently receive a new positive
    # scope proof. Prior aliases are retained but need individual scope review.
    def exact_scope(src,dst):
        return exact_scope_check(src,dst,[target[i] for i in by_ref[dst["norm"]]],
                                 source_groups[(src["loc"],src["pk"])],bool(args.power_scope))
    comparisons=0; buf=[]; missing_sources=0; exact_pairs=0; technical_exact_pass=0
    for s in sources:
        loc=s["loc"]; x=locations[loc]; rawref=s["norm"]
        exact_ids=set(by_ref.get(rawref,())) if rawref else set()
        aliases=alias_by_source.get((loc,s["pk"],rawref),set())
        alias_targets={a[0] for a in aliases}
        alias_ids={rid for ref in alias_targets for rid in by_ref.get(ref,())}
        prior=links.get((loc,s["pk"]),set())
        prior_ids={rid for ref,_,_ in prior for rid in by_ref.get(ref,())}
        station_candidates,close=candidates_by_loc[loc]
        selected=exact_ids|alias_ids|prior_ids
        # Do not invent alternatives for a globally exact source PDC. If
        # identity is missing, examine all available local/geo/address targets.
        if not exact_ids and not alias_ids:
            selected.update(rid for sid in station_candidates for rid in by_site[sid])
        if not selected: missing_sources+=1
        for rid in sorted(selected):
            n=target[rid]; site=sites[n["station"]]
            # multiple groups on a PDC are not multiple station owners
            unique_target=len(global_owners[n["norm"]])==1
            unique_source=bool(s["pk"] and (not rawref or len(refowners[rawref])==1))
            exact=rid in exact_ids; alias=rid in alias_ids and not exact
            # Prior compiled offer is only evidence of old scope, not proof of
            # current per-connector scope. Record but require explicit review.
            old=[(offer,mode_) for ref,offer,mode_ in prior if ref==n["norm"]]
            scope="MISSING" if not s["price"] else "NOT_EVALUATED"
            card=hom="NOT_EVALUATED"
            if exact and unique_target and unique_source:
                scope,card,hom=exact_scope(s,n)
            res=candidate_checks(s,n,x,site,exact,alias,unique_target,unique_source,len(close),approved,scope,card,hom,power_scope_enabled=bool(args.power_scope))
            res["scope_evidence"]="unique_exact_source_connector_to_national_profile" if scope=="PASS" else None
            res["prior_overlay_scope_observation"]=bool(old)
            res["source_evse_count"]=x["evse_count"];res["national_pdc_count"]=site["pdc_count"]
            res["source_has_price_payload"]=s["price"];res["source_technical_status"]=s["status"]
            res["source_status_at"]=s["status_at"];res["recent_fault_excluded"]=s["fault"]
            if exact:
                exact_outcomes[res["decision"]]+=1
                exact_pairs+=1
                if all(res["criteria"][k]=="PASS" for k in ("current","plug","power")):technical_exact_pass+=1
            for reason in res["blocking"]:blockers[reason]+=1
            for reason in res["missing"]:missing_counts[reason]+=1
            if res["first_blocker"]:first[res["first_blocker"]]+=1
            outcomes[res["decision"]]+=1
            nc[rid]+=1;sc[s["id"]]+=1
            if res["decision"]=="MATCH_VALIDATED":
                nv[rid]+=1;sv[s["id"]]+=1
                if exact:verified_exact+=1
                if s["fault"]:recent_fault_matches+=1
            # Deduplicate repeated criterion vectors, while preserving per-
            # candidate values, method, all blockers and observations.
            pattern=dump({"criteria":res.pop("criteria"),"blocking":res.pop("blocking"),"missing":res.pop("missing"),"not_evaluated":res.pop("not_evaluated")})
            if pattern not in patterns:
                patterns[pattern]=len(patterns)+1
            buf.append((rid,s["id"],res["method"],res["decision"],res["first_blocker"],dump(res),dump(sorted(old)),dump(sorted(fn for ref,fn in aliases if ref==n["norm"])),patterns[pattern]))
            comparisons+=1
            if len(buf)>=10000:
                db.executemany("INSERT INTO candidate VALUES(?,?,?,?,?,?,?,?,?)",buf);buf.clear()
    if buf:db.executemany("INSERT INTO candidate VALUES(?,?,?,?,?,?,?,?,?)",buf)
    db.executemany("INSERT INTO criterion_pattern VALUES(?,?)",[(pid,pat) for pat,pid in patterns.items()])
    national_out=collections.Counter()
    for rid,n in target.items():
        count=nc[rid]; validated=nv[rid]
        result="NO_CANDIDATE_IN_CACHED_SCOPE" if not count else ("MATCH_VALIDATED" if validated else "CANDIDATES_UNRESOLVED")
        national_out[result]+=1
        db.execute("INSERT INTO national_disposition VALUES(?,?,?,?,?)",(rid,count,validated,len(old_target.get(n["norm"],())),result))
    for s in sources:
        sid=s["id"];count=sc[sid];validated=sv[sid]
        result="NO_NATIONAL_CANDIDATE" if not count else ("MATCH_VALIDATED" if validated else "CANDIDATES_UNRESOLVED")
        db.execute("INSERT INTO source_disposition VALUES(?,?,?,?)",(sid,count,validated,result))
    db.executescript("""
    CREATE INDEX national_evse ON national_connector(evse_normalized);
    CREATE INDEX national_station_lookup ON national_connector(station_id);
    CREATE INDEX national_name ON national_station(name);
    CREATE INDEX national_address ON national_station(address);
    CREATE INDEX national_scope_station ON national_operational_scope(station_id);
    CREATE INDEX source_evse ON source_connector(location_pk,evse_pk,connector_pk);
    CREATE INDEX candidate_source ON candidate(source_id);
    """)
    summary={"schemaVersion":1,"ruleVersion":POWER_SCOPE_RULE if args.power_scope else RULE_VERSION,"country":"FR","mode":"AUDIT_ONLY_NO_PRICE_PROMOTION",
        "comparisonAt":dt.datetime.now(dt.timezone.utc).isoformat(),"codeSha":__import__("os").environ.get("GITHUB_SHA"),
        "nationalArtifactProvenance":national_proof,
        "powerScopeEvidenceSha256":POWER_SCOPE_SHA256 if args.power_scope else None,
        "nationalManifestSha256":sha(master/"manifest.json"),"nationalAllSha256":mm["allSha256"],"nationalSourceDate":mm.get("sourceRetrievedAt"),
        "electroverseTariffArtifact":14760747281,"electroverseStatusArtifact":14838028097,
        "tariffManifestSha256":sha(cache/"manifest.json"),"mappingSha256":sha(map_path),
        "statusManifestSha256":sha(status/"manifest.json"),"overlayManifestSha256":sha(overlay/"manifest.json"),
        "operatorRegistrySha256":sha(review/"g5-operator-crosswalk-review.json"),"aliasEvidenceSha256":alias_provenance,
        "nationalStations":len(sites),"nationalEvseIds":len(active),"nationalConnectorProfiles":len(target),
        "nationalStaticStations":mm["stationCount"],"nationalStaticEvseIds":mm["pdcCount"],
        "nationalDynamicDate":dynamic["generatedAt"],"nationalDynamicSha256":sha(dynamic_path),
        "nationalDynamicSourceSha256":dynamic["sourceSha256"],"nationalProvenanceReportSha256":sha(source_report_path),
        "nationalOperationalStates":dict(collections.Counter(national_state.values())),
        "exactCandidateDisposition":dict(exact_outcomes),"exactScopeValidatedPairs":verified_exact,
        "validatedPairsWithRecentHistoricalFault":recent_fault_matches,
        "missingCriteriaNonBlocking":dict(missing_counts),"criterionPatternCount":len(patterns),
        "sourceLocations":len(locations),"sourceEvseConnectorRows":len(sources),"sourceRowsWithoutCandidate":missing_sources,
        "candidateComparisons":comparisons,"exactIdentityCandidatePairs":exact_pairs,"exactPairsPassingPlugCurrentPower":technical_exact_pass,
        "nationalDisposition":dict(national_out),"candidateDisposition":dict(outcomes),"allBlockingCriteria":dict(blockers),"firstBlockingCriteria":dict(first),
        "reviewedOperatorPairs":len(approved),"observedSourceLocationFieldNames":dict(metadata_keys),
        "historicalOverlayOffers":om.get("stats",{}).get("publishedOffers"),
        "limitations":["National compact profile is station/EVSE/type/nominal-power, not a physical socket ID inventory.",
            "Prior alias registries and overlay links are evidence candidates, not blanket new operator or tariff-scope approval.",
            "Only source records available in pinned cache; no-candidate is not proof that Electroverse has no offer anywhere.",
            "Exact unique connector scope can be certified in this audit; aliases/fallback and group scope still require individual proof. Missing attributes are not standalone blockers; NOT_EVALUATED is distinct.",
            "National static/dynamic input is historical, not current availability; exclusions retained in national_operational_scope.",
            "MATCH_VALIDATED is matching/scope only; price calculation, technical fault eligibility and promotion are separate.",
            "Artifact is a queryable candidate archive; durable post-expiry retention and Production generation binding are still required."],
        "supplierCalls":0,"automaticPublication":False}
    db.executemany("INSERT INTO metadata VALUES(?,?)",[(k,dump(v)) for k,v in summary.items()])
    db.commit()
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Decision index integrity failed")
    for table,wanted in [("national_disposition",len(target)),("source_disposition",len(sources)),("candidate",comparisons),("national_operational_scope",len(all_owners)),("criterion_pattern",len(patterns))]:
        if db.execute("SELECT count(*) FROM "+table).fetchone()[0]!=wanted:raise ValueError("Decision coverage mismatch "+table)
    if db.execute("SELECT count(*) FROM candidate c LEFT JOIN criterion_pattern p ON p.id=c.pattern_id WHERE p.id IS NULL").fetchone()[0]:
        raise ValueError("Missing criterion vector")
    db.close()
    summary["sqliteSha256"]=sha(out/"g5-matching.sqlite")
    summary["sqliteBytes"]=(out/"g5-matching.sqlite").stat().st_size
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("G5_REAL_COMPARISON "+dump(summary))

if __name__=="__main__":
    main()
