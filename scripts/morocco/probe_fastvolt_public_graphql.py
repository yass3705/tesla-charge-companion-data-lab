#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ENDPOINT = "https://sg2i.com/akwadigi/fastvolt/graphql"
PING_QUERY = "query TccPublicProbe { __typename }"
SCHEMA_QUERY = "query TccPublicSchemaProbe { __schema { queryType { name fields { name } } } }"
# Recovered directly from the public FastVolt web-map bundle; no schema guessing.
FASTVOLT_SECTION_QUERY = "query NewQuery { fastvoltsections { __typename } }"
UA = "TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)"


def decode_json(data):
    try:
        return json.loads(data.decode('utf-8','replace'))
    except Exception:
        return None


def summarize(obj, schema=False):
    if obj is None:
        return {"json": False}
    out={"json": True, "top_level_keys": sorted(obj.keys()) if isinstance(obj,dict) else [], "response_type": type(obj).__name__}
    if isinstance(obj,dict):
        data_obj=obj.get('data')
        if isinstance(data_obj,dict):
            out['data_keys']=sorted(data_obj.keys())
            if '__typename' in data_obj: out['typename']=data_obj.get('__typename')
            # Only retain nested typename, never station/content values.
            fv=data_obj.get('fastvoltsections')
            if isinstance(fv,dict) and '__typename' in fv:
                out['fastvoltsections_typename']=fv.get('__typename')
            if schema:
                sch=data_obj.get('__schema')
                qt=sch.get('queryType') if isinstance(sch,dict) else None
                if isinstance(qt,dict):
                    out['query_root_name']=qt.get('name')
                    fields=qt.get('fields')
                    if isinstance(fields,list):
                        names=sorted({f.get('name') for f in fields if isinstance(f,dict) and isinstance(f.get('name'),str)})
                        out['query_field_names']=names
                        out['query_field_count']=len(names)
        errs=obj.get('errors')
        if isinstance(errs,list):
            out['error_count']=len(errs)
            out['error_messages']=[str(e.get('message',''))[:200] for e in errs[:5] if isinstance(e,dict)]
    return out


def call(query, label, method='GET', schema=False):
    if method=='GET':
        url=ENDPOINT+'?'+urlencode({'query':query})
        req=Request(url, headers={'User-Agent':UA,'Accept':'application/json'}, method='GET')
    else:
        body=json.dumps({'query':query}).encode()
        req=Request(ENDPOINT, data=body, headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=20) as r:
            b=r.read(262144)
            return {'label':label,'method':method,'status':getattr(r,'status',200),'content_type':r.headers.get('Content-Type'),'response':summarize(decode_json(b), schema=schema)}
    except HTTPError as e:
        b=e.read(262144)
        return {'label':label,'method':method,'status':e.code,'content_type':e.headers.get('Content-Type'),'response':summarize(decode_json(b), schema=schema)}
    except Exception as e:
        return {'label':label,'method':method,'error':type(e).__name__+': '+str(e)[:250]}

probes=[
    call(PING_QUERY,'typename_get','GET'),
    call(PING_QUERY,'typename_post','POST'),
    call(SCHEMA_QUERY,'query_root_fields_get','GET',schema=True),
    call(FASTVOLT_SECTION_QUERY,'public_bundle_newquery_fastvoltsections_typename','GET')
]
report={
  'schema_version':3,
  'generated_at':datetime.now(timezone.utc).isoformat(),
  'endpoint':ENDPOINT,
  'source':'public FastVolt web-map JavaScript asset',
  'policy':{'read_only':True,'no_login':True,'no_credentials':True,'no_mutations':True,'query_only':True,'schema_field_names_only':True,'bundle_recovered_field_validation_only':True,'raw_response_body_persisted':False,'content_values_persisted':False},
  'probes':probes
}
report['validated_public_graphql']=any(p.get('status')==200 and p.get('response',{}).get('typename') for p in probes)
report['validated_fastvoltsections_root']=any(p.get('response',{}).get('fastvoltsections_typename') for p in probes)
for p in probes:
    names=p.get('response',{}).get('query_field_names')
    if names is not None:
        report['public_query_field_names']=names
        break
json.dump(report,sys.stdout,ensure_ascii=False,indent=2); print()
