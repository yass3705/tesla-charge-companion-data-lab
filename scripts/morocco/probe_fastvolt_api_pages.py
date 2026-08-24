#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

URL='https://www.fastvolt.net/api/pages'
UA='TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)'
MAX_BYTES=1_000_000
MAX_DEPTH=9

INTEREST=('charger','station','borne','geo','coord','location','connector','evse','power','status','price','tariff','operator','map')

def shape(v, depth=0):
    if depth>=6: return {'type':type(v).__name__}
    if isinstance(v,dict):
        keys=sorted(str(k) for k in v.keys())[:160]
        fields={}
        for k in sorted(v,key=lambda x:str(x))[:80]:
            fields[str(k)]=shape(v[k],depth+1)
        return {'type':'dict','keys':keys,'fields':fields}
    if isinstance(v,list):
        rec={'type':'list','count':len(v)}
        if v: rec['item_shape']=shape(v[0],depth+1)
        return rec
    return {'type':type(v).__name__}

def walk_schema(v,path='$',depth=0,all_keys=None,interesting_paths=None,list_paths=None):
    if all_keys is None: all_keys=set()
    if interesting_paths is None: interesting_paths=[]
    if list_paths is None: list_paths=[]
    if depth>MAX_DEPTH: return all_keys,interesting_paths,list_paths
    if isinstance(v,dict):
        for k,val in v.items():
            ks=str(k); all_keys.add(ks)
            p=f'{path}.{ks}'
            if any(t in ks.lower() for t in INTEREST): interesting_paths.append(p)
            walk_schema(val,p,depth+1,all_keys,interesting_paths,list_paths)
    elif isinstance(v,list):
        list_paths.append({'path':path,'count':len(v)})
        # Traverse a bounded set of item shapes only; never persist item values.
        for i,item in enumerate(v[:5]):
            walk_schema(item,f'{path}[]',depth+1,all_keys,interesting_paths,list_paths)
    return all_keys,interesting_paths,list_paths

report={
 'schema_version':3,
 'generated_at':datetime.now(timezone.utc).isoformat(),
 'policy':{'read_only':True,'get_only':True,'no_login':True,'no_mutations':True,'no_session_start':True,'raw_response_body_persisted':False,'values_persisted':False,'schema_keys_only':True,'bounded_recursive_schema_walk':True},
 'url':URL
}
try:
    req=Request(URL,headers={'User-Agent':UA,'Accept':'application/json,*/*;q=0.1'},method='GET')
    with urlopen(req,timeout=20) as r:
        b=r.read(MAX_BYTES+1)
        report['status']=getattr(r,'status',200)
        report['content_type']=r.headers.get('Content-Type')
        report['bytes_read']=min(len(b),MAX_BYTES)
        report['truncated']=len(b)>MAX_BYTES
        b=b[:MAX_BYTES]
        try:
            data=json.loads(b.decode('utf-8','replace'))
            report['json']=True
            report['top_level_type']=type(data).__name__
            if isinstance(data,dict):
                report['top_level_keys']=sorted(str(k) for k in data.keys())[:120]
                report['top_level_field_shapes']={str(k):shape(v,1) for k,v in data.items()}
            elif isinstance(data,list):
                report['item_count']=len(data)
                report['item_shape']=shape(data[0],1) if data else None
            keys,paths,lists=walk_schema(data)
            report['recursive_schema']={
              'max_depth':MAX_DEPTH,
              'unique_key_count':len(keys),
              'interesting_keys':sorted(k for k in keys if any(t in k.lower() for t in INTEREST))[:200],
              'interesting_paths':sorted(set(paths))[:300],
              'list_shapes':sorted({(x['path'],x['count']) for x in lists})[:200],
            }
        except Exception as ex:
            report['json']=False
            report['parse_error']=type(ex).__name__
except HTTPError as ex:
    report['status']=ex.code
    report['content_type']=ex.headers.get('Content-Type')
    report['http_error']=True
except Exception as ex:
    report['error']=type(ex).__name__+': '+str(ex)[:180]
json.dump(report,sys.stdout,ensure_ascii=False,indent=2)
print()
