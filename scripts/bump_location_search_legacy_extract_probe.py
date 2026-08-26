#!/usr/bin/env python3
"""Compare Bump public GraphQL location search v1/v2 technical payloads.

Unauthenticated read-only search only; safe field selection is schema-derived and limited to
station/EVSE/operator/tariff/map identifiers. No account, session or payment data is queried.
"""
from __future__ import annotations
import json, re, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_location_search_runtime_probe import sample

ENDPOINT='https://api.bump-charge.com/graphql'
OUT=Path('reports/bump/location_search_legacy_extract_latest.json')
UA='TeslaChargeCompanionDataLab/1.0 (public Bump legacy map extraction)'
TYPE_SHAPE='kind name ofType { kind name ofType { kind name ofType { kind name } } }'
SAFE=re.compile(r'^(?:id|identifier|hash|name|status|isRoaming|maxPower|power|latitude|longitude|tariffGroup|operator|operators|location|locations|evse|evses|allEvses|coordinates|connectorTypes|connectors|chargeType|items|results|data|points|markers|clusters|total|count|priceScoring|currency|price|tariff)$',re.I)


def post(q:str,v:dict[str,Any]|None=None)->tuple[int|str,dict[str,Any]]:
    req=urllib.request.Request(ENDPOINT,data=json.dumps({'query':q,'variables':v or {}}).encode(),method='POST',headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            o=json.load(r); return int(r.status),o if isinstance(o,dict) else {}
    except urllib.error.HTTPError as e:
        try:o=json.loads(e.read(500000))
        except Exception:o={}
        return int(e.code),o if isinstance(o,dict) else {}
    except Exception as e:return 'network_error',{'errorType':type(e).__name__}


def unwrap(t:Any)->tuple[str|None,str|None]:
    c=t if isinstance(t,dict) else {}
    for _ in range(8):
        k,n=c.get('kind'),c.get('name')
        if n:return k,n
        c=c.get('ofType') if isinstance(c.get('ofType'),dict) else {}
    return None,None


def inspect(name:str)->dict[str,Any]:
    q=f'''query X {{ __type(name:"{name}") {{ kind inputFields {{ name type {{ {TYPE_SHAPE} }} }} fields {{ name type {{ {TYPE_SHAPE} }} args {{ name }} }} }} }}'''
    _,o=post(q); t=((o.get('data') or {}).get('__type') or {})
    return {
      'kind':t.get('kind'),
      'inputFields':[{'name':f.get('name'),'kind':unwrap(f.get('type'))[0],'namedType':unwrap(f.get('type'))[1]} for f in (t.get('inputFields') or [])],
      'fields':[{'name':f.get('name'),'kind':unwrap(f.get('type'))[0],'namedType':unwrap(f.get('type'))[1],'hasArgs':bool(f.get('args'))} for f in (t.get('fields') or [])]
    }


def selection(type_name:str,cache:dict[str,Any],depth=0,stack=None)->str:
    if depth>5:return '__typename'
    stack=set(stack or ())
    if type_name in stack:return '__typename'
    stack.add(type_name)
    t=cache.setdefault(type_name,inspect(type_name)); parts=['__typename']
    for f in t.get('fields') or []:
        n=f['name']
        if f['hasArgs'] or not SAFE.match(n):continue
        if f['kind'] in ('SCALAR','ENUM'):parts.append(n)
        elif f['kind']=='OBJECT' and f.get('namedType'):
            child=selection(f['namedType'],cache,depth+1,stack)
            parts.append(f'{n} {{ {child} }}')
    return ' '.join(parts)


def collect(v:Any,rx:re.Pattern[str])->list[Any]:
    a=[]
    def w(x):
        if isinstance(x,dict):
            for k,y in x.items():
                if rx.search(str(k)) and isinstance(y,(str,int,float,bool)) and y not in ('',None):a.append(y)
                w(y)
        elif isinstance(x,list):
            for y in x:w(y)
    w(v); out=[]; seen=set()
    for x in a:
        m=json.dumps(x,ensure_ascii=False,sort_keys=True)
        if m not in seen:seen.add(m);out.append(x)
    return out[:300]


def main():
    s=sample(); lat,lon=s['latitude'],s['longitude']; d=.03
    zone={'topLeft':{'latitude':lat+d,'longitude':lon-d},'bottomRight':{'latitude':lat-d,'longitude':lon+d}}
    versions=[('search','LocationSearchInput','SearchLocationResult'),('searchV2','LocationSearchInputV2Input','SearchLocationResultV2')]
    attempts=[]
    for field,input_type,result_type in versions:
        cache={}; inp_schema=cache.setdefault(input_type,inspect(input_type)); sel=selection(result_type,cache)
        allowed={f['name'] for f in inp_schema.get('inputFields') or []}
        inp={'searchZone':zone}
        if 'isRoaming' in allowed:inp['isRoaming']=False
        if 'isBumpOrPartner' in allowed:inp['isBumpOrPartner']=True
        q=f'''query X($input:{input_type}!) {{ chargePoints {{ locations {{ {field}(input:$input) {{ {sel} }} }} }} }}'''
        status,o=post(q,{'input':inp}); errors=[str(e.get('message'))[:700] for e in (o.get('errors') or []) if isinstance(e,dict)]
        data=((((o.get('data') or {}).get('chargePoints') or {}).get('locations') or {}).get(field)) if isinstance(o,dict) else None
        attempts.append({'field':field,'inputType':input_type,'resultType':result_type,'input':inp,'status':status,'errors':errors,'selection':sel,'typeShapes':cache,'data':data,'ids':collect(data,re.compile(r'(^id$|identifier|location.*id|evse.*id)',re.I)),'hashes':collect(data,re.compile(r'^hash$',re.I)),'tariffGroups':collect(data,re.compile(r'tariff.*group|group.*tariff',re.I)),'prices':collect(data,re.compile(r'tariff|price|currency',re.I))})
    p={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'method':{'unauthenticated':True,'publicReadOnlySearchOnly':True,'schemaDerivedSafeSelection':True,'mutationsSent':False,'credentialsUsed':False,'personalDataQueried':False,'sampleFromOfficialBumpIrve':True},'sample':s,'attempts':attempts}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'field':a['field'],'status':a['status'],'errors':a['errors'],'ids':a['ids'][:20],'hashes':a['hashes'][:20],'tariffGroups':a['tariffGroups'][:20]} for a in attempts],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
