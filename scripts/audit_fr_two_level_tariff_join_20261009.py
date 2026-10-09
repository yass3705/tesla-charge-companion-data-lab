#!/usr/bin/env python3
"""Classify active IRVE EVSE tariffs by two independently auditable match tiers.

L1: identical alphanumeric-normalized source EVSE and IRVE EVSE.
L2: for otherwise non-L1 published eMSP offers, source location matched uniquely
within <=10m, source and target have identical count of EVSE, maximum
station power within AC max(2kW,10%) or DC max(15kW,10%) tolerance,
and published tariff uniform across source location (else no indiscriminate broadcast).

All L2 evidence is a *candidate*: source operator/address manual verification
may remain necessary; do not publish to TCC from this audit.
"""
import runpy,collections,pathlib,json,math,re
R=pathlib.Path(__file__).resolve().parents[1]
base=runpy.run_path(str(R/'scripts/audit_fr_tariff_left_join_20261009.py'))
active=base['active'];cpo=set(base['cpo']);power_by_pdc=base['power_by_pdc'];station_by_pdc=base['station_by_pdc']
n=base['key'];load=base['load'];num=base['number']
national=base['irve'];D=base['dynamic']
pdc_stations=collections.defaultdict(set)
station={}
grid=collections.defaultdict(set)
CELL=.002
for row in national:
 sid=str(row[0]);cfgs=row[8] or []
 ev={}
 kinds={}
 for cfg in cfgs:
  kw=num(cfg[3] if len(cfg)>3 else None)
  kind=str(cfg[2] if len(cfg)>2 else '').upper()
  for x in (cfg[6] if len(cfg)>6 and isinstance(cfg[6],list) else []):
   k=n(x)
   if not k:continue
   ev[k]=max(ev.get(k,0),kw or 0)
   kinds[k]=kind
   pdc_stations[k].add(sid)
 coord=None
 try:
  la,lo=float(row[3]),float(row[4])
  if abs(la)<=90 and abs(lo)<=180 and math.isfinite(la+lo):coord=(la,lo)
 except (TypeError,ValueError):pass
 maxp=max(ev.values(),default=0)
 kind='DC' if any(x=='DC' for k,x in kinds.items() if ev[k]==maxp) else 'AC' if any(x=='AC' for k,x in kinds.items() if ev[k]==maxp) else 'DC' if maxp>=50 else 'UNKNOWN'
 station[sid]={'coord':coord,'ids':set(ev),'maxp':maxp,'kind':kind,'operator':str(row[5] or ''),'brand':str(row[11] if len(row)>11 else ''),'name':str(row[1] or ''),'address':str(row[2] or '')}
 if coord and set(ev)&active:
  grid[tuple(math.floor(z/CELL) for z in coord)].add(sid)
def distance(x,y):
 lat1,lon1,lat2,lon2=map(math.radians,(x[0],x[1],y[0],y[1]))
 h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
 return 12742000*math.asin(min(1,math.sqrt(h)))
def unique_near(x,threshold=10):
 if not x:return None
 try:
  lat,lon=map(float,x)
  if not math.isfinite(lat+lon):return None
 except (ValueError,TypeError):return None
 ia,ib=map(lambda q:math.floor(q/CELL),(lat,lon))
 ids=set()
 for i in range(ia-1,ia+2):
  for j in range(ib-1,ib+2):ids.update(grid.get((i,j),()))
 candidates=[(distance((lat,lon),station[s]['coord']),s) for s in ids if distance((lat,lon),station[s]['coord'])<=threshold]
 return candidates[0] if len(candidates)==1 else None
def power_ok(a,b,srcKind,tgtKind):
 if not a or not b:return False
 tolerance=max(2,.10*max(a,b))
 if srcKind=='DC' and tgtKind=='DC':tolerance=max(tolerance,15)
 return abs(a-b)<=tolerance
def rows(directory):
 manifest=load(directory+'/manifest.json')
 for tile in manifest.get('tiles') or []:
  yield from (load(directory+'/'+tile['file']).get('emspOffers') or [])
def classify(outsrc):
 exact=set()
 groups=collections.defaultdict(list)
 non_exact=collections.Counter()
 for offer in rows('data/platforms/'+outsrc+'/france' if outsrc=='electra' else 'data/platforms/electroverse/france-evse'):
  pricing=offer.get('pricing') or {}
  if not pricing.get('rules') and pricing.get('type') not in ('free','flatRate'):continue
  ids={n(x) for x in offer.get('evseIds') or []}
  if len(ids)!=1:continue
  k=next(iter(ids))
  if k not in active:continue
  m=offer.get('metadata') or {}
  mode=m.get('identityMode')
  physical=[m.get('physicalReference')]
  physical+=m.get('physicalReferences') or []
  if outsrc=='electra':
   direct=(mode=='exact_national_irve_evse')
   pk=str(m.get('electraLocationId') or '')
  else:
   direct=any(n(pr)==k and bool(n(pr)) for pr in physical)
   pk=str(m.get('electroverseLocationPk') or '')
  if direct:
   exact.add(k)
  else:
   non_exact[str(mode)]+=1
   groups[pk].append((k,offer))
 return exact,groups,non_exact
Eexact,Eg,Emodes=classify('electra')
Vexact,Vg,Vmodes=classify('electroverse')
assert Eexact<=base['electra'] and Vexact<=base['electroverse']
# Extract operational location evidence for derived-only offers
electra_source={str(x['id']):x for x in load('data/platforms/electra/france/source-locations.json.gz')['locations']}
evmap={str(x['electroverseLocationPk']):x for x in load('data/electroverse/irve_location_mapping.json')['mappings']}
# Cache source EVSE technical composition in one pass
ecache={}
manifest=load('data/electroverse/tariff_cache/manifest.json')
for shard in manifest['shards']:
 for pk,item in (load('data/electroverse/tariff_cache/'+shard['file']).get('stations') or {}).items():
  if str(pk) in Vg:
   ee=(item.get('tariff') or {}).get('evses') or []
   c=[y for e in ee for y in (e.get('connectors') or [])]
   powers=[num(y.get('kilowatts')) for y in c if num(y.get('kilowatts'))]
   top=max(powers,default=0)
   dc=any(any(s in str((y.get('standard') or {}).get('name') or '').upper() for s in ('CCS','COMBO','CHADEMO','DC')) and num(y.get('kilowatts'))==top for y in c)
   ac=any(any(s in str((y.get('standard') or {}).get('name') or '').upper() for s in ('T2','TYPE2','IEC_62196')) and num(y.get('kilowatts'))==top for y in c)
   ecache[str(pk)]={'count':len({str(e.get('pk') or e.get('physicalReference') or i) for i,e in enumerate(ee)}),'maxp':top,'kind':'DC' if dc else 'AC' if ac else 'DC' if top>=50 else 'UNKNOWN'}
diagnostics=collections.defaultdict(collections.Counter)
def accepted(mode,groups):
 accepted_ids=set();records=[]
 # Capture the number of sources that compete for the same station, after individual evidence qualification
 preliminary=collections.defaultdict(list)
 for pk,offers in groups.items():
  if not pk:continue
  target_ids={k for k,o in offers}
  station_ids={station_by_pdc.get(k) for k in target_ids}
  if len(station_ids)!=1:diagnostics[mode]['multipleTargetStations']+=1;continue
  sid=next(iter(station_ids));target=station[sid]
  if mode=='electra':
   src=electra_source.get(pk)
   if not src:diagnostics[mode]['missingSource']+=1;continue
   coord=(src.get('coordinates') or {})
   point=(coord.get('latitude'),coord.get('longitude'))
   n_source=len({str(x.get('id') or x.get('evseId') or i) for i,x in enumerate(src.get('evses') or [])})
   peak=(num(src.get('maxPower')) or 0)/1000
   names=' '.join(str(x).upper() for x in (src.get('connectorTypes') or []))
   srcKind='DC' if any(x in names for x in ('CCS','COMBO','CHADEMO','NACS')) or peak>=50 else 'AC' if 'TYPE2' in names or 'TYPE 2' in names else 'UNKNOWN'
   # curated source-side name/address evidence required, plus GPS max 10m.
   evidence=[(o.get('metadata') or {}).get('associationEvidence') or {} for k,o in offers]
   if any(float(e.get('nameAddressSimilarity') or 0)<.70 for e in evidence):
    diagnostics[mode]['nameAddressEvidenceMissing']+=1;continue
   if any(str((o.get('metadata') or {}).get('identityMode'))!='curated_irve_location' for k,o in offers):
    diagnostics[mode]['unclassifiedMode']+=1;continue
  else:
   src=ecache.get(pk);m=evmap.get(pk)
   if not src or not m:diagnostics[mode]['missingSource']+=1;continue
   point=((m.get('electroverse') or {}).get('lat'),(m.get('electroverse') or {}).get('lon'))
   n_source=src['count'];peak=src['maxp'];srcKind=src['kind']
   # Link independently to the same IRVE station; never treat a stale 15m map as 10m.
   if str(m.get('irveStationId'))!=sid:
    diagnostics[mode]['sourceMappingDifferentStation']+=1;continue
  near=unique_near(point)
  if not near or near[1]!=sid:diagnostics[mode]['notUniqueWithin10m']+=1;continue
  if n_source!=len(target['ids']) or not n_source:diagnostics[mode]['evseCountMismatch']+=1;continue
  if not power_ok(peak,target['maxp'],srcKind,target['kind']):diagnostics[mode]['powerMismatch']+=1;continue
  # Equal price for all derived PDCs within a station gives safe one-to-many broadcast,
  # otherwise per-EVSE cross-attribution requires extra proof (held back).
  tariffs={json.dumps(o.get('pricing'),sort_keys=True,separators=(',',':')) for k,o in offers}
  if len(tariffs)!=1:diagnostics[mode]['heterogeneousTariffAmbiguous']+=1;continue
  preliminary[sid].append((pk,target_ids,near[0],n_source))
  diagnostics[mode]['candidateSourceLocations']+=1
 # Avoid two nearby sources being assigned to same target with different tariffs
 for sid,items in preliminary.items():
  if len(items)!=1:
   diagnostics[mode]['multipleSourceLocationsSameStation']+=len(items);continue
  pk,ids,d,cnt=items[0]
  accepted_ids.update(ids)
  records.append({'stationId':sid,'sourceLocationId':pk,'distanceMeters':round(d,2),'activeTargetEvses':len(ids),'stationTotalEvses':cnt})
 diagnostics[mode]['validatedGpsSourceLocations']=len(records)
 diagnostics[mode]['validatedGpsTargetEvses']=len(accepted_ids)
 return accepted_ids,records
Egeo,Edetail=accepted('electra',Eg)
Vgeo,Vdetail=accepted('electroverse',Vg)
assert not (Egeo&Eexact) and not (Vgeo&Vexact)
labels=('CPO','CPO+Electra','CPO+Electroverse','CPO+Electra+Electroverse',
        'Electra','Electroverse','Electra+Electroverse','aucun_tarif_valide')
def tabulate(e,v):
 overall=collections.Counter();by_power=collections.defaultdict(collections.Counter)
 for k in active:
  state=tuple(name for present,name in ((k in cpo,'CPO'),(k in e,'Electra'),(k in v,'Electroverse')) if present)
  label='+'.join(state) if state else 'aucun_tarif_valide'
  overall[label]+=1
  power=power_by_pdc.get(k)
  p=('%g'%power)+' kW' if power else 'PUISSANCE_INCONNUE'
  by_power[p][label]+=1
 return overall,by_power
l1,p1=tabulate(Eexact,Vexact)
total,pt=tabulate(Eexact|Egeo,Vexact|Vgeo)
baseline,baselinePower=tabulate(base['electra'],base['electroverse'])
def table(by):
 return [{ 'powerKw':kw, **{label:by[kw][label] for label in labels},'activeEVSE':sum(by[kw].values())} for kw in sorted(by,key=lambda x:float(x.split()[0]) if x!='PUISSANCE_INCONNUE' else -1)]
output={
 'generatedAt':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
 'status':'AUDIT ONLY - GPS tariff matches not promoted to production',
 'base':'94,586 explicitly en_service IRVE EVSE in most recent snapshot (check actual count)',
 'sourceDates':base['output']['sourceSnapshotDates'],
 'tiers':{'level1':'normalized direct source EVSE ID equals IRVE PDC ID, except CPO tariff verified at network scope',
          'level2':'additional published eMSP tariff with source location unique within <=10m, exact whole station EVSE count, power match AC max(2kW,10%) and DC max(15kW,10%), and homogeneous source published tariff',
          'total':'set union of level1 and level2 for each platform; no double count; categories exclusive'},
 'scopes':{'IRVEActive':len(active),'cpo':len(cpo),'ElectraLevel1':len(Eexact),'ElectraLevel2Additional':len(Egeo),'ElectroverseLevel1':len(Vexact),'ElectroverseLevel2Additional':len(Vgeo),
           'ElectraTotal':len(Eexact|Egeo),'ElectroverseTotal':len(Vexact|Vgeo)},
 'level1':dict(l1),'level2AdditionalSourceEvidence':{'Electra':len(Egeo),'Electroverse':len(Vgeo)},
 'level2MarginalByCategory':{label:total[label]-l1[label] for label in labels},
 'total':dict(total),'previousBroadOverlayCoverage':dict(baseline),
 'unreviewedPublishedEmsps':{'Electra':len(base['electra']-(Eexact|Egeo)),'Electroverse':len(base['electroverse']-(Vexact|Vgeo))},
 'diagnostics':{k:dict(v) for k,v in diagnostics.items()},
 'topMissingExactIdentityModes':{'Electra':Emodes,'Electroverse':Vmodes},
 'byPowerLevel1':table(p1),'byPowerTotal':table(pt),
 'gpsExamples':{'Electra':Edetail[:50],'Electroverse':Vdetail[:50]},
 'cautions':['GPS tariff-only joins are candidates pending CPO and address validation; no production activation.',
             'If multiple powers have separate tariff scenarios, L2 is excluded unless their attribution is unambiguous.',
             'Previous broad overlay count uses prevalidated non-literal modes beyond 10m/strict station count; deliberately not silently assumed eligible for requested strict GPS tier.']
}
out=R/'reports/france/irve-tariff-two-level-left-join-20261009.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print('IRVE_TARIFF_TWO_LEVEL_RESULT='+json.dumps({k:v for k,v in output.items() if k not in ('byPowerLevel1','byPowerTotal','gpsExamples','topMissingExactIdentityModes')},ensure_ascii=False,separators=(',',':')))
print('IRVE_TARIFF_TWO_LEVEL_BY_POWER='+json.dumps([{ 'powerKw':r['powerKw'],'level1':{z:r[z] for z in labels[:4]},'total':{z:next(x for x in output['byPowerTotal'] if x['powerKw']==r['powerKw'])[z] for z in labels[:4]}} for r in output['byPowerLevel1']],ensure_ascii=False,separators=(',',':')))
