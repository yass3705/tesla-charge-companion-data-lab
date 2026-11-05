#!/usr/bin/env python3
"""Restore archived eMSP overlays by their historical normalized exact EVSE identity.

No provider call, geography match or station creation. Unmatched/ambiguous offers
remain in the signed archive and a per-offer rejection ledger, never discarded.
"""
import argparse, collections, copy, gzip, hashlib, json, math, re, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v9_rebuild.canonical import key, validate

def sha(raw): return hashlib.sha256(raw).hexdigest()
def identity(value): return re.sub('[^A-Z0-9]','',str(value or '').strip().upper())
CONTRACTS={
 'Electroverse':('FR:emsp_exact','electroverse-france-evse-national-overlay','exact_unique_national_irve_pdc'),
 'Electra':('FR:electra_emsp_exact','electra-france-platform-national-evse-overlay','exact_national_irve_evse')}

def read_archive(folder,channel):
 raw=(folder/'manifest.json').read_bytes();m=json.loads(raw)
 if m.get('schemaVersion')!=1 or m.get('dataset')!=CONTRACTS[channel][1] or m.get('country')!='FR':raise ValueError('Archive identity mismatch')
 offers=[];seen=set()
 for tile in m.get('tiles',[]):
  name=tile.get('file')
  if not isinstance(name,str) or not re.fullmatch(r't_[0-9-]+_[0-9-]+\.json\.gz',name) or name in seen:raise ValueError('Invalid/duplicate tile')
  seen.add(name);data=(folder/name).read_bytes()
  if sha(data)!=tile.get('sha256') or len(data)!=tile.get('bytes'):raise ValueError('Tile integrity mismatch')
  payload=json.loads(gzip.decompress(data));rows=payload.get('emspOffers')
  if payload.get('schemaVersion')!=1 or payload.get('country')!='FR' or not isinstance(rows,list) or len(rows)!=tile.get('count'):raise ValueError('Tile internal count/schema mismatch')
  offers.extend(rows)
 if len(seen)!=m.get('tileCount'):raise ValueError('Incomplete tile set')
 locations={}
 if channel=='Electra':
  archive=(folder/'source-locations.json.gz').read_bytes()
  if sha(archive)!=m.get('sourceArchive',{}).get('sha256'):raise ValueError('Source archive SHA mismatch')
  payload=json.loads(gzip.decompress(archive));rows=payload.get('locations')
  if payload.get('country')!='FR' or not isinstance(rows,list) or len(rows)!=m['sourceArchive'].get('locationCount'):raise ValueError('Source archive internal count mismatch')
  for row in rows:
   for tariff in row.get('chargeTariffs',[]):
    if tariff.get('currency')!='EUR' or not tariff.get('elements') or not any(e.get('priceComponents') for e in tariff['elements']):raise ValueError('Source currency/components missing')
    for element in tariff['elements']:
     for component in element.get('priceComponents',[]):
      value=component.get('price')
      if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError('Invalid source component amount')
   if row['id'] in locations and locations[row['id']]!=row:locations[row['id']]=None
   elif row['id'] not in locations:locations[row['id']]=row
 return m,sha(raw),offers,locations

def normalize(national,channel,offers,provenance,locations=None):
 if national.get('source',{}).get('id')!='FR:irve_static':raise ValueError('National reference mismatch')
 source,_,mode=CONTRACTS[channel];by_id=collections.defaultdict(list)
 for row in national['evses']:
  if row.get('officialEvseId'):by_id[identity(row['officialEvseId'])].append(row)
 stations={r['id']:r for r in national['stations']};cpos={r['id']:r for r in national['cpos']}
 used={};accepted=[];rejected=[];holds=collections.Counter();groups=collections.defaultdict(list)
 for raw in offers:
  if not raw.get('id'):raise ValueError('Missing source offer ID')
  groups[raw['id']].append(raw)
 duplicates=0
 for group in groups.values():
  raw=group[0];meta=raw.get('metadata',{});ids=raw.get('evseIds');reason=None
  if any(row!=raw for row in group[1:]):
   rejected.append({'sourceOfferId':raw['id'],'sourceEvseIds':ids,'reason':'conflicting_duplicate_source_offer'});continue
  duplicates+=len(group)-1
  if raw.get('provider')!=channel or meta.get('verified') is not True:reason='unverified_provider_offer'
  elif meta.get('identityMode')!=mode:reason='historical_identity_method_requires_separate_proof'
  elif (raw.get('verifiedScope') if channel=='Electroverse' else meta.get('verifiedScope'))!='exact_evse':reason='scope_not_exact_evse'
  elif not isinstance(ids,list) or len(ids)!=1 or not identity(ids[0]):reason='invalid_source_evse_scope'
  else:
   matches=by_id.get(identity(ids[0]),[])
   if len(matches)!=1:reason='national_evse_absent' if not matches else 'national_evse_ambiguous'
  loc=None
  if not reason and channel=='Electra':
   loc=(locations or {}).get(meta.get('electraLocationId'))
   if not loc or sum(identity(e.get('evseId'))==identity(ids[0]) for e in loc.get('evses',[]))!=1:reason='source_evse_not_unique_in_archived_location'
  if reason:
   rejected.append({'sourceOfferId':raw['id'],'sourceEvseIds':ids,'identityMode':meta.get('identityMode'),'reason':reason});continue
  evse=matches[0];used[evse['id']]=evse
  row={'id':key('FR',source,'offer',(channel,raw['id'],evse['id'])),'channel':channel,
       'scope':{'evseId':evse['id'],'connectorId':None},'sourceOfferId':raw['id'],
       'sourceEvseId':ids[0],'officialEvseId':evse['officialEvseId'],
       'proof':'archived_unique_normalized_official_evse','rawOffer':copy.deepcopy(raw),
       'calculationStatus':'not_evaluated'}
  if loc:
   # The historical compiler did not preserve these non-empty restrictions.
   # Keep the attributed offer visible but prohibit a misleading partial total.
   omitted={'minKwh','maxKwh','startDate','endDate','minPower','maxPower'}
   unknown=[]
   known={'dayOfWeek','startTime','endTime','minDuration','maxDuration'}|omitted
   for t in loc.get('chargeTariffs',[]):
    for el in t.get('elements',[]):
     restrictions=el.get('restrictions') or {}
     kinds={pc.get('type') for pc in el.get('priceComponents',[])}
     for k,v in restrictions.items():
      if v not in (None,[], '') and (k in omitted or k not in known):unknown.append(k)
     if restrictions.get('dayOfWeek') and not (restrictions.get('startTime') or restrictions.get('endTime')):unknown.append('dayOfWeek_without_window')
     if restrictions.get('maxDuration') is not None and kinds!={'CONGESTION_TIME'}:unknown.append('maxDuration')
     if restrictions.get('minDuration') and not kinds.issubset({'TIME','PARKING_TIME','CONGESTION_TIME'}):unknown.append('minDuration_non_time_component')
   if unknown:row['calculationHold']='unpreserved_source_restrictions';row['sourceRestrictionFields']=sorted(set(unknown));holds[row['calculationHold']]+=1
  accepted.append(row)
 # A provider can repeat one national EVSE in different locations. Conflicting
 # complete tariffs for that same channel/EVSE must never compete by low price.
 by_target=collections.defaultdict(list)
 for row in accepted:by_target[row['scope']['evseId']].append(row)
 for rows in by_target.values():
  signatures={json.dumps(row['rawOffer'].get('pricing'),sort_keys=True) for row in rows}
  if len(signatures)>1:
   for row in rows:
    if row.get('calculationHold'):holds[row['calculationHold']]-=1
    row['calculationHold']='conflicting_tariffs_for_same_evse';holds[row['calculationHold']]+=1
 station_ids={e['stationId'] for e in used.values()};cpo_ids={stations[s]['cpoId'] for s in station_ids}
 result={'schemaVersion':1,'source':{'id':source,'artifactSha256':sha(json.dumps(provenance,sort_keys=True).encode()),**provenance},
  'countries':[{'code':'FR'}],'cpos':[cpos[c] for c in sorted(cpo_ids)],'stations':[stations[s] for s in sorted(station_ids)],
  'evses':sorted(used.values(),key=lambda r:r['id']),'connectors':[c for c in national['connectors'] if c['evseId'] in used],
  'offers':sorted(accepted,key=lambda r:r['id'])}
 validate(result)
 return result,{'source':source,'archiveOffers':len(offers),'identicalDuplicateRows':duplicates,'attributedOffers':len(accepted),'calculationHolds':dict(holds),'rejections':rejected,'rejectionCounts':dict(collections.Counter(r['reason'] for r in rejected))}

def build(national_path,folder,channel,out):
 root=Path(__file__).resolve().parents[1]
 if out.exists() or root==out.resolve() or root in out.resolve().parents:raise ValueError('New isolated output required')
 raw=national_path.read_bytes();m,msha,offers,locations=read_archive(folder,channel)
 result,report=normalize(json.loads(raw),channel,offers,{'nationalSha256':sha(raw),'archiveManifestSha256':msha,'generatedAt':m.get('generatedAt'),'identityContract':'historical_normalized_official_evse_unique'},locations)
 out.mkdir(parents=True);p=out/(CONTRACTS[channel][0].replace(':','__')+'.json')
 p.write_text(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n')
 report['canonicalSha256']=sha(p.read_bytes());report['provenance']=result['source']
 (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 return {k:v for k,v in report.items() if k!='rejections'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--national',required=True,type=Path);p.add_argument('--archive',required=True,type=Path);p.add_argument('--channel',required=True,choices=CONTRACTS);p.add_argument('--out',required=True,type=Path);a=p.parse_args();print(json.dumps(build(a.national,a.archive,a.channel,a.out)))
