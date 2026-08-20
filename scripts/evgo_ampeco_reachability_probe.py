#!/usr/bin/env python3
"""Read-only reachability probe for EVGO/AMPECO tenant candidates.

Uses only unauthenticated GET requests to candidate tenant roots and already-observed
read-only/listing routes. It never logs credentials, query strings, account/payment data,
or full successful response bodies. A successful JSON response is reduced to shape only.
"""
from __future__ import annotations
import datetime as dt
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT=Path('artifacts/evgo-ampeco-reachability'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.5)'
HOSTS=['evgo.eu-evgo.charge.ampeco.tech','echo.eu-evgo.charge.ampeco.tech']
PATHS=['/','/app/evses/search','/app/locations/withEVSE','/public-api/resources/charge-points/v1.0']

SENSITIVE=('token','secret','authorization','cookie','email','phone','payment','card','account','user','customer','wallet','invoice')

def safe_shape(value,depth=0):
    if depth>3:return None
    if isinstance(value,list):
        return {'type':'list','length':len(value),'sample_shapes':[safe_shape(x,depth+1) for x in value[:2]]}
    if isinstance(value,dict):
        keys=[str(k) for k in value.keys() if not any(s in str(k).lower() for s in SENSITIVE)]
        out={'type':'object','keys':keys[:80]}
        nested={}
        for k in keys[:20]:
            v=value.get(k)
            if isinstance(v,(dict,list)): nested[k]=safe_shape(v,depth+1)
        if nested:out['nested']=nested
        return out
    return {'type':type(value).__name__}

def probe(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*'},method='GET')
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            body=r.read(120000).decode('utf-8','replace')
            rec={'url':url,'status':r.status,'final_url':r.geturl(),'content_type':r.headers.get('content-type',''),'server':r.headers.get('server','')}
    except urllib.error.HTTPError as e:
        try: body=e.read(20000).decode('utf-8','replace')
        except Exception: body=''
        rec={'url':url,'status':e.code,'final_url':e.geturl(),'content_type':e.headers.get('content-type','') if e.headers else '','server':e.headers.get('server','') if e.headers else ''}
    except Exception as e:
        return {'url':url,'status':None,'error':f'{type(e).__name__}:{e}'}
    ctype=rec.get('content_type','').lower()
    if body and ('json' in ctype or body.lstrip().startswith(('{','['))):
        try:rec['json_shape']=safe_shape(json.loads(body))
        except Exception:rec['body_class']='json_like_unparsed'
    elif body:
        low=body.lower()
        rec['body_signals']={k:(k in low) for k in ('ampeco','unauthorized','authentication','login','not found','evgo')}
        rec['body_length_sampled']=len(body)
    return rec

def main():
    report={'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'policy':{'read_only':True,'no_login':True,'no_mutations':True,'no_query_strings':True,'no_credentials':True,'successful_response_body_persisted':False},'hosts':{}}
    for host in HOSTS:
        item={}
        try:
            infos=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
            item['dns_addresses']=sorted({x[4][0] for x in infos})[:10]
        except Exception as e:item['dns_error']=f'{type(e).__name__}:{e}'
        item['probes']=[probe('https://'+host+p) for p in PATHS]
        report['hosts'][host]=item
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({h:[(p.get('url'),p.get('status')) for p in v.get('probes',[])] for h,v in report['hosts'].items()},ensure_ascii=False))

if __name__=='__main__':main()
