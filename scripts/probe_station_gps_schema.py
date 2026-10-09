#!/usr/bin/env python3
import gzip,json,pathlib
R=pathlib.Path(__file__).resolve().parents[1]
def read(p):
 with (gzip.open(R/p,'rt') if p.endswith('.gz') else open(R/p)) as f:return json.load(f)
n=read('data/national/france-irve-static-v9/all.json.gz')
e=read('data/platforms/electra/france/source-locations.json.gz')['locations']
m=read('data/electroverse/irve_location_mapping.json')['mappings']
c=read('data/electroverse/tariff_cache/shard-000.json')
stations=list(c['stations'].values())
print('GPS_SCHEMA_SAMPLES='+json.dumps({'irve':n[:2], 'electra':[dict((k,v) for k,v in x.items() if k in ['id','name','coordinates','operator','cpo','postalCode','city','evses']) for x in e[:1]],'mapping':m[:2],'cache':[dict((k,v) for k,v in x.items() if k!='tariff') for x in stations[:2]]},ensure_ascii=False,default=str)[:16000])
