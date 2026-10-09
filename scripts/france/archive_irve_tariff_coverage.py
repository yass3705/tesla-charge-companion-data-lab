#!/usr/bin/env python3
"""Archive France tariff matching permanently: P1 exact / P2 published overlays / P3 independently verified.

This script RECOMPUTES using canonical IRVE dynamic+static, vetted direct CPO and
the Electra / Electroverse published tariff-overlay tiles. No price changes or V9
runtime writes. Full offers and per-EVSE classifications are stored in compressed,
lossless files, while indexed source evidence remains in versioned Data Lab.
"""
from __future__ import annotations
import argparse, contextlib, csv, datetime as dt, gzip, hashlib, io, json, os
import pathlib, runpy, sys
from collections import Counter, defaultdict

ROOT=pathlib.Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'reports/france/tariff-coverage'
SCHEMA='1.1.0'
LABELS=['CPO','CPO+Electra','CPO+Electroverse','CPO+Electra+Electroverse',
        'Electra','Electroverse','Electra+Electroverse','aucun_tarif_valide']
def dump(o):return json.dumps(o,ensure_ascii=False,separators=(',',':'),sort_keys=True,default=str)
def load(path):
 p=ROOT/path
 with (gzip.open(p,'rt',encoding='utf8') if p.suffix=='.gz' else p.open('r',encoding='utf8')) as h:return json.load(h)
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for data in iter(lambda:f.read(1048576),b''):h.update(data)
 return h.hexdigest()
@contextlib.contextmanager
def gztext(p):
 p=pathlib.Path(p)
 with p.open('wb') as raw:
  with gzip.GzipFile(filename='',mode='wb',compresslevel=8,fileobj=raw,mtime=0) as z:
   with io.TextIOWrapper(z,encoding='utf8',newline='\n') as txt:yield txt
def safe_integer(s):
 try:return int(s)
 except (TypeError,ValueError):return 0
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--out-dir',default=str(DEFAULT))
 ap.add_argument('--run-id',default=os.environ.get('GITHUB_RUN_ID') or 'local')
 ap.add_argument('--trigger',default=os.environ.get('GITHUB_EVENT_NAME') or 'manual')
 a=ap.parse_args()
 out=pathlib.Path(a.out_dir).resolve();out.mkdir(parents=True,exist_ok=True)
 s=runpy.run_path(str(ROOT/'scripts/audit_fr_three_priority_match_20261009.py'))
 base=s['base'];two=s['t'];active=s['active'];norm=s['norm']
 data=s['output'];rawCpo=base['cpo'];rawSourceCounts=base['per_source']
 e1,v1=s['E1'],s['V1'];e2,v2=s['E2'],s['V2'];e3=s['E3'];v3=s['V3_validated']
 stations=two['station'];station_by_id=base['station_by_pdc'];max_kw=base['power_by_pdc']
 if not (e1<=e2 and v1<=v2 and e2<=active and v2<=active):raise SystemExit('FAIL CLOSED: P1/P2 outside active scope')
 if data['countEVSEActive']!=len(active) or sum(data['levels']['P1_P2']['coverage'].values())!=len(active):
  raise SystemExit('FAIL CLOSED: IRVE totals and coverage do not reconcile')
 if data['priorityCounts']['Electra']['P3TechnicalCandidateAdditional']!=0 or data['priorityCounts']['Electroverse']['P3TechnicalCandidateAdditional']!=0:
  # P3 still candidates; preserve report but never promote implicitly.
  print('P3 audit candidates are not automatically published.',file=sys.stderr)
 def snapshot_path(p):return str(p.relative_to(ROOT))
 irveSrc=ROOT/'data/national/france-irve-static-v9/manifest.json'
 eManifest=ROOT/'data/platforms/electra/france/manifest.json'
 vManifest=ROOT/'data/platforms/electroverse/france-evse/manifest.json'
 provenance={'irveStatic':{'file':snapshot_path(irveSrc),'sha256':sha(irveSrc)},
             'irveDynamic':{'file':'data/national/france-irve-dynamic-status-v9.json.gz','generatedAt':base['dynamic'].get('generatedAt'),
               'sourceSha256':base['dynamic'].get('sourceSha256'),
               'snapshotSha256':sha(ROOT/'data/national/france-irve-dynamic-status-v9.json.gz')},
             'electraOverlay':{'file':snapshot_path(eManifest),'sha256':sha(eManifest),'generatedAt':load(snapshot_path(eManifest)).get('generatedAt')},
             'electroverseOverlay':{'file':snapshot_path(vManifest),'sha256':sha(vManifest),'generatedAt':load(snapshot_path(vManifest)).get('generatedAt')}}
 # Every priced offer, with exact published pricing JSON, identity-mode and tile provenance.
 offer_stats=Counter();offer_ids=defaultdict(lambda:defaultdict(list));modes=defaultdict(lambda:defaultdict(set))
 offer_file=out/'offers-latest.jsonl.gz'
 with gztext(offer_file) as f:
  for provider,directory in (('Electra','data/platforms/electra/france'),('Electroverse','data/platforms/electroverse/france-evse')):
   manifest=load(directory+'/manifest.json')
   accepted=e2 if provider=='Electra' else v2
   for tile in manifest.get('tiles') or []:
    for offer in load(directory+'/'+tile['file']).get('emspOffers') or []:
     ids={norm(v) for v in offer.get('evseIds') or [] if norm(v)}
     if len(ids)!=1:continue
     pdc=next(iter(ids))
     if pdc not in active or pdc not in accepted:continue
     mode=str((offer.get('metadata') or {}).get('identityMode') or 'unspecified')
     oid=str(offer.get('id') or '')
     row={'source':'eMSP','provider':provider,'irveEvseId':pdc,
          'matchTier':'P1' if pdc in (e1 if provider=='Electra' else v1) else 'P2',
          'identityMode':mode,'tileFile':directory+'/'+tile['file'],
          'rawPublishedOffer':offer}
     f.write(dump(row)+'\n')
     offer_stats[provider]+=1
     offer_ids[pdc][provider].append(oid)
     modes[pdc][provider].add(mode)
 assert len({k for k in offer_ids if k in active})<=len(active)
 # Materialized first-party CPO source rows. Where the source has generic tariff
 # scopes, source file path is the authoritative lookup, not a guessed EVSE rate.
 details=defaultdict(list)
 for file,group,id_field,price_field,validator in base['files']:
  try:
   for i,row in enumerate(load(file).get(group) or []):
    if not isinstance(row,dict):continue
    idv=norm(row.get(id_field))
    if idv not in active or file not in rawCpo.get(idv,set()):continue
    if validator and not validator(row):continue
    details[idv].append({'source':file,'sourceRow':i,'rawValidatedRow':row})
  except Exception as exc:raise SystemExit('FAIL CLOSED: CPO evidence extract '+file+': '+str(exc))
 # Additional CPO datasets with prices and EVSE keys, indexed by normalized ID.
 def attach(pdc,source,field,value,index=None):
  k=norm(pdc)
  if k in active and source in rawCpo.get(k,set()) and value is not None:
   details[k].append({'source':source,'sourceRow':index,'pricingField':field,'rawValidatedRow':value})
 for li,loc in enumerate(load('data/operator_direct/ionity_exact_france.json').get('stations') or []):
  for j,conn in enumerate(loc.get('connectors') or []):
   attach(conn.get('sourceEvseId'),'ionity_official_exact','connector',conn,[li,j])
 for i,row in enumerate(load('data/national/allego_direct_stations_france.json.gz').get('evses') or []):
  attach(row.get('evseId'),'allego_direct_exact','evse',row,i)
 for li,loc in enumerate(load('data/national/atlante_direct_stations_france_latest.json.gz').get('locations') or []):
  for j,conn in enumerate(loc.get('connectors') or []):
   attach(conn.get('evseId'),'atlante_first_party_ad_hoc','connector',conn,[li,j])
 for li,loc in enumerate(load('data/national/bump_direct_tariffs_graphql_france.json.gz').get('stations') or []):
  for j,row in enumerate((loc.get('match') or {}).get('points') or []):
   attach(row.get('idPdcItinerance'),'bump_graphql_evse_direct','point',row,[li,j])
 # For all other CPO-specific datasets (WAAT, Powerdot, national flat network):
 # canonical source references remain resolvable in the source repository and
 # capture manifests. Do not pretend a specific price was materialized.
 direct_details=out/'cpo-prices-latest.jsonl.gz'
 cpo_count=0;source_ref_only=0
 with gztext(direct_details) as f:
  for pdc in sorted(active):
   for source in sorted(rawCpo.get(pdc,set())):
    candidates=[d for d in details.get(pdc,[]) if d['source']==source]
    if not candidates:
     candidates=[{'source':source,'lookup':'canonical_source','tariffMaterializedInArchive':False}]
     source_ref_only+=1
    for row in candidates:
     f.write(dump({'irveEvseId':pdc,**row})+'\n');cpo_count+=1
 # Physical reference details and per-EVSE billing coverage. Power max IRVE used as group,
 # not as a substitute for individual connector tariff variants.
 physical={}
 for row in base['irve']:
  sid=str(row[0]);physical[sid]={'name':row[1],'address':row[2],
   'latitude':row[3],'longitude':row[4],'operator':row[5],
   'networkOrBrand':row[11] if len(row)>11 else None}
 evse_file=out/'evse-latest.jsonl.gz'
 observed=Counter();status_count=0
 with gztext(evse_file) as f:
  for pdc in sorted(active):
   station_id=station_by_id.get(pdc)
   labels=['CPO'] if rawCpo.get(pdc) else []
   if pdc in e2:labels.append('Electra')
   if pdc in v2:labels.append('Electroverse')
   group='+'.join(labels) if labels else 'aucun_tarif_valide'
   observed[group]+=1
   kw=max_kw.get(pdc)
   source_data={}
   for prov,exact,published in (('Electra',e1,e2),('Electroverse',v1,v2)):
    is_present=pdc in published
    source_data[prov]={'present':is_present,'matchTier':'P1' if pdc in exact else 'P2' if is_present else None,
      'identityModes':sorted(modes[pdc][prov]),'publishedOfferIds':offer_ids[pdc][prov],
      'offerCount':len(offer_ids[pdc][prov])}
   record={'evseIdNormalise':pdc,'status':'en_service','stationId':station_id,
    'station':physical.get(station_id),'nominalMaxPowerKw':kw,
    'powerGroup':('%g'%kw)+' kW' if kw else 'PUISSANCE_INCONNUE',
    'category':group,'cpo':{'hasDirectTariff':bool(rawCpo.get(pdc)),
      'directSourceFiles':sorted(rawCpo.get(pdc,set()))},
    'emsp':source_data,'priceDetailsFiles':['offers-latest.jsonl.gz','cpo-prices-latest.jsonl.gz']}
   f.write(dump(record)+'\n');status_count+=1
 if observed!=Counter(data['levels']['P1_P2']['coverage']):raise SystemExit('FAIL CLOSED: archived EVSE categories mismatch engine')
 if status_count!=len(active):raise SystemExit('FAIL CLOSED: archived EVSE row count mismatch IRVE active')
 now=dt.datetime.now(dt.timezone.utc)
 stamp=now.strftime('%Y-%m-%dT%H-%M-%SZ')
 hist_dir=out/'snapshots';hist_dir.mkdir(exist_ok=True)
 prior_file=out/'latest.json'
 try:
  previous=json.loads(prior_file.read_text(encoding='utf8')) if prior_file.exists() else None
 except (OSError,ValueError):
  raise SystemExit('FAIL CLOSED: previous archive summary is unreadable')
 summary={
  'schemaVersion':SCHEMA,'generatedAt':now.isoformat(),'githubRunId':str(a.run_id),'trigger':a.trigger,
  'status':'validated_audit_not_v9_published','p3PublishableNewEvses':0,
  'provenance':provenance,
  'metrics':{'irveActiveEVSE':len(active),'cpoDirectEVSE':len(rawCpo),
   'oneOrMoreTariff':len(active)-observed['aucun_tarif_valide'],
   'noValidTariff':observed['aucun_tarif_valide'],
   'ElectraPublishedEVSE':len(e2),'ElectroversePublishedEVSE':len(v2),
   'offersArchived':dict(offer_stats),'cpoEvidenceRowsArchived':cpo_count,
   'cpoSourceReferencesWithoutMaterializedRows':source_ref_only},
  'levels':data['levels'],
  'identityTierCounts':data['priorityCounts'],
  'matchDiagnostics':data['diagnostics'],
  'directCpoSourceCounts':{k:len(v) for k,v in sorted(rawSourceCounts.items())},
  'files':{'evse':'evse-latest.jsonl.gz','offers':'offers-latest.jsonl.gz',
    'cpoPricing':'cpo-prices-latest.jsonl.gz',
    'history':'history.jsonl',
    'historicalSummaries':'snapshots/',
    'script':'scripts/france/archive_irve_tariff_coverage.py'},
  'checksums':{'evse-latest.jsonl.gz':sha(evse_file),'offers-latest.jsonl.gz':sha(offer_file),
   'cpo-prices-latest.jsonl.gz':sha(direct_details)},
  'notes':['P1: direct normalized original EVSE reference','P2: overlay evidence retained, with published identityMode',
   'P3: new GPS candidates require independent physical CPO/address validation; not automatically promoted',
   'Static IRVE rows lacking explicit dynamic en_service are excluded, not classified as dead',
   'CPO direct source attribution is conservative and not nationally exhaustive',
   'Historical source snapshots remain recoverable via immutable Git commit SHA.']
 }
 if len(summary['levels']['P1_P2']['power'])<30:raise SystemExit('FAIL CLOSED: implausibly few power groups')
 if previous:
  old=previous.get('metrics',{})
  old_categories=(previous.get('levels',{}).get('P1_P2',{}) or {}).get('coverage',{})
  new_categories=summary['levels']['P1_P2']['coverage']
  summary['reviewDelta']={
   'previousReviewedAt':previous.get('generatedAt'),
   'previousGitHubRunId':previous.get('githubRunId'),
   'activeEVSE':summary['metrics']['irveActiveEVSE']-int(old.get('irveActiveEVSE') or 0),
   'withAnyTariff':summary['metrics']['oneOrMoreTariff']-int(old.get('oneOrMoreTariff') or 0),
   'withoutTariff':summary['metrics']['noValidTariff']-int(old.get('noValidTariff') or 0),
   'cpoDirect':summary['metrics']['cpoDirectEVSE']-int(old.get('cpoDirectEVSE') or 0),
   'electra':summary['metrics']['ElectraPublishedEVSE']-int(old.get('ElectraPublishedEVSE') or 0),
   'electroverse':summary['metrics']['ElectroversePublishedEVSE']-int(old.get('ElectroversePublishedEVSE') or 0),
   'byTariffCombination':{k:int(new_categories.get(k) or 0)-int(old_categories.get(k) or 0) for k in LABELS},
   'dynamicShaChanged':summary['provenance']['irveDynamic']['sourceSha256']!=(previous.get('provenance',{}).get('irveDynamic',{}).get('sourceSha256'))
  }
 else:summary['reviewDelta']={'previousReviewedAt':None,'firstBaseline':True}
 (out/'latest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 # A compact permanent snapshot for EACH successful verification. Git history
 # preserves old full detail files by commit SHA while 'latest' stays convenient.
 historical={'generatedAt':summary['generatedAt'],'githubRunId':summary['githubRunId'],
    'trigger':summary['trigger'],'provenance':provenance,'metrics':summary['metrics'],
    'reviewDelta':summary['reviewDelta'],
    'tiers':summary['identityTierCounts'],
    'fourCategories':{k:summary['levels'][k]['fourBuckets'] for k in ('P1','P1_P2','P1_P2_P3_allTechnicalCandidates')},
    'diagnostics':summary['matchDiagnostics'],'detailFileChecksums':summary['checksums']}
 historic_file=hist_dir/(stamp+'-run-'+re.sub('[^0-9A-Za-z_-]','',str(a.run_id))+'.json')
 historic_file.write_text(json.dumps(historical,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 with (out/'history.jsonl').open('a',encoding='utf8') as h:h.write(dump(historical)+'\n')
 print('COVERAGE_ARCHIVE_OK='+dump({'active':len(active),'anyTariff':summary['metrics']['oneOrMoreTariff'],
   'noTariff':summary['metrics']['noValidTariff'],'P1':summary['levels']['P1']['fourBuckets'],
   'P2':summary['levels']['P1_P2']['fourBuckets'],'P3New':0,
   'offersArchived':summary['metrics']['offersArchived'],'sourceEvidenceRows':cpo_count,
   'outputs':list(summary['files'].values()),'historicalFile':historic_file.name}))
if __name__=='__main__':
 import re
 main()
