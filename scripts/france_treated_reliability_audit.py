#!/usr/bin/env python3
"""France treated/released-slot reliability audit.

Static, fail-closed audit. It never promotes tariffs or mutates canonical counters.
It inventories:
- treated authorities and contradictory status artifacts;
- positive residual/missing/error tariff metrics in direct evidence;
- V9 France tariff-source registry paths that do not materialize in the repo;
- the 74 historical slots currently carried as active even though all are RELEASED_*.
"""
from __future__ import annotations
import json,re,unicodedata
from pathlib import Path
from datetime import datetime,timezone
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
CANON=ROOT/"docs/france-cpo-progress-2026-09.json"
REG=ROOT/"v9-production-runtime/data/v9/source-registry.json"
OUT=ROOT/"reports/france/cpo-treated-reliability-audit-latest.json"

def load(p:Path):
    return json.loads(p.read_text(encoding="utf-8"))

def norm(s:str)->str:
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower()
    s=re.sub(r"\b(fr|sas|gmbh|france|sarl)\b"," ",s)
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def walk(obj:Any,path=""):
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{path}.{k}" if path else str(k)
            yield p,k,v
            yield from walk(v,p)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            yield from walk(v,f"{path}[{i}]")

canon=load(CANON)
treated=[str(x) for x in canon.get("treatedNominative",[])]
treated_norm=[(x,norm(x)) for x in treated]

# Explicitly released historical slots.
slots=[str(x) for x in canon.get("activeNominative",[])]
def slot_bucket(s):
    if "SETASIDE_EXACT_IDENTITY" in s: return "identityAlreadySetAside"
    if "TREATED_HISTORICALLY_PROVEN" in s: return "historicallyTreated"
    if re.search(r"\\blineage\\b",s,re.I): return "lineage"
    if re.search(r"\balias\b",s,re.I): return "alias"
    if re.search(r"authority .*already treated",s,re.I): return "authorityAlreadyTreated"
    return "unclassified"
slot_counts={}
for s in slots: slot_counts[slot_bucket(s)]=slot_counts.get(slot_bucket(s),0)+1

# Evidence files: intentionally bounded to France/direct evidence, avoid arbitrary docs prose.
files=[]
for base,patterns in [
    (ROOT/"data/operator_direct",["*.json"]),
    (ROOT/"reports/france",["**/*.json"]),
    (ROOT/"data/reports",["*.json"]),
    (ROOT/"v9-production-runtime/data/v9",["france-*.json"]),
]:
    if base.exists():
        for pat in patterns: files.extend(base.glob(pat))
files=sorted(set(p for p in files if p.is_file() and p.stat().st_size<=8_000_000))

contradictions=[]
coverage_gaps=[]
evidence_index=[]
bad_status_keys={"blocked","setaside"}
gap_re=re.compile(r"(unpriced|missing|notpublished|not_published|not published|notariff|no_tariff|residual|unresolved|persistenterrors|errorspersistantes|failed|failure|mismatch)",re.I)
ignore_gap_re=re.compile(r"(missingvaluesbyfield|examples|samples|historical|source)",re.I)

for p in files:
    try: x=load(p)
    except Exception: continue
    op=None
    if isinstance(x,dict):
        for key in ("operator","network","authority","cpo"):
            if isinstance(x.get(key),str): op=x[key]; break
    opn=norm(op or "")
    matches=[]
    if opn:
        for t,tn in treated_norm:
            if opn==tn or (len(opn)>=5 and (opn in tn or tn in opn)):
                matches.append(t)
    rel=str(p.relative_to(ROOT))
    source_type=""
    if isinstance(x,dict) and isinstance(x.get("classification"),dict):
        source_type=str(x["classification"].get("sourceType") or "")
    third_party_probe="third_party" in source_type.lower() or "third-party" in source_type.lower()
    if matches and not third_party_probe:
        evidence_index.append({"path":rel,"operator":op,"treatedMatches":matches[:5]})
    # Status contradictions only from direct/first-party evidence.
    if matches and isinstance(x,dict) and not third_party_probe:
        cls=x.get("classification")
        if isinstance(cls,dict):
            flags={k:v for k,v in cls.items() if k.lower() in ("treated","blocked","setaside","failclosed")}
            if flags.get("treated") is False or flags.get("blocked") is True or flags.get("setAside") is True or flags.get("setaside") is True:
                contradictions.append({"path":rel,"operator":op,"treatedMatches":matches[:5],"classification":flags,
                                       "reason":cls.get("reason")})
    # Positive numeric gap metrics; ignore historical third-party probes and non-France artifacts.
    country=str(x.get("country") or "") if isinstance(x,dict) else ""
    if third_party_probe or (country and country.upper() not in ("FR","FRA","FRANCE")):
        continue
    for full,k,v in walk(x):
        if not gap_re.search(str(k)) or ignore_gap_re.search(full): continue
        positive=False
        if isinstance(v,(int,float)) and not isinstance(v,bool): positive=v>0
        elif isinstance(v,list): positive=len(v)>0
        elif isinstance(v,dict): positive=len(v)>0
        if positive:
            coverage_gaps.append({"path":rel,"operator":op,"treatedMatches":matches[:5],"metric":full,"value":v if not isinstance(v,(list,dict)) else len(v)})

# De-duplicate gap rows and cap noisy files per metric.
seen=set(); cg=[]
for g in coverage_gaps:
    key=(g["path"],g["metric"],str(g["value"]))
    if key in seen: continue
    seen.add(key); cg.append(g)
coverage_gaps=cg

# Runtime France tariff sources: check whether declared file exists either from repo root
# or relative to v9-production-runtime (registry paths are runtime-root relative in some entries).
registry_issues=[]
registry_sources=[]
if REG.exists():
    reg=load(REG)
    for s in reg.get("sources",[]):
        if "FR" not in (s.get("countries") or []) or s.get("active") is False or "tariff" not in (s.get("capabilities") or []): continue
        path=s.get("path")
        exists=None; candidates=[]
        if path:
            candidates=[ROOT/path,ROOT/"v9-production-runtime"/path]
            exists=any(c.exists() for c in candidates)
        row={"id":s.get("id"),"label":s.get("label"),"path":path,"exists":exists,
             "operatorIds":s.get("operatorIds",[]),"refresh":s.get("refresh")}
        registry_sources.append(row)
        if path and not exists: registry_issues.append(row)

# Known high-value exact coverage metrics from current canonical/runtime artifacts.
known=[]
def add(path,label,metrics):
    p=ROOT/path
    if p.exists():
        try:
            x=load(p); known.append({"label":label,"path":path,"metrics":metrics(x)})
        except Exception as e: known.append({"label":label,"path":path,"error":str(e)})
add("reports/france/qwello/public-evse-tariff-audit-latest.json","Qwello FR*QWC",
    lambda x:{"requested":x.get("requestedFrQwcEvseIds"),"priced":x.get("pricedEvseIds"),"unpriced":x.get("unpricedRecoveredEvseIds"),"failed":x.get("failedEvseIds"),"complete":x.get("coverageComplete")})
add("v9-production-runtime/data/v9/france-loadmotion-offers.json","Load Motion family",
    lambda x:{"generatedAt":x.get("generatedAt"),"sourceEvidence":x.get("sourceEvidence")})
add("data/reports/bump_direct_tariffs_report.json","Bump",
    lambda x:x.get("counts"))
add("data/reports/waat_qualicharge_direct_tariffs_report.json","WAAT QualiCharge",
    lambda x:x.get("counts"))
add("reports/france/reveo/national-exact-coverage.json","REVEO",
    lambda x:{"connectors":x.get("connectorCount"),"priced":x.get("exactActiveTariffConnectorCount"),"missing":x.get("missingTariffConnectorCount"),"coverage":x.get("coverage")})

report={
 "schemaVersion":1,"country":"FR","generatedAt":datetime.now(timezone.utc).isoformat(),
 "type":"treated-and-released-slot-reliability-audit",
 "canonical":{"blobAccounting":{"treated":canon.get("treatedCpos"),"setAside":canon.get("setAsideCpos"),"active":canon.get("activeRemainingCpos"),"total":canon.get("totalCpos")},
              "latestBatch":canon.get("latestBatch"),"businessUnresolvedAuthorities":canon.get("businessUnresolvedAuthorities",0),
              "pendingDedupeCount":len(canon.get("pendingDedupe",[]))},
 "releasedHistoricalSlots":{"count":len(slots),"allReleasedMarkers":all(s.startswith("RELEASED_") for s in slots),
                            "classificationByMarker":slot_counts,"unclassified":[s for s in slots if slot_bucket(s)=="unclassified"]},
 "treatedAuthorities":{"count":len(treated),"statusContradictions":contradictions,
                       "candidateCoverageGapMetrics":coverage_gaps,
                       "evidenceFilesMatched":len(evidence_index)},
 "runtimeFranceTariffSources":{"count":len(registry_sources),"missingDeclaredPaths":registry_issues,"sources":registry_sources},
 "knownCoverageChecks":known,
 "decision":{
   "businessBacklogFromCurrentActiveSlots":0 if all(s.startswith("RELEASED_") for s in slots) else None,
   "safeToRetireActiveAsBusinessCategory":all(s.startswith("RELEASED_") for s in slots) and not [s for s in slots if slot_bucket(s)=="unclassified"],
   "treatedDoesNotMean100PercentPriced":True,
   "gapPolicy":"Keep unresolved EVSE fail-closed; direct CPO exact tariff -> Electra -> Electroverse -> unpriced. Never extrapolate to close a metric."
 }
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"released":report["releasedHistoricalSlots"],"contradictions":len(contradictions),"gapMetrics":len(coverage_gaps),
                  "runtimeMissingPaths":len(registry_issues),"safeToRetireActive":report["decision"]["safeToRetireActiveAsBusinessCategory"]},ensure_ascii=False,indent=2))
