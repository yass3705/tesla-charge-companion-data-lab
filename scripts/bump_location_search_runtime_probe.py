#!/usr/bin/env python3
"""Probe Bump public GraphQL searchV3 with a real official Bump map zone.

Unauthenticated, read-only search query only. No account/session/payment data or mutations.
"""
from __future__ import annotations
import json, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_direct_inventory import DATASET_API, decode_csv, get_bytes, get_json, is_bump_operator, norm, resolve_csv_resource

ENDPOINT='https://api.bump-charge.com/graphql'
OUT=Path('reports/bump/location_search_runtime_latest.json')
UA='TeslaChargeCompanionDataLab/1.0 (public Bump location search runtime)'


def post(query:str, variables:dict[str,Any])->tuple[int|str,dict[str,Any]]:
    req=urllib.request.Request(ENDPOINT,data=json.dumps({'query':query,'variables':variables}).encode(),method='POST',headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            obj=json.load(r); return int(r.status), obj if isinstance(obj,dict) else {}
    except urllib.error.HTTPError as e:
        try: obj=json.loads(e.read(300000))
        except Exception: obj={}
        return int(e.code), obj if isinstance(obj,dict) else {}
    except Exception as e:
        return 'network_error', {'errorType':type(e).__name__}


def coords(v:Any)->tuple[float,float]|None:
    s=norm(v)
    if not s: return None
    try:
        a=json.loads(s)
        if isinstance(a,list) and len(a)>=2:
            lon,lat=float(a[0]),float(a[1]); return lat,lon
    except Exception: pass
    return None


def sample()->dict[str,Any]:
    ds=get_json(DATASET_API); res=resolve_csv_resource(ds)
    rows,_=decode_csv(get_bytes(str(res.get('url') or res.get('latest'))))
    out=[]
    for r in rows:
        if not is_bump_operator(r.get('nom_operateur')): continue
        c=coords(r.get('coordonneesXY'))
        sid=norm(r.get('id_station_itinerance')); eid=norm(r.get('id_pdc_itinerance'))
        if c and sid and eid: out.append((sid,eid,c,r))
    out.sort(key=lambda x:(x[0],x[1]))
    sid,eid,(lat,lon),r=out[0]
    return {'stationIdentifier':sid,'evseIdentifier':eid,'stationName':norm(r.get('nom_station')),'latitude':lat,'longitude':lon}


def main():
    s=sample(); lat=s['latitude']; lon=s['longitude']; d=.02
    zone={'topLeft':{'latitude':lat+d,'longitude':lon-d},'bottomRight':{'latitude':lat-d,'longitude':lon+d}}
    q='''query TccSearch($input: LocationSearchInputV3Input!) { chargePoints { locations { searchV3(input: $input) { __typename } } } }'''
    variants=[
        {'label':'zone_only','input':{'searchZone':zone}},
        {'label':'direct_non_roaming','input':{'searchZone':zone,'isRoaming':False}},
        {'label':'bump_or_partner_non_roaming','input':{'searchZone':zone,'isRoaming':False,'isBumpOrPartner':True}},
    ]
    attempts=[]
    for v in variants:
        status,obj=post(q,{'input':v['input']})
        errors=[str(x.get('message'))[:500] for x in (obj.get('errors') or []) if isinstance(x,dict)]
        data=obj.get('data') if isinstance(obj,dict) else None
        attempts.append({'label':v['label'],'status':status,'errors':errors,'hasData':data is not None,'typename':((((data or {}).get('chargePoints') or {}).get('locations') or {}).get('searchV3') or {}).get('__typename') if isinstance(data,dict) else None})
    payload={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'method':{'unauthenticated':True,'publicReadOnlySearchOnly':True,'mutationsSent':False,'credentialsUsed':False,'personalDataQueried':False,'sampleFromOfficialBumpIrve':True},'sample':s,'searchZone':zone,'attempts':attempts,'publicSearchSucceeded':any(a.get('typename') for a in attempts)}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(payload,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
