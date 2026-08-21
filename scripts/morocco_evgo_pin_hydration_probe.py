#!/usr/bin/env python3
"""Read-only EVGO pin->location hydration and public schema probe."""
from __future__ import annotations
import datetime as dt, json, urllib.error, urllib.request
from pathlib import Path

HOST='https://cp.evgo.ma'; PIN_IDS=[8,4,19]
PATHS=['/api/v1/app/locations','/api/v2/app/locations']
CASES={'numeric_ids':{'locations':PIN_IDS},'string_ids':{'locations':[str(x) for x in PIN_IDS]},'objects_id':{'locations':[{'id':x} for x in PIN_IDS]},'objects_locationId':{'locations':[{'locationId':x} for x in PIN_IDS]},'objects_location_id':{'locations':[{'location_id':x} for x in PIN_IDS]}}
OUT=Path('artifacts/morocco-evgo-pin-hydration'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.3)'
ALLOW={'id','name','title','status','availability','available','power','powerKw','maxPower','max_power','maximumPower','latitude','longitude','lat','lng','address','city','currency','currencies','tariff','tariffs','price','free','evse','evses','evseId','evse_id','evseIdentifier','connectors','connectorType','connector_id','connectorId','type','standard','format','operator','network','cpo','clusterSize','underlyingLocationIds','geo','av','locationId','location_id','zones'}

def sanitize(v,depth=0):
    if depth>7:return None
    if isinstance(v,list):return [sanitize(x,depth+1) for x in v[:10]]
    if isinstance(v,dict):
        out={}
        for k,x in v.items():
            if k in ALLOW: out[k]=sanitize(x,depth+1)
            elif isinstance(x,(dict,list)):
                y=sanitize(x,depth+1)
                if y not in (None,{},[]): out[k]=y
        return out
    if isinstance(v,(str,int,float,bool)) or v is None:return v
    return None

def nested_key_shapes(o):
    out={}
    try:
        locs=o.get('locations') or []
        if not locs:return out
        loc=locs[0]; zones=loc.get('zones') or []
        out['location_keys']=sorted(map(str,loc.keys()))[:120]
        if zones:
            zone=zones[0]; out['zone_keys']=sorted(map(str,zone.keys()))[:120]
            evses=zone.get('evses') or []
            if evses:
                evse=evses[0]; out['evse_keys']=sorted(map(str,evse.keys()))[:120]
                conns=evse.get('connectors') or [] if isinstance(evse,dict) else []
                if conns and isinstance(conns[0],dict):out['connector_keys']=sorted(map(str,conns[0].keys()))[:120]
    except Exception:pass
    return out

def shape(body):
    try:o=json.loads(body)
    except Exception:return {'json':False}
    r={'json':True}
    if isinstance(o,dict):
        r['top_level_keys']=sorted(map(str,o.keys()))[:50]
        r['collection_counts']={str(k):len(v) for k,v in o.items() if isinstance(v,(list,dict))}
        r['collection_item_keys']={str(k):sorted(map(str,v[0].keys()))[:120] for k,v in o.items() if isinstance(v,list) and v and isinstance(v[0],dict)}
        nk=nested_key_shapes(o)
        if nk:r['nested_public_key_shapes']=nk
        s=sanitize(o)
        if s not in ({},None):r['sanitized_public_sample']=s
        if isinstance(o.get('message'),str):r['message']=o['message'][:500]
        if isinstance(o.get('errors'),dict):r['error_keys']=sorted(map(str,o['errors'].keys()))[:50]
    return r

def perform(q,path,label,method):
    try:
        with urllib.request.urlopen(q,timeout=25) as z:status=z.status;ctype=z.headers.get('content-type','');body=z.read(500000).decode('utf-8','replace')
    except urllib.error.HTTPError as e:
        status=e.code;ctype=e.headers.get('content-type','') if e.headers else ''
        try:body=e.read(500000).decode('utf-8','replace')
        except Exception:body=''
    except Exception as e:return {'method':method,'path':path,'case':label,'status':None,'error_type':type(e).__name__}
    return {'method':method,'path':path,'case':label,'status':status,'content_type':ctype,'safe_response':shape(body)}

def post_req(path,label,payload):
    q=urllib.request.Request(HOST+path,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    return perform(q,path,label,'POST')

def get_req(path,label):
    q=urllib.request.Request(HOST+path,method='GET',headers={'User-Agent':UA,'Accept':'application/json'})
    return perform(q,path,label,'GET')

def main():
    probes=[post_req(path,label,payload) for path in PATHS for label,payload in CASES.items()]
    for base in PATHS:
        for location_id in PIN_IDS:probes.append(get_req(f'{base}/{location_id}',f'direct_location_{location_id}'))
    report={'schema_version':4,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'host':'cp.evgo.ma','source_pin_ids':PIN_IDS,'policy':{'read_only_hydration':True,'get_single_location_read_only':True,'no_login':True,'no_credentials':True,'no_mutations':True,'no_coordinates_submitted':True,'ids_origin':'anonymous /app/pins public response','raw_response_bodies_persisted':False,'only_whitelisted_public_charging_fields_sampled':True,'nested_key_names_only_for_schema_discovery':True},'post_cases_tested':list(CASES),'direct_get_ids_tested':PIN_IDS,'probes':probes}
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'method':x.get('method'),'path':x['path'],'status':x.get('status'),'counts':x.get('safe_response',{}).get('collection_counts',{}),'nested':x.get('safe_response',{}).get('nested_public_key_shapes',{})} for x in probes]))
if __name__=='__main__':main()
