#!/usr/bin/env python3
import gzip,json,pathlib,collections
R=pathlib.Path(__file__).resolve().parents[1]
def load(f):
 with (gzip.open(R/f,'rt',encoding='utf-8') if str(f).endswith('.gz') else (R/f).open()) as h:return json.load(h)
def offers(path):
 m=load(path+'/manifest.json');stats=collections.Counter();sample={};rows=collections.Counter();missing=collections.Counter()
 for tile in m.get('tiles') or []:
  d=load(path+'/'+tile['file'])
  for z in d.get('emspOffers') or []:
   meta=z.get('metadata') or {}
   mode=str(meta.get('identityMode') or '[NONE]')
   stats[mode]+=1
   if mode not in sample:sample[mode]={'id':z.get('id'),'evseIds':z.get('evseIds'),'powerKw':meta.get('powerKw'),'associationEvidence':meta.get('associationEvidence'),'physicalReference':meta.get('physicalReference'),'metadataKeys':list(meta.keys())}
   if z.get('verifiedScope'):rows[str(z.get('verifiedScope'))]+=1
   if meta.get('powerKw') is not None:missing['withPower']+=1
 print('GPS_MATCH_MODE_PROBE='+json.dumps({'overlay':path,'stats':stats,'offerScopes':rows,'meta':missing,'samples':sample},ensure_ascii=False))
offers('data/platforms/electra/france')
offers('data/platforms/electroverse/france-evse')
s=load('data/platforms/electra/france/source-locations.json.gz')
e=next((x for x in s['locations'] if x.get('chargeTariffs') and len(x.get('evses') or [])>1),s['locations'][0])
print('GPS_SOURCE_ELECTRA_SAMPLE='+json.dumps({'topKeys':list(e.keys()),'sample':e},ensure_ascii=False)[:6000])
ma=load('data/electroverse/irve_location_mapping.json')
print('GPS_SOURCE_EVR_MAPPING='+json.dumps({'topKeys':list(ma.keys()),'sample':ma.get('mappings',[])[:2]},ensure_ascii=False)[:4300])
ec=load('data/electroverse/tariff_cache/manifest.json')
print('GPS_SOURCE_EVR_CACHE_MANIFEST='+json.dumps({'keys':list(ec.keys()),'shards':ec.get('shards',[])[:1]},ensure_ascii=False)[:1900])
sh=load('data/electroverse/tariff_cache/'+ec['shards'][0]['file']);rows=sh.get('stations') or {}
sample=next(iter(rows.values()))
print('GPS_SOURCE_EVR_CACHE_SAMPLE='+json.dumps(sample,ensure_ascii=False)[:3900])
