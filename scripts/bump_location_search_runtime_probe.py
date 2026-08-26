#!/usr/bin/env python3
"""Probe Bump public GraphQL map search and anonymous tariff lookup for one official Bump station.

Unauthenticated, read-only queries only. No account/session/payment data or mutations.
The sample station is taken from Bump's own official IRVE inventory and only public charging/tariff
fields required for TCC are retained. Matching is primarily geographic because the app may expose
an internal EVSE identifier different from the regulatory FRBMP interoperable identifier.
"""
from __future__ import annotations
import json, math, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_direct_inventory import DATASET_API, decode_csv, get_bytes, get_json, is_bump_operator, norm, resolve_csv_resource

ENDPOINT='https://api.bump-charge.com/graphql'
OUT=Path('reports/bump/location_search_runtime_latest.json')
UA='TeslaChargeCompanionDataLab/1.0 (public Bump location/tariff search runtime)'


def post(query:str, variables:dict[str,Any])->tuple[int|str,dict[str,Any]]:
    req=urllib.request.Request(ENDPOINT,data=json.dumps({'query':query,'variables':variables}).encode(),method='POST',headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            obj=json.load(r); return int(r.status), obj if isinstance(obj,dict) else {}
    except urllib.error.HTTPError as e:
        try: obj=json.loads(e.read(500000))
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


def errors(obj:dict[str,Any])->list[str]:
    return [str(x.get('message'))[:500] for x in (obj.get('errors') or []) if isinstance(x,dict)]


def distance_m(lat1:float,lon1:float,lat2:float,lon2:float)->float:
    # Sufficient for sub-km matching of the same station.
    dy=(lat2-lat1)*111_320.0
    dx=(lon2-lon1)*111_320.0*math.cos(math.radians((lat1+lat2)/2.0))
    return math.hypot(dx,dy)


def safe_location(loc:dict[str,Any], sample_lat:float, sample_lon:float)->dict[str,Any]:
    c=loc.get('coordinates') if isinstance(loc.get('coordinates'),dict) else {}
    lat=c.get('latitude'); lon=c.get('longitude')
    dist=None
    if isinstance(lat,(int,float)) and isinstance(lon,(int,float)):
        dist=round(distance_m(sample_lat,sample_lon,float(lat),float(lon)),1)
    evses=[]
    for e in loc.get('evses') or []:
        if not isinstance(e,dict): continue
        tg=e.get('tariffGroup') if isinstance(e.get('tariffGroup'),dict) else {}
        evses.append({
            'evseId':e.get('id'),'evseIdentifier':e.get('identifier'),'evseIsRoaming':e.get('isRoaming'),
            'tariffGroupId':tg.get('id'),
        })
    return {
        'locationId':loc.get('id'),'locationName':loc.get('name'),'locationIsRoaming':loc.get('isRoaming'),
        'latitude':lat,'longitude':lon,'distanceFromOfficialMeters':dist,'evses':evses,
    }


def tariff_detail(evse:dict[str,Any])->dict[str,Any]:
    q='''query TccTariff($tariffGroupId: TariffGroupId!, $evseId: EvseId!, $hasAnonymous: Boolean) {
      tariffs { detail(tariffGroupId: $tariffGroupId, evseId: $evseId, hasAnonymous: $hasAnonymous) {
        id name currency type alternativeText alternativeUrl
      } }
    }'''
    status,obj=post(q,{'tariffGroupId':evse['tariffGroupId'],'evseId':evse['evseId'],'hasAnonymous':True})
    tariff=(((obj.get('data') or {}).get('tariffs') or {}).get('detail')) if isinstance(obj,dict) else None
    return {
        'evseId':evse.get('evseId'),'evseIdentifier':evse.get('evseIdentifier'),'tariffGroupId':evse.get('tariffGroupId'),
        'status':status,'errors':errors(obj),'hasTariff':isinstance(tariff,dict),
        'tariff':{k:tariff.get(k) for k in ('id','name','currency','type','alternativeText','alternativeUrl')} if isinstance(tariff,dict) else None,
    }


def main():
    s=sample(); lat=s['latitude']; lon=s['longitude']; d=.02
    zone={'topLeft':{'latitude':lat+d,'longitude':lon-d},'bottomRight':{'latitude':lat-d,'longitude':lon+d}}

    q_v3='''query TccSearchV3($input: LocationSearchInputV3Input!) { chargePoints { locations { searchV3(input: $input) { __typename } } } }'''
    variants=[
        {'label':'zone_only','input':{'searchZone':zone}},
        {'label':'direct_non_roaming','input':{'searchZone':zone,'isRoaming':False}},
        {'label':'bump_or_partner_non_roaming','input':{'searchZone':zone,'isRoaming':False,'isBumpOrPartner':True}},
    ]
    attempts=[]
    for v in variants:
        status,obj=post(q_v3,{'input':v['input']})
        data=obj.get('data') if isinstance(obj,dict) else None
        attempts.append({'label':v['label'],'status':status,'errors':errors(obj),'hasData':data is not None,'typename':((((data or {}).get('chargePoints') or {}).get('locations') or {}).get('searchV3') or {}).get('__typename') if isinstance(data,dict) else None})

    q_search='''query TccSearch($input: LocationSearchInput!) {
      chargePoints { locations { search(input: $input) {
        locations {
          id name isRoaming
          coordinates { latitude longitude }
          evses { id identifier isRoaming tariffGroup { id } }
        }
      } } }
    }'''
    search_status,search_obj=post(q_search,{'input':{'searchZone':zone,'isRoaming':False}})
    search_errors=errors(search_obj)
    locations=((((search_obj.get('data') or {}).get('chargePoints') or {}).get('locations') or {}).get('search') or {}).get('locations') if isinstance(search_obj,dict) else []
    locations=locations if isinstance(locations,list) else []
    public_locations=[safe_location(x,lat,lon) for x in locations if isinstance(x,dict)]
    public_locations.sort(key=lambda x: x['distanceFromOfficialMeters'] if isinstance(x.get('distanceFromOfficialMeters'),(int,float)) else 10**12)

    exact=[]
    for loc in public_locations:
        for e in loc.get('evses') or []:
            if str(e.get('evseIdentifier') or '').casefold()==s['evseIdentifier'].casefold():
                exact.append({'location':loc,'evse':e})

    nearest=public_locations[0] if public_locations else None
    geo_match=nearest if nearest and isinstance(nearest.get('distanceFromOfficialMeters'),(int,float)) and nearest['distanceFromOfficialMeters'] <= 500 else None
    tariff_candidates=[]
    source='none'
    if exact:
        tariff_candidates=[exact[0]['evse']]; source='exact_interoperable_identifier'
    elif geo_match:
        tariff_candidates=[e for e in geo_match.get('evses') or [] if e.get('evseId') and e.get('tariffGroupId')]
        source='nearest_location_within_500m'

    tariff_attempts=[tariff_detail(e) for e in tariff_candidates[:12]]

    payload={
        'schemaVersion':'1.2.0',
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'method':{
            'unauthenticated':True,'publicReadOnlySearchOnly':True,'mutationsSent':False,
            'credentialsUsed':False,'personalDataQueried':False,'sampleFromOfficialBumpIrve':True,
        },
        'sample':s,'searchZone':zone,'attempts':attempts,
        'publicSearchSucceeded':any(a.get('typename') for a in attempts),
        'classicSearch':{
            'status':search_status,'errors':search_errors,'locationCount':len(public_locations),
            'locations':public_locations[:10],
            'exactOfficialEvseMatchCount':len(exact),
            'nearestLocationMatch':geo_match,
            'mappingSource':source,
        },
        'anonymousTariffDetails':tariff_attempts,
        'anonymousTariffSucceeded':any(x.get('hasTariff') for x in tariff_attempts),
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(payload,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
