#!/usr/bin/env python3
"""Inspect public German AFIR dynamic feeds before status normalization."""
from __future__ import annotations
import gzip, io, json, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT="https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{offer_id}/file/noauth"
UA="Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"
OFFERS={"eround":"961629419076456448","qwello":"972966368902897664"}
KEY_HINTS=("status","avail","occup","refill","charging","electric","idg","external","identifier","fault","operat")


def fetch(offer_id):
    req=urllib.request.Request(ENDPOINT.format(offer_id=offer_id),headers={"User-Agent":UA,"Accept":"application/json","Accept-Encoding":"gzip"})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read()
        if "gzip" in (r.headers.get("Content-Encoding") or "").lower():
            raw=gzip.decompress(raw)
        return json.loads(raw.decode("utf-8-sig")),len(raw)


def walk(obj,path="$",depth=0,counts=None,examples=None):
    if counts is None: counts=Counter()
    if examples is None: examples=defaultdict(list)
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{path}.{k}"
            lk=k.lower()
            if any(h in lk for h in KEY_HINTS):
                counts[p]+=1
                if len(examples[p])<5:
                    if isinstance(v,(str,int,float,bool)) or v is None:
                        examples[p].append(v)
                    elif isinstance(v,dict):
                        examples[p].append({"type":"object","keys":list(v.keys())[:20]})
                    elif isinstance(v,list):
                        examples[p].append({"type":"list","length":len(v)})
            walk(v,p,depth+1,counts,examples)
    elif isinstance(obj,list):
        for v in obj:
            walk(v,path+"[]",depth+1,counts,examples)
    return counts,examples


def find_relevant_objects(obj,path="$",out=None):
    if out is None: out=[]
    if isinstance(obj,dict):
        keys={k.lower() for k in obj}
        if any("status" in k or "availability" in k for k in keys) and len(out)<12:
            out.append({"path":path,"object":obj})
        for k,v in obj.items(): find_relevant_objects(v,f"{path}.{k}",out)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): find_relevant_objects(v,f"{path}[{i}]",out)
    return out


def main():
    report={"dataset":"germany-afir-dynamic-schema-probe","generatedAt":datetime.now(timezone.utc).isoformat(),"feeds":[]}
    for provider,oid in OFFERS.items():
        data,size=fetch(oid)
        counts,examples=walk(data)
        rel=find_relevant_objects(data)
        feed={
            "provider":provider,"offerId":oid,"uncompressedBytes":size,
            "topType":type(data).__name__,"topKeys":list(data.keys()) if isinstance(data,dict) else None,
            "interestingPaths":[{"path":p,"count":c,"examples":examples[p]} for p,c in counts.most_common(120)],
            "relevantObjects":rel,
        }
        report["feeds"].append(feed)
        print("TCC_AFIR_DYNAMIC_PROFILE="+json.dumps({"provider":provider,"offerId":oid,"uncompressedBytes":size,"relevantObjects":len(rel)},sort_keys=True))
        for x in rel[:4]:
            print("TCC_AFIR_DYNAMIC_EXAMPLE="+json.dumps({"provider":provider,"path":x["path"],"object":x["object"]},ensure_ascii=False,sort_keys=True)[:12000])
        print("TCC_AFIR_DYNAMIC_PATHS="+json.dumps({"provider":provider,"paths":[{"path":p,"count":c,"examples":examples[p]} for p,c in counts.most_common(40)]},ensure_ascii=False,sort_keys=True)[:18000])
    p=Path("data/germany/afir_dynamic_schema_probe.json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__": main()
