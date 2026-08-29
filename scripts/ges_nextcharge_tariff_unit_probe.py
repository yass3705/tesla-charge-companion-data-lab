#!/usr/bin/env python3
"""Extract public NextCharge display labels that document tariff component units.

Static CDN assets only; no application API, login, payment or charging calls.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
import requests

LANG="https://nextchargeapp-542e.kxcdn.com/map//assets/languages/it.json"
BUNDLES=[
 "https://nextchargeapp-542e.kxcdn.com/map/main.a22e183819ebbdfc.js",
 "https://nextchargeapp-542e.kxcdn.com/map/5121.b6a40f76497e5a07.js",
]
OUT=Path("data/reports/ges_nextcharge_tariff_unit_probe.json")
MATCH=re.compile(r"(tariff|tariffa|price|prezzo|energy|energia|time|tempo|parking|sosta|session|sessione|kwh|kw/h|/min|minuto|minute|€|eur)",re.I)
UNIT=re.compile(r".{0,100}(?:€/\s*kwh|eur\s*/\s*kwh|/\s*kwh|€/\s*min|eur\s*/\s*min|/\s*min|kwh|minute|minuto).{0,140}",re.I)

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def walk(x,path=""):
    if isinstance(x,dict):
        for k,v in x.items():yield from walk(v,f"{path}.{k}" if path else str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x):yield from walk(v,f"{path}[{i}]")
    else:yield path,x

def main():
    s=requests.Session();s.headers['User-Agent']='Mozilla/5.0 Chrome/140 Safari/537.36'
    report={"generatedAt":now(),"security":{"staticPublicAssetsOnly":True,"applicationApiCalled":False,"accountCredentialsUsed":False},"language":{},"bundleUnitContexts":[]}
    r=s.get(LANG,timeout=30);r.raise_for_status();data=r.json();hits=[]
    for path,val in walk(data):
        text=f"{path} {val}"
        if MATCH.search(text):hits.append({"path":path,"value":str(val)[:500]})
    report['language']={"url":LANG,"status":r.status_code,"matchedEntries":hits[:500]}
    contexts=set()
    for url in BUNDLES:
        x=s.get(url,timeout=30);x.raise_for_status();text=x.text
        for m in UNIT.finditer(text):
            frag=m.group(0).replace('\n',' ').replace('\r',' ')
            if len(frag)<=400:contexts.add(frag)
    report['bundleUnitContexts']=sorted(contexts)[:300]
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({"matchedLanguageEntries":len(hits),"languageHits":hits[:150],"bundleUnitContexts":report['bundleUnitContexts'][:150]},ensure_ascii=False,indent=2)[:100000])
if __name__=='__main__':main()
