#!/usr/bin/env python3
"""Read-only global inventory of tariff source *shapes*, then actual France eMSP
pricing scenarios for the unchanged V9 pricing engine.

Not a national EVSE priced-coverage counter. Sources may be draft/staging, API
raw, CPO official fixed tariffs or published eMSP; never count a price field as
a verified ad-hoc public EVSE tariff without separate reconciliation.

Output path reports/tariff-scenarios/. No V9 production modifications.
"""
from __future__ import annotations
import collections,datetime as dt,gc,gzip,hashlib,json,os,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/tariff-scenarios'
COUNTRIES=['FR','IT','CH','DE','ES','NL','UK','MA','BE']
KEYWORDS={
 'energy':('priceperkwh','energy','kwh','consumptionrate','per_kwh','unitprice','unit_price','priceperkwh','eurperkwh','price_per_kwh','preckwh'),
 'connected_time':('connectedtime','priceperminute','perminute','timeprice','time_rate','timerate','chargeperminute','durationrate','rateperminute'),
 'parking_idle':('parking','idle','postcharge','post_charge','blocking','blockier','overtime','stayfee','stay_fee','occupation'),
 'congestion':('congestion','surcharge','soc80','occupationafter','overstay','over_stay'),
 'session_fixed':('connectionfee','connection_fee','sessionfee','session_fee','startfee','start_fee','fixedfee','flatfee','oneoff','one_off'),
 'minimum':('minimumsession','minimumtotal','minimumbill','min_charge','mincharge'),
 'tiered_duration':('durationbands','powerbands','timebands','startafter','afterfree','freetime','grace','thresholdminutes','perblock','blockminutes','billingstep'),
 'time_window':('starttime','endtime','days_of_week','daysofweek','hoursofoperation','timeofday','timerestriction','validfrom','validuntil','dynamicby'),
 'power_scope':('minpower','maxpower','powerkw','powerband','chargingpower','plugtype','connectorstandard','chargingtype'),
 'subscription':('subscription','membership','memberrate','planid','planprice','monthlyfee','abon','discount','electraplus'),
 'tax_currency':('currency','vat','tva','tax','includesvat'),
 'other_complex':('restrictions','componentgroups','conditionalsessionfees','rule','pricingmodel','elements','pricecomponents'),
}
COUNTRY_TOKENS={
 'FR':('france','french','fr'), 'IT':('italy','italia','italian','it'),
 'CH':('switzerland','swiss','ch'), 'DE':('germany','deutsch','de'),
 'ES':('spain','españa','spanish','es','reve'), 'NL':('netherlands','dutch','dotnl','nl'),
 'UK':('unitedkingdom','united_kingdom','britain','uk','gb'), 'MA':('morocco','maroc','ma'),
 'BE':('belgium','belgique','belgian','be')
}
ROOTS=[
 'data/operator_direct','data/national','data/platforms/electra/france',
 'data/platforms/electroverse/france-evse','data/switzerland','data/spain_reve',
 'data/belgium','data/loadmotion','data/greenspot','data/gofast','data/atlante',
 'data/adhoc_payment','data/tariff_history','data/qovoltis','data/zewatt',
 'data/publish','data/tcc_v9','data/seed','reports/morocco','v9-production-runtime/data/v9'
]
MAX_DECOMPRESSED=75_000_000
MAX_VISIT=8000
MAX_SAMPLES_PER_FAMILY=80
def jdump(obj):return json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n'
def norm(v):return re.sub('[^a-z0-9]','',str(v or '').lower())
def family(k):
 s=norm(k)
 hits=set()
 for f,words in KEYWORDS.items():
  if any(norm(w) in s for w in words):hits.add(f)
 return hits
def countries_for(path,obj):
 s=str(path).lower();tokens=set(re.split(r'[^a-z0-9]+',s))
 result=set()
 for cc,words in COUNTRY_TOKENS.items():
  if any(w in tokens for w in words):result.add(cc)
 if not result:
  x=obj.get('countryCode') or obj.get('country') or obj.get('country_code') if isinstance(obj,dict) else None
  if isinstance(x,str):
   val=x.strip().upper();result.update([cc for cc in COUNTRIES if cc==val])
 if not result and s.startswith('data/operator_direct/'):
  # A number of official FR datasets omit the FR suffix; keep explicit unknown.
  return ['UNSPECIFIED']
 return sorted(result) if result else ['UNSPECIFIED']
def stage(path,doc):
 s=str(path).lower()
 if 'candidate' in s or 'staging' in s or 'probe' in s or 'residual' in s:return 'candidate_or_staging'
 if s.startswith('reports/') or s.startswith('data/seed/'):return 'research_or_manual_observation_not_tariff_validated'
 if 'manifest' in s or 'report' in s or 'status' in s or 'index' in s:return 'metadata_or_status'
 if '/platforms/' in s and '/france/' in s or '/france-evse/' in s:return 'validated_emsp_overlay'
 if '/operator_direct/' in s or 'direct' in s or 'official' in s:return 'cpo_direct_source_unconfirmed_scope'
 if '/tariff_cache/' in s or '/pages/' in s or 'raw' in s:return 'raw_source_unverified'
 if '/data/v9/' in s or '/tcc_v9/' in s:return 'runtime_candidate'
 return 'source_dataset_unclassified'
def load(path):
 # Fail closed on enormous raw data instead of silently running out of memory.
 size=path.stat().st_size
 if size>MAX_DECOMPRESSED:return None,'oversize_compressed'
 with (gzip.open(path,'rb') if path.name.endswith('.gz') else path.open('rb')) as f:
  raw=f.read(MAX_DECOMPRESSED+1)
 if len(raw)>MAX_DECOMPRESSED:return None,'oversize_decompressed'
 try:return json.loads(raw),None
 except (UnicodeError,ValueError) as e:return None,'invalid_json_'+str(e)[:65]
def scan(doc):
 """
 Bounded structural census. Count occurrences in inspected nodes ONLY, keep a
 denominator and mark sampling, never pretend nested counts = tariff count.
 """
 queue=collections.deque([(doc,0)]);inspected=0;sampled=False
 fields=collections.Counter();fam=collections.Counter();pricing=collections.Counter()
 examples=collections.defaultdict(list);nestedlist=collections.Counter()
 while queue and inspected<MAX_VISIT:
  value,depth=queue.popleft();inspected+=1
  if depth>10:sampled=True;continue
  if isinstance(value,list):
   nestedlist['arrays']+=1
   if len(value)>200:sampled=True
   # Inspect first, evenly spaced and last elements (never claim exhaustive).
   idx=list(range(min(len(value),12)))
   if len(value)>12:idx+=sorted({i*(len(value)-1)//11 for i in range(12)})
   if len(value)>100:idx+=sorted({i*(len(value)-1)//19 for i in range(20)})
   for i in sorted(set(idx)):queue.append((value[i],depth+1))
  elif isinstance(value,dict):
   nestedlist['objects']+=1
   for k,v in value.items():
    fields[str(k)]+=1
    for name in family(k):
     fam[name]+=1
     if len(examples[name])<8 and str(k) not in examples[name]:examples[name].append(str(k))
    if k in ('pricing','tariff','directAdHoc') and isinstance(v,dict):
     x=v.get('type')
     if x:pricing[str(x)]+=1
    if isinstance(v,(dict,list)):queue.append((v,depth+1))
 if queue:sampled=True
 return {'sampled':sampled,'inspectedNodes':inspected,'families':dict(fam),
         'pricingTypes':dict(pricing),'exampleFieldNames':dict(examples),
         'dominantFieldNames':[k for k,_ in fields.most_common(30)],
         'objectsVisited':nestedlist['objects'],'arraysVisited':nestedlist['arrays']}
def source_rows():
 for root in ROOTS:
  d=ROOT/root
  if not d.exists():continue
  for p in sorted(d.rglob('*')):
   if not p.is_file() or not (p.name.endswith('.json') or p.name.endswith('.json.gz')):continue
   # France Electra/Electroverse offer tiles are exhaustively read below in
   # france_samples(). Avoid reading their 649 tiles twice for generic schemas.
   if 'data/platforms/' in str(p) and re.fullmatch(r't_[0-9_]+[.]json[.]gz',p.name):continue
   yield p
def path_key(path):return str(path.relative_to(ROOT))
def france_samples():
 """Full count of priced overlay rows + bounded deterministic samples of real FR offers.
 No synthetic fixture is ever labeled a real source record.
 """
 files=[
 ('Electra eMSP','data/platforms/electra/france'),
 ('Electroverse eMSP','data/platforms/electroverse/france-evse')
 ]
 output=[];stats=collections.Counter();variants=collections.defaultdict(list)
 for provider,directory in files:
  manifest=json.loads((ROOT/directory/'manifest.json').read_text())
  for tile in manifest.get('tiles') or []:
   p=ROOT/directory/tile['file']
   try:
    with gzip.open(p,'rt',encoding='utf8') as f:payload=json.load(f)
   except (OSError,ValueError) as exc:
    stats[provider+'/tile_failed']+=1;continue
   for offer in payload.get('emspOffers') or []:
    pricing=offer.get('pricing') or {}
    if not isinstance(pricing,dict):stats[provider+'/missing_pricing']+=1;continue
    typ=str(pricing.get('type') or ('rules' if pricing.get('rules') else 'unknown'))
    rules=pricing.get('rules') or []
    fieldnames=set()
    for rule in rules:
     if isinstance(rule,dict):fieldnames.update(k for k in rule if rule[k] is not None)
    for group in pricing.get('componentGroups') or []:
     fieldnames.add('componentGroups')
     for rule in group.get('rules') or []:
      if isinstance(rule,dict):fieldnames.update(k for k in rule if rule[k] is not None)
    fam=set().union(*(family(k) for k in set(pricing)|fieldnames))
    if any(r.get('ocpiDurationBands') for r in rules if isinstance(r,dict)):fam.add('tiered_duration')
    if any(r.get('congestionTimePerMinute') is not None for r in rules if isinstance(r,dict)):fam.add('congestion')
    if any(r.get('scope') not in (None,'allDay') for r in rules if isinstance(r,dict)):fam.add('time_window')
    if any(r.get('pricePerKwh') is not None for r in rules if isinstance(r,dict)):fam.add('energy')
    if any(r.get('chargingTimePerMinuteEur') is not None or r.get('chargePerMinute') is not None for r in rules if isinstance(r,dict)):fam.add('connected_time')
    if any(r.get('pricePerMinute') is not None or r.get('connectedTimePerMinuteEur') is not None for r in rules if isinstance(r,dict)):fam.add('connected_time')
    stats[provider+'/offer_rows']+=1;stats[provider+'/pricing_type/'+typ]+=1
    for x in fam:stats[provider+'/family/'+x]+=1
    signature=provider+'|'+typ+'|'+','.join(sorted(fam))+'|'+','.join(sorted(fieldnames))
    stats[provider+'/signature/'+hashlib.sha1(signature.encode()).hexdigest()[:12]]+=1
    if len(variants[signature])<MAX_SAMPLES_PER_FAMILY:
     variants[signature].append({'provider':provider,'offerId':offer.get('id'),
       'tariffType':typ,'families':sorted(fam),'identityMode':(offer.get('metadata') or {}).get('identityMode'),
       'targetEvseIds':offer.get('evseIds'), 'offer':offer})
 for sig,arr in sorted(variants.items()):
  # Coverage per signature kept; samples capped to bound CI and storage.
  sample_id=hashlib.sha1(sig.encode()).hexdigest()[:12]
  for item in arr:
   item['signatureId']=sample_id
   output.append(item)
 return output,stats,dict(collections.Counter({hashlib.sha1(k.encode()).hexdigest()[:12]:len(v) for k,v in variants.items()}))
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 rows=[];bycountry=collections.defaultdict(lambda:collections.Counter())
 globalfamilies=collections.Counter(); skipped=collections.Counter()
 for file_index,path in enumerate(source_rows()):
  rel=path_key(path);doc,error=load(path)
  if error:
   result={'file':rel,'sizeBytes':path.stat().st_size,'status':'unreadable_or_skipped','reason':error,
          'country':countries_for(rel,{}),'stage':stage(rel,{})}
   rows.append(result);skipped[error]+=1;continue
  header=doc if isinstance(doc,dict) else {}
  result={'file':rel,'sizeBytes':path.stat().st_size,'status':'scanned',
   'country':countries_for(rel,header),'stage':stage(rel,header),
   'declaredCountry':header.get('countryCode') or header.get('country') if isinstance(header,dict) else None,
   'schemaVersion':header.get('schemaVersion') if isinstance(header,dict) else None,
   'declaredPublished':header.get('publishedToTcc',header.get('publishesToTcc')) if isinstance(header,dict) else None,
   'topLevelType':'dict' if isinstance(doc,dict) else 'list' if isinstance(doc,list) else type(doc).__name__,
   'topLevelKeys':list(header)[:70] if isinstance(header,dict) else None,
   'topLevelCount':len(doc) if isinstance(doc,list) else None,
   'structuralScan':scan(doc)}
  rows.append(result)
  for cc in result['country']:
   bycountry[cc]['files_scanned']+=1
   for fam in result['structuralScan']['families']:
    bycountry[cc]['source_files_with_'+fam]+=1
  for fam in result['structuralScan']['families']:globalfamilies[fam]+=1
  del doc
  if file_index%25==0:gc.collect()
 samples,frstats,samplecounts=france_samples()
 (OUT/'france-real-offer-fixtures.json').write_text(jdump(samples),encoding='utf8')
 (OUT/'source-shapes-latest.json').write_text(jdump(rows),encoding='utf8')
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 countries={k:dict(v) for k,v in sorted(bycountry.items())}
 # Include each TCC country even if no local price source was found.
 for cc in COUNTRIES:countries.setdefault(cc,{})
 summary={'schemaVersion':'1.0','generatedAt':now,'scopeCountries':COUNTRIES,
  'method':'Repository file / structural schema census, not a claim of eligible EVSE pricing coverage.',
  'sourceRoots':ROOTS,'sourceFilesEnumerated':len(rows),
  'sourceFilesScanned':sum(x['status']=='scanned' for x in rows),
  'sourceFilesSkipped':dict(skipped),'countries':countries,
  'globalFamilySourceCounts':dict(globalfamilies),
  'franceRealOfferRows':dict(frstats),'franceFixtureSampleCount':len(samples),
  'franceFixtureSignatures':samplecounts,
  'priorityFrance':'initial calculation regression after global structural census',
  'interpretation':{'source_file_with_field':'not equal to a validated EVSE tariff',
   'overlays':'Electra/Electroverse published eMSP source, not the CPO direct price',
   'stage':'candidate/staging raw rates must not be included in production comparisons',
   'sampling':'only France published eMSP offers fully enumerated; nested schema scan samples wide arrays and is marked sampled',
   'large_json':'oversize files listed with reason, not silently counted as scanned'},
  'outputs':{'sourceShapes':'source-shapes-latest.json','franceRealOfferFixtures':'france-real-offer-fixtures.json'}}
 (OUT/'global-inventory-latest.json').write_text(jdump(summary),encoding='utf8')
 print('GLOBAL_TARIFF_INVENTORY='+json.dumps({'files':len(rows),'scanned':summary['sourceFilesScanned'],
  'skipped':dict(skipped),'countrySummary':{k:v.get('files_scanned',0) for k,v in countries.items()},
  'familyCounts':summary['globalFamilySourceCounts'],
  'franceRealSamples':len(samples),
  'franceOfferRows':{k:v for k,v in frstats.items() if '/offer_rows' in k},
  'francePricingTypes':{k:v for k,v in frstats.items() if '/pricing_type/' in k}},ensure_ascii=False))
if __name__=='__main__':main()
