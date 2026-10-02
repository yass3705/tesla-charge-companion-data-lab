#!/usr/bin/env python3
import gzip,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"data/national/germany_non_tesla_catalog_staging_direct_cpo.json.gz"
OUT=ROOT/"reports/germany/public-access-schema-probe.json"
with gzip.open(SRC,"rt",encoding="utf-8") as f:
    data=json.load(f)
def lists(x,path="$",out=None):
    out=[] if out is None else out
    if isinstance(x,list):
        if x and isinstance(x[0],dict): out.append((len(x),path,x))
        for i,v in enumerate(x[:3]): lists(v,path+"["+str(i)+"]",out)
    elif isinstance(x,dict):
        for k,v in x.items(): lists(v,path+"."+k,out)
    return out
cands=sorted(lists(data),reverse=True,key=lambda z:z[0])
n,path,rows=cands[0]
fields=Counter()
examples={}
terms=["nicht öffentlich","nicht oeffentlich","privat","mitarbeiter","personal","kunden","gäste","gaeste","bewohner","mieter","fuhrpark","schranke"]
hits=Counter()
samples={t:[] for t in terms}
for row in rows:
    flat=[]
    def rec(x,p=""):
        if isinstance(x,dict):
            for k,v in x.items(): rec(v,p+"."+k if p else k)
        elif isinstance(x,list):
            for v in x: rec(v,p)
        elif x is not None:
            s=str(x); flat.append((p,s)); fields[p]+=1
            examples.setdefault(p,[])
            if len(examples[p])<3 and s not in examples[p]: examples[p].append(s)
    rec(row)
    text=" | ".join(v for _,v in flat).lower()
    for term in terms:
        if term in text:
            hits[term]+=1
            if len(samples[term])<10: samples[term].append({p:v for p,v in flat if any(q in p.lower() for q in ["name","address","operator","access","id","city","street"])})
report={"schemaVersion":"1.0.0","dataset":"germany-public-access-schema-probe","source":str(SRC.relative_to(ROOT)),"policy":{"nonDestructive":True,"automaticProductionExclusion":False},"selectedCollection":{"path":path,"rows":n},"topLists":[{"rows":a,"path":b} for a,b,_ in cands[:15]],"fields":[{"path":k,"rowsPresent":v,"examples":examples[k]} for k,v in fields.most_common()],"termCounts":dict(hits),"termSamples":samples}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"rows":n,"path":path,"termCounts":dict(hits)},ensure_ascii=False))
