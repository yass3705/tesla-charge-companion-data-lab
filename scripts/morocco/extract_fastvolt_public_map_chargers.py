#!/usr/bin/env python3
import json,sys
from datetime import datetime,timezone
from urllib.request import Request,urlopen

URL='https://www.fastvolt.net/api/pages'
UA='TeslaChargeCompanionDataLab/1.0 (+public read-only inventory)'
MAX_BYTES=1_000_000
ALLOWED_VALUE_KEYS=(
 'charger_id','charger_name','geo_coordinates','address_line_1','address_line_2','city','zip_code',
 'brand','model','label','max_output','ccs_count','chademo_count','type2_count','state'
)

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
 'schema_version':2,
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
   'note':'Public raw fields brand/model/state are preserved as source fields only. brand is not promoted to site_brand and state is not promoted to live status without separate validation.'
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
    raw={k:x.get(k) for k in ALLOWED_VALUE_KEYS}
    rows.append({
      **raw,
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
 'production_candidate_count':sum(1 for x in rows if x['production_candidate']),
 'with_max_output_count':sum(1 for x in rows if x.get('max_output') not in (None,'')),
 'with_ccs_count':sum(1 for x in rows if x.get('ccs_count') not in (None,'')),
 'with_type2_count':sum(1 for x in rows if x.get('type2_count') not in (None,'')),
 'with_chademo_count':sum(1 for x in rows if x.get('chademo_count') not in (None,'')),
 'with_address_count':sum(1 for x in rows if x.get('address_line_1') not in (None,'')),
 'raw_state_value_present_count':sum(1 for x in rows if x.get('state') not in (None,''))
}
report['chargers']=rows
json.dump(report,sys.stdout,ensure_ascii=False,indent=2); print()
