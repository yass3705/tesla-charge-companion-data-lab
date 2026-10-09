#!/usr/bin/env python3
"""GPS station matching sensitivity audit; no writes to source, no tariff exclusion.

Station = unique national IRVE station identifier.
Baseline = exact normalized EVSE / physicalReference -> globally unique IRVE PDC.
GPS fallback only for source locations without a baseline identity.
15/30/50m: unique candidate GPS vs GPS+matching normalized CPO, kept separate.
GPS matches are PROPOSALS not evidence-proven physical identity.
"""
from collections import defaultdict
from datetime import datetime, timezone
import gzip,json,math,pathlib,re
R=pathlib.Path(__file__).resolve().parents[1]
def read(p):
 with (gzip.open(R/p,'rt',encoding='utf-8') if p.endswith('.gz') else open(R/p,'r',encoding='utf-8')) as f:return json.load(f)
def txt(v):return str(v or '').strip()
def key(v):return re.sub(r'[^A-Z0-9]','',txt(v).upper())
def validcoord(lat,lon):
 try:
  a,b=float(lat),float(lon)
  return (a,b) if math.isfinite(a) and math.isfinite(b) and -90<=a<=90 and -180<=b<=180 else None
 except (ValueError,TypeError):return None
def haversine(a,b):
 p1,l1=a;p2,l2=b
 d1=math.radians(p2-p1);d2=math.radians(l2-l1)
 z=math.sin(d1/2)**2+math.cos(math.radians(p1))*math.cos(math.radians(p2))*math.sin(d2/2)**2
 return 12742000*math.asin(min(1,math.sqrt(z)))
def company_keys(names):
 return {key(v) for v in names if len(key(v))>=5 and key(v) not in ('INCONNU','UNKNOWN','NA','SANSNOM')}
def name_tokens(v):
 return set(re.findall(r'[A-Z0-9]{3,}',txt(v).upper()))
def station_location(loc,kind):
 if kind=='electra':
  c=loc.get('coordinates') or {}
  return validcoord(c.get('latitude'),c.get('longitude'))
 x=loc.get('electroverse') or {}
 return validcoord(x.get('lat'),x.get('lon'))

national=read('data/national/france-irve-static-v9/all.json.gz')
national_version=read('data/national/france-irve-static-v9/manifest.json').get('generatedAt')
irve={};pdcowners=defaultdict(set);grid=defaultdict(list)
CELL=.002
for row in national:
 sid=txt(row[0]);ll=validcoord(row[3],row[4])
 irve[sid]={'id':sid,'latlon':ll,'company':company_keys([row[5],row[11] if len(row)>11 else '']),'name':txt(row[1]),'address':txt(row[2])}
 for cfg in (row[8] or []):
  for pdc in (cfg[6] if isinstance(cfg,list) and len(cfg)>6 and isinstance(cfg[6],list) else []):
   if key(pdc):pdcowners[key(pdc)].add(sid)
 if ll:grid[(math.floor(ll[0]/CELL),math.floor(ll[1]/CELL))].append(sid)
pdc_unique={k:next(iter(ids)) for k,ids in pdcowners.items() if len(ids)==1}
radii=[15,30,50]
def candidates(ll,max_m=50):
 if ll is None:return []
 a,b=ll;ia,ib=math.floor(a/CELL),math.floor(b/CELL)
 # Conservative longitude expansion to account for smaller E-W distances at higher latitude.
 cx=max(1,math.ceil(max_m/(111195*CELL*max(.15,math.cos(math.radians(a))))))
 cy=max(1,math.ceil(max_m/(111195*CELL)))
 ids=set()
 for x in range(ia-cy,ia+cy+1):
  for y in range(ib-cx,ib+cx+1):ids.update(grid.get((x,y),[]))
 ds=[(haversine(ll,irve[s]['latlon']),s) for s in ids if irve[s]['latlon']]
 return sorted([(d,s) for d,s in ds if d<=max_m],key=lambda x:(x[0],x[1]))
def appraise(label,locations):
 exact=set();exact_loc=0;gps_count=0
 added={r:set() for r in radii}
 corroborated={r:set() for r in radii}
 details={r:defaultdict(int) for r in radii}
 evidence=[]
 for loc in locations:
  ids={pdc_unique[k] for k in [key(x) for x in loc['pdcRefs']] if k in pdc_unique}
  if ids:exact.update(ids);exact_loc+=1;continue
  ll=loc['coord']
  if ll is None:
   for r in radii:details[r]['missingCoordinates']+=1
   continue
  gps_count+=1
  near=candidates(ll,max(radii))
  for r in radii:
   inrange=[(d,s) for d,s in near if d<=r]
   if not inrange:details[r]['noNearbyIRVE']+=1;continue
   comp=loc['company'];cmp=[(d,s) for d,s in inrange if comp & irve[s]['company']]
   # GPS-only: an unmatched location must have precisely one IRVE station.
   if len(inrange)==1:
    added[r].add(inrange[0][1]);details[r]['uniqueGPSLocation']+=1
   else:details[r]['ambiguousGPSLocation']+=1
   # GPS+CPO: there must be exactly one geographically viable IRVE station
   # whose CPO matches a declared operator from source (CPO equality, no inference).
   if len(cmp)==1:
    corroborated[r].add(cmp[0][1]);details[r]['uniqueCpoBackedGPSLocation']+=1
   elif len(cmp)>1:details[r]['ambiguousCpoBackedGPSLocation']+=1
   else:details[r]['noCpoAgreement']+=1
   if r==30 and (len(inrange)>1 or len(cmp)==0) and len(evidence)<35:
    evidence.append({'source':label,'id':loc['id'],'name':loc['name'],'latlon':ll,'sourceCompany':sorted(comp),
      'nearbyIRVE':[{ 'id':s,'distanceM':round(d,1),'name':irve[s]['name'],'operator':sorted(irve[s]['company'])} for d,s in inrange[:7]],
      'cpoValidated':len(cmp)==1})
 return {'exact':exact,'gps_added':added,'gps_cpo':corroborated,'details':details,
         'matchedExactLocations':exact_loc,'missingExactLocationsWithGps':gps_count,'manualExamples':evidence}
electra_meta=read('data/platforms/electra/france/manifest.json')
e_raw=read('data/platforms/electra/france/source-locations.json.gz')
el=[{'id':txt(x.get('id')),'name':txt(x.get('name')),
 'pdcRefs':[e.get('evseId') for e in x.get('evses') or []],
 'coord':station_location(x,'electra'),
 'company':company_keys([(x.get('cpo') or {}).get('name'),(x.get('operator') or {}).get('name')])}
 for x in e_raw.get('locations') or []]
e=appraise('Electra eMSP',el)
ev_meta=read('data/electroverse/tariff_cache/manifest.json')
mapping={txt(m.get('electroverseLocationPk')):m for m in read('data/electroverse/irve_location_mapping.json').get('mappings') or []}
evl=[]
for sh in ev_meta['shards']:
 data=read('data/electroverse/tariff_cache/'+sh['file'])
 for pk,x in (data.get('stations') or {}).items():
  sid=txt(x.get('electroverseLocationPk') or pk)
  m=mapping.get(sid) or {}
  evl.append({'id':sid,'name':txt((m.get('irve') or {}).get('name')),
   'pdcRefs':[v.get('physicalReference') for v in ((x.get('tariff') or {}).get('evses') or [])],
   'coord':station_location(m,'electroverse'),
   # Mapping IRVE operator is a candidate's identity, not independent source CPO proof.
   'company':company_keys([(m.get('electroverse') or {}).get('operatorName')])})
v=appraise('Electroverse',evl)
out={
 'definition':'unique IRVE stations; ID intersection by alphanumeric-normalized globally unique EVSE/physicalReference; geographic fallback only for unmatched platform source locations. GPS-only and source-CPO-backed GPS are CANDIDATES, not verified identities.',
 'generatedAt':datetime.now(timezone.utc).isoformat(),
 'sourceDates':{'irve':national_version,'electra':electra_meta['generatedAt'],'electroverse':ev_meta['generatedAt']},
 'volumes':{'IRVE':len(irve),'ElectraEMSP':len(el),'ElectroverseCached':len(evl)},
 'baselineExact':{'IRVE_Electra':len(e['exact']),'IRVE_Electroverse':len(v['exact']),'allThree':len(e['exact']&v['exact'])},
 'sensitivity':{},
 'diagnostics':{
  'Electra':{'matchedExactLocations':e['matchedExactLocations'],'missingExactLocationsWithGps':e['missingExactLocationsWithGps']},
  'Electroverse':{'matchedExactLocations':v['matchedExactLocations'],'missingExactLocationsWithGps':v['missingExactLocationsWithGps']}
 },
 'sampleAmbiguities':(e['manualExamples'][:15]+v['manualExamples'][:15])
}
for r in radii:
 ea=e['exact']|e['gps_added'][r]
 va=v['exact']|v['gps_added'][r]
 ec=e['exact']|e['gps_cpo'][r]
 vc=v['exact']|v['gps_cpo'][r]
 out['sensitivity'][str(r)+'m']={
  'gpsUnique':{
   'IRVE_Electra':len(ea),'IRVE_Electroverse':len(va),'allThree':len(ea&va),
   'additionalIRVE_Electra':len(ea-e['exact']),'additionalIRVE_Electroverse':len(va-v['exact']),
   'additionalAllThree':len((ea&va)-(e['exact']&v['exact']))
  },
  'gpsWithMatchingSourceCpo':{
   'IRVE_Electra':len(ec),'IRVE_Electroverse':len(vc),'allThree':len(ec&vc),
   'additionalIRVE_Electra':len(ec-e['exact']),'additionalIRVE_Electroverse':len(vc-v['exact']),
   'additionalAllThree':len((ec&vc)-(e['exact']&v['exact']))
  },
  'sourceLocationDiagnostics':{'Electra':dict(e['details'][r]),'Electroverse':dict(v['details'][r])}
 }
print('GPS_STATION_SENSITIVITY_RESULT='+json.dumps({k:v for k,v in out.items() if k!='sampleAmbiguities'},ensure_ascii=False,separators=(',',':')))
outpath=R/'reports'/'station-overlap-gps-sensitivity-20261009.json'
outpath.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
