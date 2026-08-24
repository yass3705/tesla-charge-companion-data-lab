#!/usr/bin/env python3
"""Validate Kilowatt public station/count routes with GET only and persist schema/counts only."""
from __future__ import annotations
import hashlib, json, ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE='https://kilowatt.ma'
ROUTES=['/api/charging-stations','/api/public-connectors-count']
OUT=Path('reports/morocco/kilowatt/latest-public-station-route-probe.json')
UA='Mozilla/5.0 (compatible; TCC-DataLab-PublicReadOnly/1.0)'


def get(route):
    req=Request(BASE+route,headers={'User-Agent':UA,'Accept':'application/json,*/*;q=0.8'})
    with urlopen(req,timeout=25,context=ssl.create_default_context()) as r:
        b=r.read(8_000_000)
        return int(getattr(r,'status',200)),r.headers.get('Content-Type',''),b


def schema(v, depth=0):
    if depth>4: return type(v).__name__
    if isinstance(v,dict):
        return {str(k):schema(val,depth+1) for k,val in list(v.items())[:80]}
    if isinstance(v,list):
        return {'type':'list','count':len(v),'item_schema':schema(v[0],depth+1) if v else None}
    if v is None: return 'null'
    return type(v).__name__


def summarize_stationish(data):
    # Never persist raw station values here; only counts/key names/status vocabulary.
    seq=None
    if isinstance(data,list): seq=data
    elif isinstance(data,dict):
        for k in ['stations','data','results','items','chargingStations','charging_stations']:
            if isinstance(data.get(k),list): seq=data[k]; break
    out={}
    if seq is not None:
        out['record_count']=len(seq)
        keys=set(); status_values=set(); connector_counts=[]
        for row in seq[:500]:
            if not isinstance(row,dict): continue
            keys.update(map(str,row.keys()))
            for sk in ['status','state','availability']:
                val=row.get(sk)
                if isinstance(val,(str,int,float,bool)): status_values.add(str(val))
            for ck in ['connectors','evses','points','chargingPoints','charging_points']:
                val=row.get(ck)
                if isinstance(val,list): connector_counts.append(len(val))
        out['record_keys']=sorted(keys)
        out['status_vocabulary']=sorted(status_values)[:50]
        if connector_counts:
            out['nested_connector_total']=sum(connector_counts)
    return out


def main():
    rep={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'policy':{'read_only':True,'public_get_only':True,'no_login':True,'no_mutations':True,'raw_bodies_persisted':False,'station_values_persisted':False},'routes':[]}
    for route in ROUTES:
        item={'route':route}
        try:
            st,ct,b=get(route)
            item.update({'status':st,'content_type':ct,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
            try:
                data=json.loads(b.decode('utf-8','ignore'))
                item['json']=True
                item['schema']=schema(data)
                item['stationish_summary']=summarize_stationish(data)
                if route.endswith('public-connectors-count') and isinstance(data,(dict,list,int,float,str)):
                    # Persist only a scalar count or safe key/type information; never tokens.
                    if isinstance(data,(int,float)): item['public_connector_count']=data
                    elif isinstance(data,dict):
                        for k,v in data.items():
                            if 'count' in str(k).lower() and isinstance(v,(int,float)):
                                item.setdefault('count_fields',{})[str(k)]=v
            except Exception as e:
                item['json']=False; item['json_error_type']=type(e).__name__
        except Exception as e:
            item['error_type']=type(e).__name__
        rep['routes'].append(item)
    rep['summary']={
        'charging_stations_get_validated':any(x.get('route')=='/api/charging-stations' and x.get('status')==200 and x.get('json') for x in rep['routes']),
        'public_connectors_count_get_validated':any(x.get('route')=='/api/public-connectors-count' and x.get('status')==200 and x.get('json') for x in rep['routes'])
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(rep['summary'],indent=2))

if __name__=='__main__': main()
