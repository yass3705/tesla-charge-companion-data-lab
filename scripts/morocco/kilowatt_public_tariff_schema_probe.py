#!/usr/bin/env python3
from __future__ import annotations
import json, ssl
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

URL='https://kilowatt.ma/api/charging-stations'
OUT=Path('reports/morocco/kilowatt/latest-public-tariff-schema.json')
UA='Mozilla/5.0 (compatible; TCC-DataLab-PublicReadOnly/1.0)'
TOKENS=('tariff','price','cost','fee','free','payment','rate','amount','currency')

def get_json(url):
    req=Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    with urlopen(req,timeout=25,context=ssl.create_default_context()) as r:
        return json.loads(r.read(8_000_000).decode('utf-8'))

def walk(obj,path='$',paths=None,types=None):
    paths=paths if paths is not None else Counter()
    types=types if types is not None else {}
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f'{path}.{k}'
            paths[p]+=1
            types.setdefault(p,type(v).__name__)
            walk(v,p,paths,types)
    elif isinstance(obj,list):
        for v in obj:
            walk(v,path+'[]',paths,types)
    return paths,types

def main():
    raw=get_json(URL)
    paths,types=walk(raw)
    matched=[]
    for p,n in sorted(paths.items()):
        low=p.lower()
        if any(t in low for t in TOKENS):
            matched.append({'path':p,'occurrences':n,'value_type':types.get(p)})
    top=Counter(); conn=Counter()
    for row in raw if isinstance(raw,list) else []:
        if not isinstance(row,dict): continue
        top.update(row.keys())
        for c in row.get('connectors') or []:
            if isinstance(c,dict): conn.update(c.keys())
    rep={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'source':URL,
      'policy':{'read_only':True,'public_get_only':True,'no_login':True,'no_mutations':True,'raw_response_not_persisted':True,'values_not_persisted':True},
      'summary':{'station_records':len(raw) if isinstance(raw,list) else None,'tariff_like_path_count':len(matched),'tariff_like_paths':matched},
      'station_field_names':sorted(top.keys()),'connector_field_names':sorted(conn.keys()),
      'modeling_note':'Schema-only diagnostic. Presence/absence of tariff-like fields does not alter CPO, site_brand, app_source/access_network, tariff_channel or status_source without explicit evidence.'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(rep['summary'],indent=2,ensure_ascii=False))

if __name__=='__main__': main()
