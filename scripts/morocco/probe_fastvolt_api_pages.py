#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

URL='https://www.fastvolt.net/api/pages'
UA='TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)'
MAX_BYTES=1_000_000

def shape(v, depth=0):
    if depth>=4: return {'type':type(v).__name__}
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

report={
 'schema_version':2,
 'generated_at':datetime.now(timezone.utc).isoformat(),
 'policy':{'read_only':True,'get_only':True,'no_login':True,'no_mutations':True,'no_session_start':True,'raw_response_body_persisted':False,'values_persisted':False,'schema_keys_only':True},
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
