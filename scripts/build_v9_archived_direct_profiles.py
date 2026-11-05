#!/usr/bin/env python3
"""Replay preserved local compilers and attach their exact EVSE profiles, offline."""
import argparse,collections,copy,gzip,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_v9_archived_emsp import identity,sha
from v9_rebuild.canonical import key,validate
FAMILIES=('zewatt','zephyre')

def replay(family,work):
 work=work.resolve()
 if family not in FAMILIES:raise ValueError('Unknown archived compiler')
 script=ROOT/f'scripts/{family}/compile_{family}_v9_offers.mjs'
 source=ROOT/f'data/{family}/france/current/{family}.json.gz'
 compiled=ROOT/f'v9-production-runtime/data/v9/france-{family}-offers.json'
 target=work/(family+'.json')
 subprocess.run(['node',str(script),'--snapshot',str(source),'--out',str(target)],cwd=work,check=True,capture_output=True)
 old=json.loads(compiled.read_bytes());new=json.loads(target.read_bytes())
 if {k:v for k,v in old.items() if k!='generatedAt'}!={k:v for k,v in new.items() if k!='generatedAt'}:
  raise ValueError('Historical compiler output changed')
 snap=json.loads(gzip.decompress(source.read_bytes()))
 if family=='zephyre' and any(s.get('currency')!='EUR' or s.get('tariff',{}).get('currency')!='EUR' for s in snap['stations'] if s.get('multitenantDirectPaymentAvailable')):
  raise ValueError('Source currency must be explicit; compiler fallback is not evidence')
 return old,{'sourceSha256':sha(source.read_bytes()),'compiledSha256':sha(compiled.read_bytes()),
             'compilerSha256':sha(script.read_bytes()),'generatedAt':snap['generatedAt']}

def normalize(national,archives,provenance):
 if national.get('source',{}).get('id')!='FR:irve_static':raise ValueError('National reference required')
 byid=collections.defaultdict(list)
 for e in national['evses']:
  if e.get('officialEvseId'):byid[identity(e['officialEvseId'])].append(e)
 used={};offers=[];rejections=[];sid='FR:archived_direct_exact'
 for family,data in archives.items():
  if family not in FAMILIES or data.get('country')!='FR' or data.get('mode')!=f'verified_{family}_direct':raise ValueError('Archived profile contract invalid')
  seen=set()
  for raw in data['directOffers']:
   if (raw.get('verifiedScope')!='exact_evse' or raw.get('directOperatorOnly') is not True or raw.get('currency')!='EUR' or raw.get('countries')!=['FR'] or not raw.get('evseIds') or raw.get('stationIds') or raw['id'] in seen):raise ValueError('Non-exact or duplicate profile')
   seen.add(raw['id'])
   for official in raw['evseIds']:
    candidates=byid[identity(official)]
    if len(candidates)!=1:
     rejections.append({'family':family,'sourceOfferId':raw['id'],'sourceEvseId':official,'reason':'national_evse_absent' if not candidates else 'national_evse_ambiguous'});continue
    e=candidates[0];used[e['id']]=e
    offers.append({'id':key('FR',sid,'offer',[family,raw['id'],e['id']]),'channel':'Direct','scope':{'evseId':e['id'],'connectorId':None},
      'sourceOfferId':raw['id'],'sourceEvseId':official,'officialEvseId':e['officialEvseId'],'family':family,
      'proof':'identical_archived_direct_compiler_exact_evse','rawOffer':copy.deepcopy(raw),'calculationStatus':'not_evaluated'})
 # Conflicting same-provider profiles cannot compete by lowest price.
 groups=collections.defaultdict(list)
 for o in offers:groups[(o['family'],o['scope']['evseId'])].append(o)
 for rows in groups.values():
  if len({json.dumps(o['rawOffer']['pricing'],sort_keys=True) for o in rows})>1:
   for o in rows:o['calculationHold']='conflicting_direct_profiles_for_same_evse'
 stationids={e['stationId'] for e in used.values()};cpoids={e['cpoId'] for e in used.values()}
 national_sha=sha(json.dumps(national,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
 out={'schemaVersion':1,'source':{'id':sid,'nationalSemanticSha256':national_sha,'artifactSha256':sha((national_sha+json.dumps(provenance,sort_keys=True)).encode()),'generatedAt':min(p['generatedAt'] for p in provenance.values()),'archives':provenance},
 'countries':[{'code':'FR'}],'cpos':[c for c in national['cpos'] if c['id'] in cpoids],
 'stations':[s for s in national['stations'] if s['id'] in stationids], 'evses':list(used.values()),
 'connectors':[c for c in national['connectors'] if c['evseId'] in used],'offers':offers}
 validate(out)
 return out,{'attributedOffers':len(offers),'families':dict(collections.Counter(o['family'] for o in offers)),
             'rejectionCounts':dict(collections.Counter(r['reason'] for r in rejections)),'rejections':rejections,'provenance':provenance,'providerRequests':0}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--national',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists() or ROOT==a.out.resolve() or ROOT in a.out.resolve().parents:raise ValueError('New isolated output required')
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(dir=a.out.parent) as t:
  archives={};proof={}
  for f in FAMILIES:archives[f],proof[f]=replay(f,Path(t))
  out,report=normalize(json.loads(a.national.read_bytes()),archives,proof)
  a.out.mkdir();target=a.out/'FR__archived_direct_exact.json';target.write_text(json.dumps(out,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n')
  report['canonicalSha256']=sha(target.read_bytes());(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rejections'}))
