#!/usr/bin/env python3
import json,re
from pathlib import Path
from collections import Counter,defaultdict

ROOT=Path(".")
DATA=ROOT/"data"/"operator_direct"
WORKFLOWS=ROOT/".github"/"workflows"

PRICE_KEY=re.compile(r"(price|tariff|rate|fee|gbp|eur|chf|dh|mad|kwh|minute|hour)",re.I)
SOURCE_KEY=re.compile(r"(source|url|website|page|endpoint)",re.I)
TIME_KEY=re.compile(r"(retrievedat|updatedat|effectivefrom|effectiveto|validfrom|validto|date)",re.I)
STATIC_NAME=re.compile(r"(official|tariff_rules|pricing_rules|pricing|tariff)",re.I)

workflow_text={}
for p in WORKFLOWS.glob("*.y*ml"):
    try: workflow_text[str(p)]=p.read_text(errors="ignore")
    except Exception: pass

def walk(obj,path="",stats=None):
    if stats is None:
        stats={"priceKeys":set(),"sourceValues":[],"timeKeys":set(),"numericPriceLike":0}
    if isinstance(obj,dict):
        for k,v in obj.items():
            kp=f"{path}.{k}" if path else str(k)
            if PRICE_KEY.search(str(k)):
                stats["priceKeys"].add(kp)
                if isinstance(v,(int,float)) and not isinstance(v,bool):
                    stats["numericPriceLike"]+=1
            if SOURCE_KEY.search(str(k)) and isinstance(v,str) and (v.startswith("http://") or v.startswith("https://")):
                stats["sourceValues"].append(v)
            if TIME_KEY.search(str(k)):
                stats["timeKeys"].add(kp)
            walk(v,kp,stats)
    elif isinstance(obj,list):
        for i,v in enumerate(obj[:5000]):
            walk(v,f"{path}[]",stats)
    return stats

rows=[]
for p in sorted(DATA.glob("*.json")):
    try:
        raw=p.read_text(errors="ignore")
        data=json.loads(raw)
    except Exception:
        continue
    # Exclude station-specific / dynamic pricing artifacts from the fixed-tariff audit.
    source_type=str(data.get("sourceType") or "") if isinstance(data,dict) else ""
    pricing_model=str(data.get("pricingModel") or "") if isinstance(data,dict) else ""
    if source_type=="official_public_station_exact_pricing" or "site_specific" in pricing_model.lower():
        continue
    stats=walk(data)
    # Conservative candidate: tariff/pricing-ish filename OR >=2 price-like fields,
    # and at least one numeric value under a price-like key.
    candidate=(STATIC_NAME.search(p.name) is not None or len(stats["priceKeys"])>=2) and stats["numericPriceLike"]>0
    if not candidate:
        continue
    rel=str(p)
    refs=[wf for wf,txt in workflow_text.items() if rel in txt or p.name in txt]
    # A source is refresh-managed only if some workflow other than this audit references it.
    managed=bool(refs)
    country=None
    if isinstance(data,dict):
        country=data.get("country") or data.get("countryCode") or data.get("market")
    if not country:
        n=p.stem.lower()
        for token,cc in [
            ("france","FR"),("uk","GB"),("belgium","BE"),("spain","ES"),
            ("italy","IT"),("germany","DE"),("switzerland","CH"),("morocco","MA"),
            ("netherlands","NL"),("portugal","PT"),("luxembourg","LU")
        ]:
            if token in n:
                country=cc; break
    rows.append({
        "path":rel,
        "country":country,
        "bytes":p.stat().st_size,
        "priceLikeKeyCount":len(stats["priceKeys"]),
        "numericPriceLikeCount":stats["numericPriceLike"],
        "hasSourceUrl":bool(stats["sourceValues"]),
        "sourceUrlSamples":stats["sourceValues"][:5],
        "hasFreshnessMetadata":bool(stats["timeKeys"]),
        "workflowManaged":managed,
        "workflowRefs":refs[:10],
        "risk":"managed" if managed else ("high_static_unmanaged" if stats["sourceValues"] else "high_unmanaged_no_source")
    })

summary=Counter(r["risk"] for r in rows)
by_country=defaultdict(Counter)
for r in rows:
    by_country[str(r["country"] or "UNKNOWN")][r["risk"]]+=1

out={
    "schemaVersion":1,
    "policy":{
        "rule":"Fixed/direct CPO tariffs must not be hard-coded as timeless values. Each tariff source must have a refresh path, provenance, freshness metadata, history, and fail-safe behavior preserving the last validated value on parser/source failure.",
        "scope":"all countries / data/operator_direct/*.json",
        "managedDefinition":"at least one GitHub Actions workflow references the tariff file path or filename",
        "note":"This is a conservative static audit. Unmanaged candidates require review; managed files can still need semantic refresh validation."
    },
    "candidateCount":len(rows),
    "riskCounts":dict(summary),
    "byCountry":{k:dict(v) for k,v in sorted(by_country.items())},
    "unmanaged":[r for r in rows if not r["workflowManaged"]],
    "managed":[r for r in rows if r["workflowManaged"]]
}
Path("reports/fixed-tariff-refresh-audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({
    "candidateCount":out["candidateCount"],
    "riskCounts":out["riskCounts"],
    "byCountry":out["byCountry"],
    "unmanagedTop":[{"path":r["path"],"country":r["country"],"risk":r["risk"]} for r in out["unmanaged"][:50]]
},ensure_ascii=False,indent=2))
