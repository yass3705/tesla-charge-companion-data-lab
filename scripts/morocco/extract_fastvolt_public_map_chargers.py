#!/usr/bin/env python3
import json,sys
from datetime import datetime,timezone
from urllib.request import Request,urlopen

URL='https://www.fastvolt.net/api/pages'
UA='TeslaChargeCompanionDataLab/1.0 (+public read-only inventory)'
MAX_BYTES=1_000_000
ALLOWED_VALUE_KEYS=('charger_id','charger_name','geo_coordinates')

def find_chargers(data):
    carte=data.get('carte') if isinstance(data,dict) else None
    if not isinstance(carte,dict): return []
    for comp in carte.get('components') or []:
        if isinstance(comp,dict) and isinstance(comp.get('chargers'),list):
            return comp['chargers']
    return []

def coord_parts(v):
    if not isinstance(v,str): return None,None
    parts=[x.strip() for x in v.split(',')]
    if len(parts)!=2: return None,None
    try: return float(parts[0]),float(parts[1])
    except Exception: return None,None

report={
 'schema_version':1,
 'generated_at':datetime.now(timezone.utc).isoformat(),
 'source_url':URL,
 'country':'MA',
 'policy':{
   'read_only':True,'get_only':True,'no_login':True,'no_mutations':True,'no_session_start':True,
   'public_page_data_only':True,'raw_response_body_persisted':False,
   'allowed_value_keys':list(ALLOWED_VALUE_KEYS),
   'credentials_or_personal_data_persisted':False
 },
 'modeling':{
   'cpo_operator':'FastVolt / Afrimobility',
   'site_brand':None,
   'app_source_access_network':'FastVolt public web map',
   'tariff_channel':'FastVolt direct',
   'status_source':None,
   'note':'site_brand and live status are not inferred from the public map inventory.'
 }
}
req=Request(URL,headers={'User-Agent':UA,'Accept':'application/json,*/*;q=0.1'},method='GET')
with urlopen(req,timeout=20) as r:
    b=r.read(MAX_BYTES+1)
    report['http_status']=getattr(r,'status',200)
    report['content_type']=r.headers.get('Content-Type')
    report['truncated']=len(b)>MAX_BYTES
    data=json.loads(b[:MAX_BYTES].decode('utf-8','replace'))
chargers=find_chargers(data)
all_keys=sorted({str(k) for x in chargers if isinstance(x,dict) for k in x.keys()})
rows=[]
valid_coords=0
for x in chargers:
    if not isinstance(x,dict): continue
    lat,lon=coord_parts(x.get('geo_coordinates'))
    if lat is not None and lon is not None: valid_coords+=1
    rows.append({
      'charger_id':x.get('charger_id'),
      'charger_name':x.get('charger_name'),
      'geo_coordinates':x.get('geo_coordinates'),
      'latitude':lat,
      'longitude':lon,
      'cpo_operator':'FastVolt / Afrimobility',
      'site_brand':None,
      'app_source_access_network':'FastVolt public web map',
      'tariff_channel':'FastVolt direct',
      'status_source':None,
      'production_candidate': bool(x.get('charger_id') and x.get('charger_name') and lat is not None and lon is not None)
    })
report['summary']={
 'charger_count':len(rows),
 'valid_coordinate_count':valid_coords,
 'item_schema_keys':all_keys,
 'production_candidate_count':sum(1 for x in rows if x['production_candidate'])
}
report['chargers']=rows
json.dump(report,sys.stdout,ensure_ascii=False,indent=2); print()
