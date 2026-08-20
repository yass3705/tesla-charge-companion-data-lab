#!/usr/bin/env python3
"""Read-only reachability probe for TotalEnergies Morocco Numocity routes.

Only unauthenticated GETs with no query parameters are issued. The goal is to distinguish
route existence/method behavior without reproducing user sessions or connector identifiers.
Successful bodies are reduced to JSON shape; error bodies are reduced to generic signals.
"""
from __future__ import annotations
import datetime as dt,json,urllib.error,urllib.request
from pathlib import Path

OUT=Path('artifacts/totalenergies-numocity-reachability');OUT.mkdir(parents=True,exist_ok=True)
BASE='https://csmstotalenergiesma.numocity.com'
PATHS=['/','/api/qr-connector','/api/get-connector-status','/api/connector-status']
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.5)'
SENSITIVE=('token','secret','authorization','cookie','email','phone','payment','card','account','user','customer','wallet','invoice')

def shape(x,depth=0):
 if depth>3:return None
 if isinstance(x,list):return {'type':'list','length':len(x),'sample_shapes':[shape(v,depth+1) for v in x[:2]]}
 if isinstance(x,dict):
  keys=[str(k) for k in x if not any(s in str(k).lower() for s in SENSITIVE)]
  return {'type':'object','keys':keys[:80]}
 return {'type':type(x).__name__}

def probe(path):
 url=BASE+path
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*'},method='GET')
 try:
  with urllib.request.urlopen(req,timeout=20) as r:body=r.read(60000).decode('utf-8','replace');rec={'path':path,'status':r.status,'final_path':urllib.request.urlparse(r.geturl()).path if hasattr(urllib.request,'urlparse') else path,'content_type':r.headers.get('content-type',''),'server':r.headers.get('server','')}
 except urllib.error.HTTPError as e:
  try:body=e.read(20000).decode('utf-8','replace')
  except Exception:body=''
  rec={'path':path,'status':e.code,'content_type':e.headers.get('content-type','') if e.headers else '','server':e.headers.get('server','') if e.headers else ''}
 except Exception as e:return {'path':path,'status':None,'error':f'{type(e).__name__}:{e}'}
 if body:
  try:rec['json_shape']=shape(json.loads(body))
  except Exception:
   low=body.lower();rec['body_signals']={k:(k in low) for k in ('not found','method','required','missing','unauthorized','forbidden','connector','qr')};rec['body_length_sampled']=len(body)
 return rec

def main():
 report={'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'base_host':'csmstotalenergiesma.numocity.com','policy':{'read_only':True,'no_login':True,'no_mutations':True,'no_query_parameters':True,'no_credentials':True,'successful_response_body_persisted':False},'probes':[probe(p) for p in PATHS]}
 (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps([(x.get('path'),x.get('status')) for x in report['probes']]))
if __name__=='__main__':main()
