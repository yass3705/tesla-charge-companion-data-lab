#!/usr/bin/env python3
"""G5 offline address provenance and GPS station/pair diagnostics only."""
import collections as C
import csv
import gzip
import json
import math
import os
import pathlib
import re
import sqlite3
import sys
import unicodedata
import zipfile
from scripts.audit_irve_g5_power_scope import download, verify, digest, write_csv
from scripts.audit_irve_g5_nonexact_inventory import RULE, VALID, j
from scripts.audit_electroverse_g5_real_matching import norm, parse_address, distance, state, power_check

def tokens(value):
    if not isinstance(value,str): return []
    return re.findall(r"[a-z0-9]+",unicodedata.normalize("NFKD",value.casefold()).encode("ascii","ignore").decode())

def address_relation(a,b):
    x,y=tokens(a),tokens(b)
    if not x or not y:return "MISSING"
    if x==y:return "EXACT_TOKEN_MATCH"
    if len(x)>len(y):x,y=y,x
    if len(x)>=3 and x[0].isdigit() and x==y[:len(x)] and any(re.fullmatch(r"[0-9]{5}",t) for t in y[len(x):]):
        return "STREET_PREFIX_REVIEW_ONLY"
    return "DIFFERENT_OR_UNRESOLVED"

def valid_coords(a):
    return all(isinstance(x,(int,float)) and math.isfinite(x) for x in a) and -90<=a[0]<=90 and -180<=a[1]<=180

def address_fields(obj,path=""):
    # Only inspect location-level metadata. Never read arbitrary tariff descriptions as addresses.
    if not isinstance(obj,dict):return {}
    out={}
    for key,val in obj.items():
        k=key.lower()
        p=path+key
        if k in ("address","formattedaddress","addressline1","addressline2","street","postalcode","postcode","city","town"):
            if val:out[p]=parse_address(val) if isinstance(val,dict) else str(val)
        elif k in ("location","charginglocation","site","metadata","electroverse","tariff","locationdetails") and isinstance(val,dict):
            out.update(address_fields(val,p+"."))
    return {k:v for k,v in out.items() if v}

def compatible(n,s):
    return (state(n["plug"],s["plug"])!="FAIL" and state(n["mode"],s["mode"])!="FAIL" and power_check(n["kw"],s["kw"],n["mode"])[0]!="FAIL")

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_g5_address_gps_diagnostics_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    base=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(base["db.sqlite"],pin["sqliteSha256"])
    rp=json.loads(base["report.json"].read_text())
    if rp["codeSha"]!=pin["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sourcePin"]["tariff"]!=pin["tariff"] or rp["newValidated"]!=14968 or rp["nonExactUnchanged"]!=559998:raise ValueError("Ledger provenance")
    db=sqlite3.connect(base["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Ledger integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=rp["codeSha"]:raise ValueError("Metadata")
    valid={(x[0],x[1]) for x in db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,))}
    vn={a for a,b in valid};vs={b for a,b in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("Reference")
    sites={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_station")}
    locs={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_location")}
    ns={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_connector")}
    ss={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_connector")}
    bysite=C.defaultdict(list);byloc=C.defaultdict(list)
    for n in ns.values():bysite[n["station_id"]].append(n)
    for s in ss.values():byloc[s["location_pk"]].append(s)
    src=download(root/"tariff",pin["tariff"],{"manifest.json":("data","electroverse","tariff_cache","manifest.json"),"map.json":("data","electroverse","irve_location_mapping.json")})
    verify(src["manifest.json"],meta["tariffManifestSha256"]);verify(src["map.json"],meta["mappingSha256"])
    manifest=json.loads(src["manifest.json"].read_text())
    mappings=json.loads(src["map.json"].read_text())["mappings"]
    mapped={str(x["electroverseLocationPk"]):x for x in mappings}
    if len(mapped)!=len(mappings) or len(locs)!=manifest["totalStations"]:raise ValueError("Source coverage")
    raw={};seen=set()
    with zipfile.ZipFile(root/"tariff"/"input.zip") as z:
        names=z.namelist()
        for sh in manifest["shards"]:
            path=pathlib.PurePosixPath(sh["file"])
            if path.is_absolute() or ".." in path.parts:raise ValueError("Unsafe shard")
            hits=[p for p in names if ("/"+p).endswith("/data/electroverse/tariff_cache/"+str(path))]
            if len(hits)!=1:raise ValueError("Shard identity")
            doc=json.loads(z.read(hits[0]))
            if len(doc["stations"])!=sh["count"]:raise ValueError("Shard count")
            for loc,row in doc["stations"].items():
                if loc in seen or str(row.get("electroverseLocationPk"))!=loc:raise ValueError("Location identity")
                seen.add(loc);raw[loc]=address_fields(row)
    if seen!=set(locs):raise ValueError("Ledger/cache location mismatch")
    opfile=pathlib.Path("data/platforms/electroverse/validated-mappings/g5-operator-crosswalk-review.json")
    verify(opfile,meta["operatorRegistrySha256"])
    approved={(str(x["supplierOperatorId"]),norm(x["nationalOperator"])) for x in json.loads(opfile.read_text())["approvedPairs"]}
    # Independent geographic discovery; no historic mapped site injected into GPS set.
    grid=C.defaultdict(list)
    def cell(a):return tuple(math.floor(x/.001) for x in a)
    for sid,n in sites.items():
        a=(n["lat"],n["lon"])
        if valid_coords(a):grid[cell(a)].append(sid)
    geo={};reverse=C.defaultdict(set);address=[];counts=C.Counter();fields=C.Counter()
    for loc,s in locs.items():
        el=mapped.get(loc,{}).get("electroverse") or {}
        mf=address_fields(el);rf=raw[loc];fields.update("mapping."+k for k in mf);fields.update("cache."+k for k in rf)
        ledger=s["address"];chosen=parse_address(el.get("address") or el.get("formattedAddress"))
        if (ledger or "")!=(chosen or ""):raise ValueError("Mapping projection changed")
        status="LEDGER_PRESENT" if ledger else "SOURCE_METADATA_PRESENT_NOT_PROJECTED" if mf or rf else "NO_ADDRESS_FIELDS_IN_INSPECTED_ARCHIVE"
        counts[status]+=1
        n=sites.get(s["mapped_station"],{})
        address.append(dict(location_pk=loc,ledger_address=ledger,mapping_fields=j(mf),raw_cache_fields=j(rf),mapped_station=s["mapped_station"],mapped_national_address=n.get("address"),relation=address_relation(ledger,n.get("address")),status=status))
        a=(s["lat"],s["lon"]);hits={}
        if valid_coords(a):
            i,k=cell(a);rad=max(1,math.ceil(.0001/max(.01,abs(math.cos(math.radians(a[0]))))/.001))
            for x in range(i-1,i+2):
                for y in range(k-rad,k+rad+1):
                    for sid in grid.get((x,y),()):
                        n=sites[sid];d=distance(a,(n["lat"],n["lon"]))
                        if d is not None and d<=10:hits[sid]=d;reverse[sid].add(loc)
        geo[loc]=hits
    out=root/"results";out.mkdir()
    write_csv(out/"address-provenance.csv.gz",address,list(address[0]))
    stations=[];site_stats=C.Counter();free_site_pairs=C.Counter()
    # Count complete competitor scopes, including already allocated and missing attributes.
    for loc,hits in geo.items():
        s=locs[loc];site_stats["NO_GPS_SITE" if not hits else "ONE_GPS_SITE" if len(hits)==1 else "MULTIPLE_GPS_SITES"]+=1
        for sid,d in hits.items():
            n=sites[sid];lhs=bysite[sid];rhs=byloc[loc]
            op="PASS" if (s["operator_id"],norm(n["operator"])) in approved else "NOT_INDEPENDENTLY_PROVEN"
            ctry="MISSING" if not s["country"] else "PASS" if s["country"]=="FR" else "FAIL"
            # Raw site counts are diagnostic, not proof of physical socket equivalence.
            k="0_TO_5M" if d<=5 else "OVER_5_TO_10M";site_stats[k]+=1
            stations.append(dict(location_pk=loc,station_id=sid,distance_m=d,gps_site_count=len(hits),reverse_location_count=len(reverse[sid]),operator_id=s["operator_id"],operator_label=s["operator_name"],national_operator=n["operator"],operator_proof=op,country=ctry,national_profiles=len(lhs),source_connectors=len(rhs),national_pdc_count=n["pdc_count"],source_evse_count=s["source_evse_count"],address_relation=address_relation(s["address"],n["address"])))
    write_csv(out/"gps-stations.csv.gz",stations,list(stations[0]))
    patterns={x["id"]:json.loads(x["criteria"]) for x in db.execute("SELECT * FROM criterion_pattern")}
    scopes={};stats=C.Counter();reasons=C.Counter();total=0;free=0
    cols=["national_id","source_id","station_id","location_pk","distance_m","allocation","pattern_id","decision","original_blockers","operator_proof","gps_site_count","reverse_location_count","national_scope_competitors","source_scope_competitors","criteria","diagnostic"]
    sql="""SELECT c.* FROM candidate c LEFT JOIN v5_exact_replay x USING(national_id,source_id) WHERE x.national_id IS NULL AND c.method LIKE 'gps+%'"""
    with gzip.open(out/"gps-pairs.csv.gz","wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for row in db.execute(sql):
            n,s=ns[row["national_id"]],ss[row["source_id"]];loc=s["location_pk"];sid=n["station_id"];d=geo[loc].get(sid)
            detail=json.loads(row["details"])
            if detail["gps_observation"]!="PASS":continue
            total+=1
            if d is None:raise ValueError("Prior GPS observation not reproduced")
            a="BOTH_UNMATCHED" if n["id"] not in vn and s["id"] not in vs else "OCCUPIED"
            if a=="BOTH_UNMATCHED":free+=1
            p=patterns[row["pattern_id"]];c=p["criteria"]
            k=(loc,sid)
            if k not in scopes:
                l=C.Counter();rr=C.Counter()
                for nn in bysite[sid]:
                    for sp in byloc[loc]:
                        if compatible(nn,sp):l[sp["id"]]+=1;rr[nn["id"]]+=1
                scopes[k]=(l,rr)
            l,rr=scopes[k];op="PASS" if (locs[loc]["operator_id"],norm(sites[sid]["operator"])) in approved else "NOT_INDEPENDENTLY_PROVEN"
            diag=[]
            if a!="BOTH_UNMATCHED":diag.append("NO_REASSIGNMENT")
            if len(geo[loc])!=1 or len(reverse[sid])!=1:diag.append("GPS_SITE_NOT_UNIQUE")
            if op!="PASS":diag.append("CPO_PROOF_NOT_ESTABLISHED")
            if l[s["id"]]!=1 or rr[n["id"]]!=1:diag.append("BIDIRECTIONAL_TECHNICAL_SCOPE_NOT_UNIQUE")
            if any(c.get(x)=="FAIL" for x in ("country","operator","plug","current","power")):diag.append("ORIGINAL_CONTRADICTION")
            if not all(c.get(x)=="PASS" for x in ("plug","current","power")):diag.append("POSITIVE_TECHNICAL_PROOF_INCOMPLETE")
            if not s["has_price"]:diag.append("NO_PRICE")
            diag.append("EVSE_IDENTITY_AND_TARIFF_SCOPE_NOT_ESTABLISHED_BY_GPS")
            if a=="BOTH_UNMATCHED":
                stats["FREE"]+=1
                for reason in diag:reasons[reason]+=1
                if l[s["id"]]==rr[n["id"]]==1 and len(geo[loc])==len(reverse[sid])==1 and all(c.get(x)=="PASS" for x in ("plug","current","power")) and c.get("country")!="FAIL" and c.get("operator")!="FAIL" and s["has_price"]:stats["TECHNICAL_SITE_SHORTLIST_NOT_VALIDATED"]+=1
            w.writerow(dict(national_id=n["id"],source_id=s["id"],station_id=sid,location_pk=loc,distance_m=d,allocation=a,pattern_id=row["pattern_id"],decision=row["decision"],original_blockers=j(p["blocking"]),operator_proof=op,gps_site_count=len(geo[loc]),reverse_location_count=len(reverse[sid]),national_scope_competitors=l[s["id"]],source_scope_competitors=rr[n["id"]],criteria=j(c),diagnostic=j(diag)))
    if total!=547654 or free!=519456:raise ValueError("GPS cohort changed: "+str((total,free)))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,referenceValidated=len(valid),locations=len(locs),addressProvenance=dict(counts),addressFieldCoverage=dict(fields),addressRelations=dict(C.Counter(x["relation"] for x in address)),gpsStationDiagnostics=dict(site_stats),gpsStationPairs=len(stations),gpsPairs=total,freeGpsPairs=free,freePairDiagnostics=dict(reasons),shortlist=dict(stats),approvedOperatorPairs=len(approved),newMatches=0,pricesPromoted=0,supplierCalls=0,matchingRulesChanged=False,automaticPublication=False,limitations=["Only archived location-level fields; absence is not proof of upstream API absence","Street prefix is diagnostic only; no address matching rule change","GPS uniqueness and technical compatibility do not prove EVSE identity or tariff scope"])
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"address-gps-report.json").write_text(j(report))
    print("G5_ADDRESS_GPS "+j(report))
if __name__=="__main__":main()
