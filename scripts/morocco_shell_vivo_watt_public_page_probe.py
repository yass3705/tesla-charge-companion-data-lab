#!/usr/bin/env python3
"""Validate the public WATT Shell/Vivo operator page as secondary evidence only."""
from __future__ import annotations
import html
import json
import re
import urllib.request
from pathlib import Path

URL='https://map.watt.ma/operators/shell-vivo/'
OUT=Path('artifacts/morocco-shell-vivo-watt/summary.json')
EXPECTED=[
  {'name':'Shell Kenitra Safsaf','power_kw':50,'connectors':3},
  {'name':'Shell Benguerir','power_kw':22,'connectors':1},
  {'name':'Shell Mellousa','power_kw':22,'connectors':1},
  {'name':'Shell aire de repos Bouznika','power_kw':120,'connectors':2},
  {'name':'Shell Benguerir - Direction Casablanca','power_kw':7,'connectors':1},
  {'name':'Shell Amskroud','power_kw':22,'connectors':1},
  {'name':'Vivo Energy Shell Exit Casablanca','power_kw':22,'connectors':1},
]
req=urllib.request.Request(URL,headers={'User-Agent':'TeslaChargeCompanion-PublicReadOnlyProbe/1.0','Accept':'text/html'})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read().decode('utf-8',errors='replace')
    status=r.status
text=html.unescape(re.sub(r'<[^>]+>',' ',raw))
text=' '.join(text.split())
missing=[]
for row in EXPECTED:
    if row['name'].lower() not in text.lower():
        missing.append(row['name'])
out={
 'schema_version':1,
 'source_url':URL,
 'http_status':status,
 'policy':{
   'read_only':True,'http_method':'GET','credentials_used':False,'cookies_used':False,
   'secondary_aggregation_evidence_only':True,'do_not_infer_native_cpo':True,
   'do_not_infer_tariff':True,'do_not_infer_live_status':True
 },
 'watt_indexed_station_count':7,
 'stations':[
   {**r,'site_brand':'Shell','cpo_operator':'unresolved','app_source_access_network':'WATT.ma public map','tariff_channel':None,'status_source':None,'production_role':'diagnostic_corroboration_only'}
   for r in EXPECTED
 ],
 'all_expected_station_names_found':not missing,
 'missing_station_names':missing,
 'assessment':{
   'melloussa':'WATT adds secondary evidence for a Shell-branded EV charging listing, but does not resolve the existing native Shell-directory conflict or establish the physical CPO.',
   'completeness':'The seven WATT-indexed sites are not treated as a complete Morocco Shell Recharge inventory; official Al Jazira evidence exists separately and is not part of this WATT seven-site page.',
   'production_decision':'diagnostic_only'
 }
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'http_status':status,'stations':7,'all_names_found':not missing,'missing':missing},ensure_ascii=False))
