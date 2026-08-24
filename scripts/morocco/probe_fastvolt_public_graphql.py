#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ENDPOINT = "https://sg2i.com/akwadigi/fastvolt/graphql"
QUERY = "query TccPublicProbe { __typename }"
UA = "TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)"


def safe_decode(data):
    try:
        obj=json.loads(data.decode('utf-8','replace'))
    except Exception:
        return {"json": False, "body_prefix": data.decode('utf-8','replace')[:160]}
    out={"json": True, "top_level_keys": sorted(obj.keys()) if isinstance(obj,dict) else [], "response_type": type(obj).__name__}
    if isinstance(obj,dict):
        data_obj=obj.get('data')
        if isinstance(data_obj,dict):
            out['data_keys']=sorted(data_obj.keys())
            if '__typename' in data_obj: out['typename']=data_obj.get('__typename')
        errs=obj.get('errors')
        if isinstance(errs,list):
            out['error_count']=len(errs)
            out['error_messages']=[str(e.get('message',''))[:200] for e in errs[:5] if isinstance(e,dict)]
    return out


def call(method):
    if method=='GET':
        url=ENDPOINT+'?'+urlencode({'query':QUERY})
        req=Request(url, headers={'User-Agent':UA,'Accept':'application/json'}, method='GET')
    else:
        body=json.dumps({'query':QUERY}).encode()
        req=Request(ENDPOINT, data=body, headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=20) as r:
            b=r.read(65536)
            return {'method':method,'status':getattr(r,'status',200),'content_type':r.headers.get('Content-Type'),'response':safe_decode(b)}
    except HTTPError as e:
        b=e.read(65536)
        return {'method':method,'status':e.code,'content_type':e.headers.get('Content-Type'),'response':safe_decode(b)}
    except Exception as e:
        return {'method':method,'error':type(e).__name__+': '+str(e)[:250]}

report={
  'schema_version':1,
  'generated_at':datetime.now(timezone.utc).isoformat(),
  'endpoint':ENDPOINT,
  'source':'public FastVolt web-map JavaScript asset',
  'policy':{'read_only':True,'no_login':True,'no_credentials':True,'no_mutations':True,'query_only':True,'raw_response_body_persisted':False},
  'probes':[call('GET'), call('POST')]
}
report['validated_public_graphql']=any(p.get('status')==200 and p.get('response',{}).get('typename') for p in report['probes'])
json.dump(report,sys.stdout,ensure_ascii=False,indent=2); print()
