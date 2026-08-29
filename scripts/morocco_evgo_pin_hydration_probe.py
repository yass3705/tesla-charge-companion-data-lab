#!/usr/bin/env python3
"""Read-only EVGO public pin -> location -> EVSE inventory probe.

Discovers public map pins anonymously, extracts their public map metadata and
underlyingLocationIds, then GETs each corresponding public /app/locations/{id}
resource. No login, credentials, charging/session actions, or mutations.
Persisted output is limited to public charging infrastructure fields needed to
validate station identity, map position, EVSE status, power, connector shape,
operator attribution and tariff references.

This probe is safe to re-run as a bounded freshness check of the public EVGO map data.
"""
from __future__ import annotations
import datetime as dt, json, urllib.error, urllib.request
from pathlib import Path

HOST='https://cp.evgo.ma'
VERSIONS=['v1','v2']
OUT=Path('artifacts/morocco-evgo-pin-hydration'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.5)'

SAFE_LOCATION={'id','name','address','description','detailed_description','additional_description','timezone','workingHours','updatedAt','zones','underlyingLocationIds'}
SAFE_EVSE={'id','identifier','emi3Identifier','roamingEvseId','label','status','isAvailable','isLongTermUnavailable','isTemporarilyUnavailable','maxPower','currentType','operatorId','operatedBy','networkId','managedByOperator','tariffId','connectors','chargePointModel','hasParkingBarrier','canReserve'}
SAFE_CONNECTOR={'id','name','format','status','icon','afirLabellingLetter'}
SAFE_PIN={'id','underlyingLocationIds','geo','av','clusterSize'}

def req_json(path:str):
    q=urllib.request.Request(HOST+path,method='GET',headers={'User-Agent':UA,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(q,timeout=25) as r:
            body=r.read(750000).decode('utf-8','replace')
            return r.status,r.headers.get('content-type',''),json.loads(body)
    except urllib.error.HTTPError as e:
        try: body=e.read(250000).decode('utf-8','replace')
        except Exception: body=''
        try: obj=json.loads(body)
        except Exception: obj={}
        return e.code,e.headers.get('content-type','') if e.headers else '',obj
    except Exception as e:
        return None,'',{'error_type':type(e).__name__}

def safe_connector(c):
    if not isinstance(c,dict): return None
    return {k:c.get(k) for k in SAFE_CONNECTOR if k in c}

def safe_evse(e):
    if not isinstance(e,dict): return None
    out={k:e.get(k) for k in SAFE_EVSE if k in e and k!='connectors'}
    conns=e.get('connectors')
    if isinstance(conns,list): out['connectors']=[safe_connector(c) for c in conns[:12]]
    return out

def safe_location(loc):
    if not isinstance(loc,dict): return None
    out={k:loc.get(k) for k in SAFE_LOCATION if k in loc and k!='zones'}
    zones=[]
    for z in (loc.get('zones') or [])[:20]:
        if not isinstance(z,dict): continue
        zones.append({'id':z.get('id'),'evses':[safe_evse(e) for e in (z.get('evses') or [])[:40]]})
    out['zones']=zones
    return out

def safe_pin(pin):
    if not isinstance(pin,dict): return None
    return {k:pin.get(k) for k in SAFE_PIN if k in pin}

def collect_ids(pins_obj):
    ids=[]
    pins=pins_obj.get('pins') if isinstance(pins_obj,dict) else None
    if not isinstance(pins,list): return ids
    for p in pins:
        if not isinstance(p,dict): continue
        vals=p.get('underlyingLocationIds')
        if not isinstance(vals,list): continue
        for x in vals:
            if isinstance(x,(int,str)) and str(x).isdigit():
                n=int(x)
                if n not in ids: ids.append(n)
    return ids

def station_summary(loc):
    statuses=[]; tariff_ids=[]; operators=[]; powers=[]; connector_names=[]; evse_ids=[]
    for z in loc.get('zones') or []:
        for e in z.get('evses') or []:
            if not isinstance(e,dict): continue
            if e.get('status') is not None: statuses.append(e.get('status'))
            if e.get('tariffId') is not None: tariff_ids.append(e.get('tariffId'))
            if e.get('operatorId') is not None: operators.append(e.get('operatorId'))
            if e.get('maxPower') is not None: powers.append(e.get('maxPower'))
            if e.get('id') is not None: evse_ids.append(e.get('id'))
            for c in e.get('connectors') or []:
                if isinstance(c,dict) and c.get('name'): connector_names.append(c.get('name'))
    return {
        'location_id':loc.get('id'),'name':loc.get('name'),'address':loc.get('address'),
        'evse_ids':list(dict.fromkeys(evse_ids)),'statuses':list(dict.fromkeys(statuses)),
        'tariff_ids':list(dict.fromkeys(tariff_ids)),'operator_ids':list(dict.fromkeys(operators)),
        'max_powers':list(dict.fromkeys(powers)),'connector_names':list(dict.fromkeys(connector_names)),
    }

def main():
    report={'schema_version':6,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'host':'cp.evgo.ma',
            'policy':{'read_only_get_only':True,'no_login':True,'no_credentials':True,'no_mutations':True,'raw_response_bodies_persisted':False,'only_public_charging_fields_persisted':True},
            'versions':{}}
    for version in VERSIONS:
        pin_path=f'/api/{version}/app/pins'
        ps,pc,pobj=req_json(pin_path)
        raw_pins=pobj.get('pins') if isinstance(pobj,dict) and isinstance(pobj.get('pins'),list) else []
        ids=collect_ids(pobj)
        entry={'pins_status':ps,'pins_content_type':pc,'pin_count':len(raw_pins) if raw_pins else (0 if isinstance(raw_pins,list) else None),'pins':[safe_pin(p) for p in raw_pins[:100]],'location_ids':ids,'locations':[],'station_summaries':[]}
        for lid in ids[:100]:
            status,ctype,obj=req_json(f'/api/{version}/app/locations/{lid}')
            loc=None
            if isinstance(obj,dict):
                if isinstance(obj.get('locations'),list) and obj.get('locations'): loc=obj['locations'][0]
                elif all(k in obj for k in ('id','name')): loc=obj
                elif isinstance(obj.get('location'),dict): loc=obj['location']
            safe=safe_location(loc) if loc else None
            entry['locations'].append({'id':lid,'status':status,'content_type':ctype,'location':safe})
            if safe: entry['station_summaries'].append(station_summary(safe))
        report['versions'][version]=entry
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for v,x in report['versions'].items():
        print(json.dumps({'version':v,'pin_count':x['pin_count'],'public_pins':x['pins'],'location_ids':len(x['location_ids']),'stations':x['station_summaries']},ensure_ascii=False))

if __name__=='__main__': main()
