#!/usr/bin/env python3
"""Inspect shape, availability and distributions of station technical metadata."""
import gzip,json,pathlib,collections,statistics,math
R=pathlib.Path(__file__).resolve().parents[1]
def load(path):
 with (gzip.open(R/path,'rt') if path.endswith('.gz') else open(R/path)) as f:return json.load(f)
irve=load('data/national/france-irve-static-v9/all.json.gz')
electra=load('data/platforms/electra/france/source-locations.json.gz')['locations']
evmanifest=load('data/electroverse/tariff_cache/manifest.json')
c=collections.Counter()
station_samples=[]
for r in irve:
 cfg=r[8] or []
 ids={str(pdc) for z in cfg for pdc in (z[6] if len(z)>6 and isinstance(z[6],list) else [])}
 c['irve_stations']+=1
 c['irve_stations_with_id']+=bool(ids)
 c['irve_stations_with_config']+=bool(cfg)
 c['irve_stations_with_many_powers']+=len({str(z[3]) for z in cfg if len(z)>3 and z[3]})>1
 c['irve_stalls_positive']+=any((z[4] if len(z)>4 else 0) for z in cfg)
 if len(station_samples)<4 and len(cfg)>1:station_samples.append({'station':r[0],'config':cfg[:5]})
ecounts=collections.Counter()
e_max=collections.Counter()
e_samples=[]
for loc in electra:
 evses=loc.get('evses') or []
 ecounts[len(evses)]+=1
 v=loc.get('maxPower')
 e_max[str(v)]+=1
 if len(e_samples)<8 and (len(evses)>3 or (v and v!=22)):
  e_samples.append({'id':loc.get('id'),'evseCount':len(evses),'maxPower':v,'connectorTypes':loc.get('connectorTypes'),'evseSample':evses[:2]})
es=collections.Counter()
ev_samples=[]
for sh in evmanifest['shards']:
 for loc in load('data/electroverse/tariff_cache/'+sh['file']).get('stations',{}).values():
  evs=((loc.get('tariff') or {}).get('evses') or [])
  es['locations']+=1
  es['locationEvses']+=len(evs)
  es['locationsWithEvses']+=bool(evs)
  es['locationWithAnyPower']+=any(any(c.get('kilowatts') is not None for c in e.get('connectors') or []) for e in evs)
  if len(ev_samples)<4 and len(evs)>0:
   ev_samples.append({'id':loc.get('electroverseLocationPk'),'count':len(evs),'evseSample':[{'physicalReference':x.get('physicalReference'),'pk':x.get('pk'),'connectorPower':[y.get('kilowatts') for y in x.get('connectors') or []]} for x in evs[:4]]})
print('STATION_TECHNICAL_SCHEMA='+json.dumps({'irve':c,'irveMultiConfigSamples':station_samples,'electraEvseCountDist':ecounts.most_common(16),'electraMaxPowerTop':e_max.most_common(28),'electraSamples':e_samples,'electroverse':es,'electroverseSamples':ev_samples},ensure_ascii=False,default=str)[:25000])
