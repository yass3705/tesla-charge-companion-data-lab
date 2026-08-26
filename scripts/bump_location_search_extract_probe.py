#!/usr/bin/env python3
"""Extract safe public technical identifiers from Bump GraphQL searchV3.

Uses only the unauthenticated read-only map search resolver already verified public. Selection is
schema-derived and restricted to station/EVSE/tariff/coordinate/operator technical fields.
"""
from __future__ import annotations
import json, re, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_location_search_runtime_probe import sample

ENDPOINT='https://api.bump-charge.com/graphql'
OUT=Path('reports/bump/location_search_extract_latest.json')
UA='TeslaChargeCompanionDataLab/1.0 (public Bump map technical extraction)'
TYPE_SHAPE='kind name ofType { kind name ofType { kind name ofType { kind name } } }'
SAFE_FIELD=re.compile(r'^(?:id|identifier|name|status|isRoaming|maxPower|power|latitude|longitude|tariffGroup|operator|operators|location|locations|evse|evses|allEvses|coordinates|connectorTypes|connectors|chargeType|items|results|data|points|markers|clusters|total|count|priceScoring|currency|price|tariff)$',re.I)


def post(query:str,variables:dict[str,Any]|None=None)->tuple[int|str,dict[str,Any]]:
    req=urllib.request.Request(ENDPOINT,data=json.dumps({'query':query,'variables':variables or {}}).encode(),method='POST',headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            obj=json.load(r); return int(r.status),obj if isinstance(obj,dict) else {}
    except urllib.error.HTTPError as e:
        try: obj=json.loads(e.read(500000))
        except Exception: obj={}
        return int(e.code),obj if isinstance(obj,dict) else {}
    except Exception as e:
        return 'network_error',{'errorType':type(e).__name__}


def unwrap(t:Any)->tuple[str|None,str|None]:
    cur=t if isinstance(t,dict) else {}
    for _ in range(8):
        k,n=cur.get('kind'),cur.get('name')
        if n: return k,n
        cur=cur.get('ofType') if isinstance(cur.get('ofType'),dict) else {}
    return None,None


def inspect(name:str)->dict[str,Any]:
    assert re.fullmatch(r'[_A-Za-z][_0-9A-Za-z]*',name)
    q=f'''query TccType {{ __type(name: "{name}") {{ name kind fields {{ name type {{ {TYPE_SHAPE} }} args {{ name }} }} }} }}'''
    _,obj=post(q); t=((obj.get('data') or {}).get('__type') or {})
    fields=[]
    for f in t.get('fields') or []:
        k,n=unwrap(f.get('type')); fields.append({'name':f.get('name'),'kind':k,'namedType':n,'hasArgs':bool(f.get('args'))})
    return {'name':t.get('name'),'kind':t.get('kind'),'fields':fields}


def build_selection(type_name:str,depth:int,cache:dict[str,dict[str,Any]],stack:set[str])->str:
    if depth>4 or type_name in stack: return ''
    t=cache.setdefault(type_name,inspect(type_name)); parts=['__typename']
    stack=set(stack); stack.add(type_name)
    for f in t.get('fields') or []:
        name=f.get('name') or ''
        if f.get('hasArgs') or not SAFE_FIELD.match(name): continue
        kind,named=f.get('kind'),f.get('namedType')
        if kind in ('SCALAR','ENUM'):
            parts.append(name)
        elif kind in ('OBJECT','INTERFACE') and named:
            child=build_selection(named,depth+1,cache,stack) if kind=='OBJECT' else ''
            if child: parts.append(f'{name} {{ {child} }}')
    return ' '.join(parts)


def collect(v:Any,key_re:re.Pattern[str],limit:int=200)->list[Any]:
    out=[]
    def walk(x:Any):
        if len(out)>=limit:return
        if isinstance(x,dict):
            for k,y in x.items():
                if key_re.search(str(k)) and isinstance(y,(str,int,float,bool)) and y not in ('',None): out.append(y)
                walk(y)
        elif isinstance(x,list):
            for y in x: walk(y)
    walk(v)
    seen=set(); ded=[]
    for x in out:
        m=json.dumps(x,sort_keys=True,ensure_ascii=False)
        if m not in seen: seen.add(m); ded.append(x)
    return ded


def main():
    s=sample(); lat,lon=s['latitude'],s['longitude']; d=.03
    zone={'topLeft':{'latitude':lat+d,'longitude':lon-d},'bottomRight':{'latitude':lat-d,'longitude':lon+d}}
    cache={}; selection=build_selection('SearchLocationResultV3',0,cache,set())
    q=f'''query TccSearch($input: LocationSearchInputV3Input!) {{ chargePoints {{ locations {{ searchV3(input:$input) {{ {selection} }} }} }} }}'''
    inp={'searchZone':zone,'isRoaming':False,'isBumpOrPartner':True}
    status,obj=post(q,{'input':inp}); errors=[str(e.get('message'))[:500] for e in (obj.get('errors') or []) if isinstance(e,dict)]
    data=((((obj.get('data') or {}).get('chargePoints') or {}).get('locations') or {}).get('searchV3')) if isinstance(obj,dict) else None
    payload={
      'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),
      'method':{'unauthenticated':True,'publicReadOnlySearchOnly':True,'schemaDerivedSafeSelection':True,'mutationsSent':False,'credentialsUsed':False,'personalDataQueried':False,'sampleFromOfficialBumpIrve':True},
      'sample':s,'input':inp,'status':status,'errors':errors,'selection':selection,'typeShapes':cache,
      'data':data,
      'ids':collect(data,re.compile(r'(^id$|identifier|location.*id|evse.*id)',re.I)),
      'tariffGroupValues':collect(data,re.compile(r'tariff.*group|group.*tariff',re.I)),
      'tariffPriceValues':collect(data,re.compile(r'tariff|price|currency',re.I)),
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':status,'errors':errors,'ids':payload['ids'][:20],'tariffGroups':payload['tariffGroupValues'][:20],'priceValues':payload['tariffPriceValues'][:20]},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
