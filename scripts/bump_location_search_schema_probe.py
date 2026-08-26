#!/usr/bin/env python3
"""Introspect Bump public GraphQL location-search input/output types.

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


def post(query:str, variables:dict[str,Any]|None=None)->dict[str,Any]:
    req=urllib.request.Request(ENDPOINT,data=json.dumps({'query':query,'variables':variables or {}}).encode(),method='POST',headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r:
        return json.load(r)


def unwrap(t:Any)->tuple[str|None,str|None,list[str]]:
    cur=t if isinstance(t,dict) else {}; wrappers=[]
    for _ in range(10):
        k=cur.get('kind'); n=cur.get('name')
        if k in ('NON_NULL','LIST'): wrappers.append(k)
        if n: return k,n,wrappers
        cur=cur.get('ofType') if isinstance(cur.get('ofType'),dict) else {}
    return None,None,wrappers


def inspect(name:str)->dict[str,Any]:
    assert re.fullmatch(r'[_A-Za-z][_0-9A-Za-z]*',name)
    q=f'''query TccType {{ __type(name: "{name}") {{ name kind enumValues {{ name }} inputFields {{ name defaultValue type {{ {TYPE_SHAPE} }} }} fields {{ name type {{ {TYPE_SHAPE} }} args {{ name defaultValue type {{ {TYPE_SHAPE} }} }} }} }} }}'''
    obj=post(q); t=((obj.get('data') or {}).get('__type') or {})
    out={'name':t.get('name'),'kind':t.get('kind'),'enumValues':[x.get('name') for x in (t.get('enumValues') or [])]}
    out['inputFields']=[]
    for f in t.get('inputFields') or []:
        k,n,w=unwrap(f.get('type')); out['inputFields'].append({'name':f.get('name'),'kind':k,'namedType':n,'wrappers':w,'defaultValue':f.get('defaultValue')})
    out['fields']=[]
    for f in t.get('fields') or []:
        k,n,w=unwrap(f.get('type'))
        args=[]
        for a in f.get('args') or []:
            ak,an,aw=unwrap(a.get('type')); args.append({'name':a.get('name'),'kind':ak,'namedType':an,'wrappers':aw,'defaultValue':a.get('defaultValue')})
        out['fields'].append({'name':f.get('name'),'kind':k,'namedType':n,'wrappers':w,'args':args})
    return out


def main():
    roots=[
      'LocationQueryController',
      'LocationSearchInput','LocationSearchInputV2Input','LocationSearchInputV3Input',
      'SearchLocationResult','SearchLocationResultV2','SearchLocationResultV3'
    ]
    types={}; queue=list(roots); seen=set()
    while queue and len(types)<80:
        n=queue.pop(0)
        if n in seen: continue
        seen.add(n)
        t=inspect(n); types[n]=t
        for f in t.get('inputFields') or []:
            if f.get('kind') in ('INPUT_OBJECT','ENUM') and f.get('namedType') not in seen: queue.append(f['namedType'])
        for f in t.get('fields') or []:
            if f.get('kind') in ('OBJECT','INTERFACE','UNION','ENUM') and f.get('namedType') not in seen: queue.append(f['namedType'])
            for a in f.get('args') or []:
                if a.get('kind') in ('INPUT_OBJECT','ENUM') and a.get('namedType') not in seen: queue.append(a['namedType'])
    payload={'schemaVersion':'1.1.0','generatedAt':datetime.now(timezone.utc).isoformat(),'method':{'unauthenticated':True,'introspectionOnly':True,'mutationsSent':False,'personalDataQueried':False},'types':types}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'typeCount':len(types),'v1':types.get('SearchLocationResult'),'v2':types.get('SearchLocationResultV2'),'v3':types.get('SearchLocationResultV3')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
