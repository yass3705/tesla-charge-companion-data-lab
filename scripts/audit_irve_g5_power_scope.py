#!/usr/bin/env python3
"""Audit nominal PDC vs individual socket scope; no matching or catalog changes."""
import collections
import csv
import gzip
import hashlib
import json
import math
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import zipfile
from scripts.france.build_france_irve_static_v9 import key, get, number, enabled, supported_connectors, coordinates
from scripts.audit_electroverse_g5_real_matching import plug

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""): h.update(block)
    return h.hexdigest()

def verify(path, expected):
    if digest(path)!=expected: raise ValueError("Digest mismatch: "+path.name)

def download(root, spec, wanted):
    repo=os.environ["GITHUB_REPOSITORY"]
    def api(path):
        return json.loads(subprocess.check_output(["gh","api",f"repos/{repo}/{path}"]))
    run=api(f"actions/runs/{spec['run']}")
    art=api(f"actions/artifacts/{spec['artifact']}")
    if (run["status"]!="completed" or run["conclusion"]!="success" or run["head_sha"]!=spec["codeSha"]
        or run["head_branch"]!="rebuild/v9-20261020" or art["expired"] or art["name"]!=spec["name"]
        or art["digest"]!="sha256:"+spec["zipSha256"] or art["workflow_run"]["id"]!=spec["run"]):
        raise ValueError("Unverified source artifact")
    root.mkdir()
    z=root/"input.zip"
    with z.open("wb") as f:
        subprocess.run(["gh","api",f"repos/{repo}/actions/artifacts/{spec['artifact']}/zip"],stdout=f,check=True)
    verify(z,spec["zipSha256"])
    found={}
    with zipfile.ZipFile(z) as archive:
        for info in archive.infolist():
            p=pathlib.PurePosixPath(info.filename)
            if p.is_absolute() or ".." in p.parts or stat.S_IFMT(info.external_attr>>16)==stat.S_IFLNK:
                raise ValueError("Unsafe ZIP entry")
            if info.is_dir(): continue
            for name,suffix in wanted.items():
                if tuple(p.parts[-len(suffix):])==suffix:
                    if name in found: raise ValueError("Duplicate wanted ZIP entry")
                    dest=root/name
                    with archive.open(info) as src,dest.open("wb") as dst: shutil.copyfileobj(src,dst)
                    found[name]=dest
    if set(found)!=set(wanted): raise ValueError("Missing source entries: "+str(set(wanted)-set(found)))
    return found

def raw_power(row):
    return number(get(row,"puissance_nominale","puissance"))

def projected_power(row):
    v=raw_power(row)
    return round(0.0 if v is None else v/1000 if v>1000 else v,1)

def scope(flags, powers):
    if len(powers)!=1 or None in powers or any(p<=0 for p in powers if p is not None):
        return "PDC_NOMINAL_MISSING_OR_CONFLICTING"
    if len(flags)>1: return "MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN"
    if len(flags)==1: return "SINGLE_DECLARED_TYPE_NOMINAL_ONLY"
    return "TYPE_SCOPE_UNKNOWN"

def classify(row, kind):
    c=json.loads(row["criteria_json"])
    if c["power"]!="FAIL": return "NO_POWER_FAILURE"
    if c["plug"]!="PASS" or c["current"]!="PASS": return "OTHER_TECHNICAL_CONTRADICTION"
    if kind=="PDC_NOMINAL_MISSING_OR_CONFLICTING": return "NOMINAL_MISSING_OR_CONFLICTING_REVIEW"
    n=float(row["national_kw"]); s=float(row["source_kw"])
    if kind=="MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN":
        return "MULTITYPE_SOURCE_ABOVE_NOMINAL_REVIEW" if s>n else "MULTITYPE_SOURCE_BELOW_NOMINAL_REVIEW"
    if row["national_mode"]=="AC" and abs(n-s)<=1:
        return "AC_SMALL_DELTA_REVIEW_NOT_TOLERANCE"
    if row["national_mode"]=="DC": return "DC_DELTA_REVIEW"
    return "OTHER_POWER_DELTA_REVIEW"

def gzjson(path):
    with gzip.open(path,"rt",encoding="utf-8") as f: return json.load(f)

def write_csv(path, rows, fields):
    with gzip.open(path,"wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_irve_power_scope_audit_only" or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:
        raise ValueError("Wrong audit scope")
    root=pathlib.Path(sys.argv[2])
    root.mkdir()
    national=download(root/"national",pin["national"],{
        "static.csv":("raw","france-irve","static.csv"),
        "all.json.gz":("data","national","france-irve-static-v9","all.json.gz"),
        "dynamic.json.gz":("data","national","france-irve-dynamic-status-v9.json.gz"),
        "refresh.json":("irve-refresh-summary.json",)})
    exact=download(root/"exact",pin["exact"],{"pairs.csv.gz":("exact-pairs.csv.gz",),"report.json":("exact-mismatch-report.json",)})
    for name,expected in [("static.csv","rawSha256"),("all.json.gz","allSha256"),("dynamic.json.gz","dynamicSha256")]:
        verify(national[name],pin[expected])
    verify(exact["pairs.csv.gz"],pin["exactPairsSha256"])
    refresh=json.loads(national["refresh.json"].read_text())
    report=json.loads(exact["report.json"].read_text())
    if report["sourcePin"]["nationalArtifact"]!=pin["national"]["artifact"] or report["exportSha256"]["exact-pairs.csv.gz"]!=pin["exactPairsSha256"]:
        raise ValueError("Exact audit provenance mismatch")
    active=set(gzjson(national["dynamic.json.gz"])["enServicePdcIds"])
    if len(active)!=refresh["activeEvse"] or len(active)!=101856: raise ValueError("Active scope mismatch")
    projection=set()
    for st in gzjson(national["all.json.gz"]):
        for group in st[8]:
            for evse in group[6]:
                if evse in active: projection.add((st[0],evse,plug(group[1]),float(group[3])))
    if len(projection)!=refresh["activeConnectorProfiles"] or len(projection)!=124918:
        raise ValueError("Profile scope mismatch")
    if {x[1] for x in projection}!=active: raise ValueError("Active identity mismatch")
    raw=collections.defaultdict(lambda:{"flags":set(),"powers":set(),"raw_values":set(),"rows":0})
    rebuilt=set()
    with national["static.csv"].open(encoding="utf-8-sig",errors="replace",newline="") as f:
        sample=f.read(65536);f.seek(0)
        try: dialect=csv.Sniffer().sniff(sample,delimiters=",;\t|")
        except csv.Error: dialect=csv.excel
        reader=csv.DictReader(f,dialect=dialect)
        headers=reader.fieldnames or []
        flag_keys={key(x) for x in headers if key(x).startswith("prisetype") or key(x)=="priseautre"}
        if not {"prisetypeef","prisetype2","prisetypecomboccs"}.issubset(flag_keys):
            raise ValueError("Missing expected connector flags")
        for rr in reader:
            row={key(k):v for k,v in rr.items() if k}
            evse=get(row,"id_pdc_itinerance")
            if evse not in active: continue
            sid=get(row,"id_station_itinerance","id_station_local") or evse
            rec=raw[(sid,evse)]
            rec["rows"]+=1
            rec["flags"].update(k for k in flag_keys if enabled(row.get(k)))
            rec["powers"].add(raw_power(row))
            rec["raw_values"].add(get(row,"puissance_nominale","puissance"))
            if coordinates(row) is None: continue
            for label in supported_connectors(row):
                rebuilt.add((sid,evse,plug(label),projected_power(row)))
    if projection!=rebuilt: raise ValueError("Raw vs projected active profiles differ: "+str((len(projection-rebuilt),len(rebuilt-projection))))
    scope_counts=collections.Counter()
    prof_counts=collections.Counter()
    national_rows=[]
    for sid,evse in sorted({(x[0],x[1]) for x in projection}):
        rec=raw[(sid,evse)]
        kind=scope(rec["flags"],rec["powers"])
        scope_counts[kind]+=1
        national_rows.append({"station_id":sid,"evse_id":evse,"raw_rows":rec["rows"],"declared_type_flags":json.dumps(sorted(rec["flags"])),"nominal_raw_values":json.dumps(sorted(rec["raw_values"])),"scope":kind})
    for sid,evse,_,_ in projection:
        rec=raw[(sid,evse)]
        prof_counts[scope(rec["flags"],rec["powers"])]+=1
    counts=collections.Counter(); previous=collections.Counter(); power_fails=0; pairs=[]; by_op=collections.Counter()
    with gzip.open(exact["pairs.csv.gz"],"rt",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            k=(row["station_id"],row["evse_id"])
            if (*k,row["national_plug"],float(row["national_kw"])) not in projection:
                raise ValueError("Exact row not in active projection")
            rec=raw[k];kind=scope(rec["flags"],rec["powers"])
            label=classify(row,kind);counts[label]+=1;previous[row["decision"]]+=1
            c=json.loads(row["criteria_json"])
            power_fails+=c["power"]=="FAIL"
            other=[k for k,v in c.items() if v=="FAIL" and k!="power"]
            by_op[(row["national_operator"],label)]+=1
            pairs.append({**row,"power_scope":kind,"scope_diagnostic":label,"declared_type_flags":json.dumps(sorted(rec["flags"])),"nominal_raw_values":json.dumps(sorted(rec["raw_values"])),"other_failed_criteria":json.dumps(other)})
    if len(pairs)!=21980 or dict(previous)!=report["exactPairDispositions"] or power_fails!=8877:
        raise ValueError("Exact cohort reconciliation failed")
    out=root/"results";out.mkdir()
    write_csv(out/"active-pdc-power-scope.csv.gz",national_rows,list(national_rows[0]))
    write_csv(out/"exact-pair-power-scope.csv.gz",pairs,list(pairs[0]))
    summary={"sourcePin":pin,"rawHeaders":headers,"declaredTypeFields":sorted(flag_keys),"activeEvse":len(active),"activeProfiles":len(projection),"rawProjectionReconciled":True,"activeEvseScope":dict(scope_counts),"activeProfileScope":dict(prof_counts),"exactPairs":len(pairs),"oldDecisions":dict(previous),"powerFailures":power_fails,"pairDiagnostics":dict(counts),"byOperator":[{"operator":k[0],"diagnostic":k[1],"count":v} for k,v in by_op.most_common()],"newMatches":0,"matchingRulesChanged":False,"supplierCalls":0,"automaticPublication":False}
    summary["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"power-scope-report.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    print("G5_POWER_SCOPE_AUDIT "+json.dumps({k:v for k,v in summary.items() if k not in ("sourcePin","byOperator")},ensure_ascii=False,sort_keys=True))
    print("G5_POWER_SCOPE_TOP_OPERATORS "+json.dumps(summary["byOperator"][:30],ensure_ascii=False))

if __name__=="__main__": main()
