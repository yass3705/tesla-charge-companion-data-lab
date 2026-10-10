#!/usr/bin/env python3
"""Permanently version the cross-country tariff census + France regression result.
Does not publish/alter production prices. Runs ONLY after successful tests.
"""
import datetime as dt,json,hashlib,os,pathlib,re
R=pathlib.Path(__file__).resolve().parents[1]
OUT=R/'reports/tariff-scenarios'
def read(x):return json.loads((OUT/x).read_text(encoding='utf8'))
def sha(x):return hashlib.sha256((OUT/x).read_bytes()).hexdigest()
def main():
 global_data=read('global-inventory-latest.json')
 fr=read('france-pricing-pilot-latest.json')
 runtime=read('france-runtime-offers-inventory.json')
 tesla=read('tesla-global-inventory-latest.json')
 tesla_pilot=read('tesla-global-pricing-pilot-latest.json')
 tesla_deep=read('tesla-complete-config-pricing-audit-latest.json')
 selection=read('tesla-source-selection-audit-latest.json')
 if not all(x.get('pass') for x in tesla_deep['checks']):raise SystemExit('Tesla full-configuration checks failed')
 duration_candidate=read('france-after-minutes-candidate-latest.json')
 if duration_candidate['status']!='staging_checks_pass':raise SystemExit('Unvalidated duration-fee candidate')
 if fr['status']!='synthetic_regressions_pass':raise SystemExit('Synthetic regression suite must pass before archive')
 if not global_data['sourceFilesScanned'] or not fr['samplesTested']:raise SystemExit('Empty inventory or regression')
 files=['global-inventory-latest.json','source-shapes-latest.json','france-real-offer-fixtures.json',
        'france-runtime-offer-fixtures.json','france-runtime-offers-inventory.json','france-pricing-pilot-latest.json',
        'tesla-global-inventory-latest.json','tesla-global-real-rule-fixtures.json',
        'tesla-global-pricing-pilot-latest.json','france-after-minutes-candidate-latest.json',
        'tesla-global-complete-config-fixtures.json','tesla-complete-config-pricing-audit-latest.json',
        'tesla-source-selection-audit-latest.json','tesla-source-selection-station-detail-latest.json']
 for f in files:
  if not (OUT/f).is_file():raise SystemExit('Missing '+f)
 timestamp=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')
 summary={
  'reviewedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
  'runId':os.environ.get('GITHUB_RUN_ID','local'),
  'referenceEngineSha':fr['enginePin'],
  'countries':global_data['scopeCountries'],
  'sourceFilesEnumerated':global_data['sourceFilesEnumerated'],
  'sourceFilesScanned':global_data['sourceFilesScanned'],
  'unscannedSourceFiles':global_data['sourceFilesSkipped'],
  'countrySourceCensus':global_data['countries'],
  'externalTeslaCatalogue':{'sha256':tesla['sourceSha256'],'reference':tesla['sourceRepository']+'@'+tesla['sourceRef'],
   'stationCount':tesla['sourceTotalStations'],'countries':tesla['countries'],'issues':tesla['issues']},
  'sourceFamilyCensus':global_data['globalFamilySourceCounts'],
  'teslaRealRulesSampled':tesla_pilot['fixtureCount'],
  'teslaCalculationRiskCounts':tesla_pilot['issues'],
  'teslaCompleteConfigurationAudit':{'configurations':tesla_deep['fixtureConfigurations'],
    'countries':tesla_deep['byCountry'],'reasons':tesla_deep['reasons']},
  'teslaLegacyLastUpdatedAge_NOT_PRICE_OBSERVATION':{k:v.get('legacyLastUpdatedAgeBuckets_NOT_OBSERVATION',{}) for k,v in tesla['countries'].items()},
  'teslaFreshnessSelection':{'stationCount':selection['macStationsAudited'],
       'byCountry':selection['countries'],'unmatchedSuCRecords':selection['unmatchedSuCRecords'],
       'policy':(selection.get('sourceSelectionPolicy') or selection['policy'])},
  'teslaTimeScopeAudit':{k:v.get('timeScopeAudit',{}) for k,v in tesla['countries'].items()},
  'franceOverlayOfferRows':{
    k:v for k,v in global_data['franceRealOfferRows'].items() if '/offer_rows' in k},
  'franceActualOffersSampled':fr['samplesTested'],
  'franceCohorts':fr.get('samplesByCohort',{}),
  'deterministicRegressionPassed':sum(x['pass'] for x in fr['syntheticCases']),
  'deterministicRegressionTotal':len(fr['syntheticCases']),
  'francePricingTypes':fr['pricingTypes'],
  'franceIncompleteReasons':fr['incompleteReasons'],
  'francePotentiallyUnmodeledFields':fr.get('unmodeledLegacyFields',{}),
  'franceAfterMinutesCandidate':duration_candidate['summary'],
  'franceAfterMinutesCandidateStatus':duration_candidate['status'],
  'sourceOutputSha256':{f:sha(f) for f in files},
  'policy':'Read-only structural country inventory and unchanged V9 pricing regression, not proof all EVSE have verified prices'}
 prior_file=OUT/'review-latest.json'
 prev=json.loads(prior_file.read_text(encoding='utf8')) if prior_file.exists() else None
 if prev:summary['delta']={'previousReviewedAt':prev.get('reviewedAt'),
    'sourceFilesScanned':summary['sourceFilesScanned']-prev.get('sourceFilesScanned',0),
    'franceActualOffersSampled':summary['franceActualOffersSampled']-prev.get('franceActualOffersSampled',0)}
 historydir=OUT/'snapshots';historydir.mkdir(parents=True,exist_ok=True)
 (OUT/'review-latest.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 stampFile=historydir/(timestamp+'-run-'+re.sub('[^a-zA-Z0-9_-]','',summary['runId'])+'.json')
 stampFile.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 with (OUT/'history.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(summary,ensure_ascii=False,separators=(',',':'))+'\n')
 print('GLOBAL_TARIFF_SCENARIO_ARCHIVE='+json.dumps({'file':str(stampFile.relative_to(R)), 'files':len(files),'countries':summary['countries'],'francePilotOffers':fr['samplesTested'],'potentiallyUnmodeledFields':summary['francePotentiallyUnmodeledFields']},ensure_ascii=False))
if __name__=='__main__':main()
