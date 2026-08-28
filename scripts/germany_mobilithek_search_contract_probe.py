#!/usr/bin/env python3
"""Probe targeted Mobilithek offer-search payload fields for AFIR providers."""
from __future__ import annotations
import json, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

URL="https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search?page=0&size=100"
UA="Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"


def post(payload):
    req=urllib.request.Request(URL,data=json.dumps(payload).encode(),method="POST",headers={"User-Agent":UA,"Accept":"application/json","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return r.status,json.loads(r.read(8_000_000).decode("utf-8-sig")),None
    except urllib.error.HTTPError as e:
        return e.code,None,e.read(20000).decode(errors="replace")
    except Exception as e:
        return None,None,repr(e)


def offers(obj):
    out=[]; seen=set()
    def walk(x):
        if isinstance(x,dict):
            if "publicationId" in x and "title" in x:
                k=str(x["publicationId"])
                if k not in seen:
                    seen.add(k); out.append({"id":k,"title":x.get("title"),"description":x.get("description"),"publisher":((x.get("agents") or {}).get("publisher") or {}).get("name")})
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(obj); return out


def main():
    tests=[]
    fields=("searchTerm","search","query","text","term")
    terms=("chargecloud","eRound","Qwello","AFIR-recharging-dyn-chargecloud-json","AFIR-recharging-dyn-eRound")
    for term in terms:
        for field in fields:
            payload={field:term}
            status,data,error=post(payload)
            rows=offers(data) if data is not None else []
            hit=[r for r in rows if term.lower() in json.dumps(r,ensure_ascii=False).lower() or ("afir-recharging-dyn" in str(r.get("title","")).lower())]
            tests.append({"term":term,"field":field,"status":status,"error":error,"offerCount":len(rows),"hits":hit[:30]})
            if hit:
                print("TCC_MOBILITHEK_SEARCH_HIT="+json.dumps({"term":term,"field":field,"hits":hit[:30]},ensure_ascii=False,sort_keys=True))
                break
    out={"dataset":"germany-mobilithek-search-contract-probe","generatedAt":datetime.now(timezone.utc).isoformat(),"tests":tests}
    p=Path("data/germany/mobilithek_search_contract_probe.json"); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    if not any(t["hits"] for t in tests):
        raise SystemExit("no targeted search payload produced a relevant hit")

if __name__=="__main__": main()
