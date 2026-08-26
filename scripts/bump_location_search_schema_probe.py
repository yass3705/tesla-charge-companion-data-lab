#!/usr/bin/env python3
"""Targeted introspection of Bump public GraphQL location-search v1/v2/v3 schemas.

Unauthenticated schema inspection only. No mutation, account, session or payment data.
"""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT='https://api.bump-charge.com/graphql'
OUT=Path('reports/bump/location_search_schema_latest.json')
UA='TeslaChargeCompanionDataLab/1.0 (public GraphQL location search schema)'
TYPE_SHAPE='kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } }'


def post(query:str)->dict[str,Any]:
    req=urllib.request.Request(ENDPOINT,data=json.dumps({'query':query}).encode(),method='POST',headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)


def unwrap(t:Any)->tuple[str|None,str|None,list[str]]:
    cur=t if isinstance(t,dict) else {}; wrappers=[]
    for _ in range(10):
        k,n=cur.get('kind'),cur.get('name')
        if k in ('NON_NULL','LIST'): wrappers.append(k)
        if n: return k,n,wrappers
        cur=cur.get('ofType') if isinstance(cur.get('ofType'),dict) else {}
    return None,None,wrappers


def inspect(name:str)->dict[str,Any]:
    assert re.fullmatch(r'[_A-Za-z][_0-9A-Za-z]*',name)
    q=f'''query TccType {{ __type(name: "{name}") {{ name kind enumValues {{ name }} inputFields {{ name defaultValue type {{ {TYPE_SHAPE} }} }} fields {{ name type {{ {TYPE_SHAPE} }} args {{ name defaultValue type {{ {TYPE_SHAPE} }} }} }} }} }}'''
    t=((post(q).get('data') or {}).get('__type') or {})
    out={'name':t.get('name'),'kind':t.get('kind'),'enumValues':[x.get('name') for x in (t.get('enumValues') or [])], 'inputFields':[], 'fields':[]}
    for f in t.get('inputFields') or []:
        k,n,w=unwrap(f.get('type')); out['inputFields'].append({'name':f.get('name'),'kind':k,'namedType':n,'wrappers':w,'defaultValue':f.get('defaultValue')})
    for f in t.get('fields') or []:
        k,n,w=unwrap(f.get('type'))
        args=[]
        for a in f.get('args') or []:
            ak,an,aw=unwrap(a.get('type')); args.append({'name':a.get('name'),'kind':ak,'namedType':an,'wrappers':aw,'defaultValue':a.get('defaultValue')})
        out['fields'].append({'name':f.get('name'),'kind':k,'namedType':n,'wrappers':w,'args':args})
    return out


def main():
    roots=['LocationSearchInput','LocationSearchInputV2Input','LocationSearchInputV3Input','SearchLocationResult','SearchLocationResultV2','SearchLocationResultV3']
    types={n:inspect(n) for n in roots}
    # One immediate layer is sufficient to decide whether results expose Location/EVSE/IDs or only map facets.
    immediate=[]
    for n in roots:
        t=types[n]
        for f in t.get('inputFields') or []:
            if f.get('kind') in ('INPUT_OBJECT','ENUM') and f.get('namedType'): immediate.append(f['namedType'])
        for f in t.get('fields') or []:
            if f.get('kind') in ('OBJECT','INTERFACE','UNION','ENUM') and f.get('namedType'): immediate.append(f['namedType'])
    for n in sorted(set(immediate)):
        if n not in types: types[n]=inspect(n)
    payload={'schemaVersion':'1.2.0','generatedAt':datetime.now(timezone.utc).isoformat(),'method':{'unauthenticated':True,'introspectionOnly':True,'mutationsSent':False,'personalDataQueried':False},'types':types}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:types.get(k) for k in ('SearchLocationResult','SearchLocationResultV2','SearchLocationResultV3','LocationSearchInput','LocationSearchInputV2Input')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
