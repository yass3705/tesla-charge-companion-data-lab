#!/usr/bin/env python3
"""Read-only validation-shape probe for TotalEnergies Morocco / Numocity.

Uses only dummy public/non-sensitive query values against client-confirmed GET route
fragments. No login, credentials, real connector IDs, charging actions or mutations.
Persisted output contains only HTTP status, JSON top-level keys, validation field names
and short harmless messages; raw bodies and query values are not stored.
"""
from __future__ import annotations
import datetime as dt,json,urllib.error,urllib.parse,urllib.request
from pathlib import Path

HOST='https://csmstotalenergiesma.numocity.com'
OUT=Path('artifacts/morocco-total-numocity-validation');OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
CASES=[
 ('qr_connector_no_query','/api/qr-connector',{}),
 ('qr_connector_dummy_qr','/api/qr-connector',{'qr':'0'}),
 ('qr_connector_list_no_query','/api/qr-connector-list',{}),
 ('qr_connector_list_dummy_qr','/api/qr-connector-list',{'qr':'0'}),
 ('connector_status_no_query','/api/get-connector-status',{}),
 ('connector_status_dummy_connectorid','/api/get-connector-status',{'connectorid':'0'}),
 ('connector_status_dummy_connectorId','/api/get-connector-status',{'connectorId':'0'}),
]

def safe_shape(body:str):
    try:o=json.loads(body)
    except Exception:return {'json':False}
    out={'json':True}
    if isinstance(o,dict):
        out['top_level_keys']=sorted(str(k) for k in o.keys())[:50]
        if isinstance(o.get('message'),str):out['message']=o['message'][:300]
        if isinstance(o.get('errors'),dict):out['error_fields']=sorted(str(k) for k in o['errors'].keys())[:50]
        elif isinstance(o.get('errors'),list):out['errors_type']='list'
    elif isinstance(o,list):out['top_level_type']='list';out['item_count']=len(o)
    return out

def req(label,path,params):
    url=HOST+path
    if params:url+='?'+urllib.parse.urlencode(params)
    q=urllib.request.Request(url,method='GET',headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*'})
    try:
        with urllib.request.urlopen(q,timeout=25) as r:status=r.status;ctype=r.headers.get('content-type','');body=r.read(120000).decode('utf-8','replace')
    except urllib.error.HTTPError as e:
        status=e.code;ctype=e.headers.get('content-type','') if e.headers else ''
        try:body=e.read(120000).decode('utf-8','replace')
        except Exception:body=''
    except Exception as e:return {'case':label,'path':path,'status':None,'error_type':type(e).__name__}
    return {'case':label,'path':path,'status':status,'content_type':ctype,'safe_response':safe_shape(body)}

def main():
    probes=[req(*c) for c in CASES]
    rep={'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'host':HOST.removeprefix('https://'),'policy':{'read_only_get_only':True,'no_login':True,'no_credentials':True,'dummy_values_only':True,'raw_response_bodies_persisted':False,'query_values_persisted':False,'no_charging_or_account_mutations':True},'probes':probes}
    (OUT/'summary.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'case':x['case'],'status':x.get('status')} for x in probes]))
if __name__=='__main__':main()
