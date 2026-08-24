#!/usr/bin/env python3
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

def classify(name, address, city, lat, lon):
    text=' '.join(str(x or '') for x in [name,address,city]).lower()
    if 'test' in text:
        return False,'test_record'
    if not (isinstance(lat,(int,float)) and isinstance(lon,(int,float))):
        return False,'missing_coordinates'
    if not (27.0 <= float(lat) <= 36.5 and -13.5 <= float(lon) <= -1.0):
        return False,'outside_morocco_bounds'
    return True,None

def main():
    raw=get_json(URL)
    count_doc=get_json(COUNT_URL)
    connector_count=count_doc.get('count') if isinstance(count_doc,dict) else None
    stations=[]
    for row in raw if isinstance(raw,list) else []:
        if not isinstance(row,dict): continue
        loc=row.get('location') if isinstance(row.get('location'),dict) else {}
        lat,lon=loc.get('latitude'),loc.get('longitude')
        prod,reason=classify(row.get('name'),row.get('address'),row.get('city'),lat,lon)
        cons=[]
        for c in row.get('connectors') or []:
            if isinstance(c,dict): cons.append({'type':c.get('type'),'power_kw':c.get('power')})
        stations.append({
            'id':row.get('id'),'name':row.get('name'),'address':row.get('address'),'city':row.get('city'),
            'latitude':lat,'longitude':lon,'status':row.get('status'),'connectors':cons,
            'production_candidate':prod,'production_exclusion_reason':reason,
            'cpo_operator':'Kilowatt','site_brand':None,
            'app_source_access_network':'Kilowatt public web map','tariff_channel':None,
            'status_source':'Kilowatt public web map'
        })
    prod=[s for s in stations if s['production_candidate']]
    status_counts=Counter(str(s.get('status')) for s in prod)
    connector_types=Counter(); powers=Counter()
    for s in prod:
        for c in s['connectors']:
            connector_types[str(c.get('type'))]+=1
            if isinstance(c.get('power_kw'),(int,float)): powers[str(c['power_kw'])]+=1
    rep={
      'schema_version':2,'generated_at':datetime.now(timezone.utc).isoformat(),'source':URL,
      'policy':{'read_only':True,'public_get_only':True,'no_login':True,'no_mutations':True,'public_station_fields_only':True},
      'modeling':{'cpo_operator':'Kilowatt','site_brand':'station-specific; not inferred','app_source_access_network':'Kilowatt public web map','tariff_channel':'unresolved unless station/native tariff evidence exists','status_source':'Kilowatt public web map'},
      'summary':{
        'raw_station_records':len(stations),'production_candidates':len(prod),'excluded_records':len(stations)-len(prod),
        'official_public_connector_count':connector_count,'status_counts_production':dict(status_counts),
        'connector_type_counts_production':dict(connector_types),'power_kw_counts_production':dict(powers),
        'website_location_claim':38,
        'reconciliation_status':'unresolved: API station records do not equal website location headline; do not force 47 records into 38 locations without client-side grouping evidence.'
      },
      'stations':stations
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(rep['summary'],indent=2,ensure_ascii=False))

if __name__=='__main__': main()
