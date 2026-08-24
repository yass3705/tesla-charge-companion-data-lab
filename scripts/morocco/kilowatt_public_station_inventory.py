#!/usr/bin/env python3
"""Extract the public Kilowatt Morocco station inventory using GET only.

Only public station fields needed by TCC are persisted. No login, credentials,
user data, session actions or mutations are used.
"""
from __future__ import annotations
import json, ssl
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

URL='https://kilowatt.ma/api/charging-stations'
COUNT_URL='https://kilowatt.ma/api/public-connectors-count'
OUT=Path('reports/morocco/kilowatt/latest-public-station-inventory.json')
UA='Mozilla/5.0 (compatible; TCC-DataLab-PublicReadOnly/1.0)'


def get_json(url):
    req=Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    with urlopen(req,timeout=25,context=ssl.create_default_context()) as r:
        return json.loads(r.read(8_000_000).decode('utf-8'))


def main():
    raw=get_json(URL)
    count_doc=get_json(COUNT_URL)
    connector_count=count_doc.get('count') if isinstance(count_doc,dict) else None
    stations=[]
    for row in raw if isinstance(raw,list) else []:
        if not isinstance(row,dict):
            continue
        loc=row.get('location') if isinstance(row.get('location'),dict) else {}
        cons=[]
        for c in row.get('connectors') or []:
            if not isinstance(c,dict): continue
            cons.append({'type':c.get('type'),'power_kw':c.get('power')})
        stations.append({
            'id':row.get('id'),
            'name':row.get('name'),
            'address':row.get('address'),
            'city':row.get('city'),
            'latitude':loc.get('latitude'),
            'longitude':loc.get('longitude'),
            'status':row.get('status'),
            'connectors':cons,
            'cpo_operator':'Kilowatt',
            'site_brand':None,
            'app_source_access_network':'Kilowatt public web map',
            'tariff_channel':None,
            'status_source':'Kilowatt public web map',
        })
    coord_groups=Counter()
    for s in stations:
        lat,lon=s.get('latitude'),s.get('longitude')
        if isinstance(lat,(int,float)) and isinstance(lon,(int,float)):
            coord_groups[(round(float(lat),6),round(float(lon),6))]+=1
    status_counts=Counter(str(s.get('status')) for s in stations)
    connector_types=Counter()
    powers=Counter()
    for s in stations:
        for c in s['connectors']:
            connector_types[str(c.get('type'))]+=1
            if isinstance(c.get('power_kw'),(int,float)):
                powers[str(c['power_kw'])]+=1
    rep={
        'schema_version':1,
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'source':URL,
        'policy':{'read_only':True,'public_get_only':True,'no_login':True,'no_mutations':True,'public_station_fields_only':True},
        'modeling':{
            'cpo_operator':'Kilowatt',
            'site_brand':'station-specific; not inferred',
            'app_source_access_network':'Kilowatt public web map',
            'tariff_channel':'unresolved unless station/native tariff evidence exists',
            'status_source':'Kilowatt public web map'
        },
        'summary':{
            'station_records':len(stations),
            'unique_coordinate_locations':len(coord_groups),
            'official_public_connector_count':connector_count,
            'status_counts':dict(status_counts),
            'connector_type_counts':dict(connector_types),
            'power_kw_counts':dict(powers),
            'headline_reconciliation_note':'The public API exposes station records while the website separately exposes a connector/point count. Do not assume station_records equals locations or points.'
        },
        'stations':stations
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(rep['summary'],indent=2,ensure_ascii=False))

if __name__=='__main__': main()
