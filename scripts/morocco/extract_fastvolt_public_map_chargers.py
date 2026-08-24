#!/usr/bin/env python3
import json,sys
from collections import Counter
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

def as_nonnegative_int(v):
    try:
        n=int(v)
        return n if n >= 0 else 0
    except Exception:
        return 0

def production_eligibility(x, lat, lon):
    charger_id=str(x.get('charger_id') or '').strip()
    charger_name=str(x.get('charger_name') or '').strip()
    label=str(x.get('label') or '').strip()
    if not charger_id:
        return False,'missing_charger_id'
    if not charger_name:
        return False,'missing_charger_name'
    if lat is None or lon is None:
        return False,'invalid_coordinates'
    lowered=' '.join((charger_id,charger_name,label)).lower()
    if charger_id.upper().startswith(('TEST','WTEST')) or charger_name.lower() in {'test','reserve'}:
        return False,'test_or_reserve_entry'
    connector_total=sum(as_nonnegative_int(x.get(k)) for k in ('ccs_count','chademo_count','type2_count'))
    if connector_total <= 0:
        return False,'no_declared_connectors'
    return True,None

report={
 'schema_version':3,
 'generated_at':datetime.now(timezone.utc).isoformat(),
 'source_url':URL,
 'country':'MA',
 'policy':{
   'read_only':True,'get_only':True,'no_login':True,'no_mutations':True,'no_session_start':True,
   'public_page_data_only':True,'raw_response_body_persisted':False,
   'allowed_value_keys':list(ALLOWED_VALUE_KEYS),
   'credentials_or_personal_data_persisted':False,
   'diagnostic_entries_retained':True
 },
 'modeling':{
   'cpo_operator':'FastVolt / Afrimobility',
   'site_brand':None,
   'app_source_access_network':'FastVolt public web map',
   'tariff_channel':'FastVolt direct',
   'status_source':None,
   'note':'Public raw fields brand/model/state are preserved as source fields only. brand is not promoted to site_brand and state is not promoted to live status without separate validation. Test/reserve or zero-connector entries remain in diagnostics but are excluded from production candidates.'
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
exclusion_reasons=Counter()
for x in chargers:
    if not isinstance(x,dict): continue
    lat,lon=coord_parts(x.get('geo_coordinates'))
    if lat is not None and lon is not None: valid_coords+=1
    production_candidate,exclusion_reason=production_eligibility(x,lat,lon)
    if exclusion_reason:
        exclusion_reasons[exclusion_reason]+=1
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
      'production_candidate':production_candidate,
      'production_exclusion_reason':exclusion_reason
    })
report['summary']={
 'charger_count':len(rows),
 'valid_coordinate_count':valid_coords,
 'item_schema_keys':all_keys,
 'production_candidate_count':sum(1 for x in rows if x['production_candidate']),
 'production_excluded_count':sum(1 for x in rows if not x['production_candidate']),
 'production_exclusion_reasons':dict(sorted(exclusion_reasons.items())),
 'with_max_output_count':sum(1 for x in rows if x.get('max_output') not in (None,'')),
 'with_ccs_count':sum(1 for x in rows if x.get('ccs_count') not in (None,'')),
 'with_type2_count':sum(1 for x in rows if x.get('type2_count') not in (None,'')),
 'with_chademo_count':sum(1 for x in rows if x.get('chademo_count') not in (None,'')),
 'with_address_count':sum(1 for x in rows if x.get('address_line_1') not in (None,'')),
 'raw_state_value_present_count':sum(1 for x in rows if x.get('state') not in (None,''))
}
report['chargers']=rows
json.dump(report,sys.stdout,ensure_ascii=False,indent=2); print()
