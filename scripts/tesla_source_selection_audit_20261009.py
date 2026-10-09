#!/usr/bin/env python3
"""Tesla per-station Mac/SuC precedence with VERIFIED provenance categories.

IMPORTANT: legacy lastUpdated in stable/data/tesla_stations.json is NOT a price
observation timestamp (the October 2026 Mac country batches changed tariffs
without refreshing this field). Never treat it as such.
This workflow is read-only; no V9 publication.
"""
from __future__ import annotations
import collections,datetime as dt,json,pathlib,re,sys,urllib.request
import tesla_global_tariff_inventory_20261009 as inv
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent/'suc_tracker'))
from core import mac_key,station_schedule,parse_date

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/tariff-scenarios'
SUC=ROOT/'data/suc-tracker/tesla_stations.json'
META=ROOT/'data/suc-tracker/metadata.json'
COUNTRIES=['FR','IT','CH','DE','ES','NL','UK','MA','BE']
BATCH_NAMES={
 'france':'FR','italy':'IT','switzerland':'CH','germany':'DE',
 'spain':'ES','netherlands':'NL','united_kingdom':'UK',
 'belgium':'BE','morocco':'MA',
}
GITHUB_COMMITS_URL=(
 'https://api.github.com/repos/yass3705/tesla-charge-companion-stable/commits'
 '?path=data%2Ftesla_stations.json&per_page=35'
)

def time_or_none(value):
    try:return parse_date(value)
    except (ValueError,TypeError):return None

def canonical_country(cc):return 'UK' if str(cc)=='GB' else str(cc)

def batch_publications():
    request=urllib.request.Request(GITHUB_COMMITS_URL,headers={
        'User-Agent':'TCC-Tesla-Price-Provenance/1.0','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=35) as response:
        raw=response.read(750_000)
    data=json.loads(raw)
    if not isinstance(data,list) or not data:raise ValueError('GitHub commit list unavailable')
    batches={}
    for item in data:
        msg=str(item.get('commit',{}).get('message') or '').split('\n',1)[0]
        match=re.fullmatch(r'chore\(stations\): publish ([a-z_]+) automated lot update #\d+',msg)
        if not match:continue
        cc=BATCH_NAMES.get(match.group(1))
        if not cc or cc in batches:continue
        stamp=time_or_none(item['commit']['committer']['date'])
        if stamp:batches[cc]={
            'publishedAt':stamp.isoformat(),'commitSha':item['sha'],
            'commitMessage':msg,'provenance':'GitHub commit for published country batch; NOT station-specific observation'}
    # Morocco October 7 batch was published as a Git commit with NO changes to
    # data/tesla_stations.json. GitHub path-filtered commit history omits it.
    # Prove the separately recorded batch commit instead of pretending no run occurred.
    if 'MA' not in batches:
        ref='ebe3a2f23aefcaf398f625cedbfe78b568cabe97'
        url='https://api.github.com/repos/yass3705/tesla-charge-companion-stable/commits/'+ref
        with urllib.request.urlopen(urllib.request.Request(url,headers={
            'User-Agent':'TCC-Tesla-Price-Provenance/1.0','Accept':'application/vnd.github+json'}),
            timeout=30) as response:
            commit=json.load(response)
        msg=commit['commit']['message'].splitlines()[0]
        if msg.startswith('chore(stations): publish morocco automated lot update #'):
            stamp=time_or_none(commit['commit']['committer']['date'])
            if stamp:
                batches['MA']={'publishedAt':stamp.isoformat(),'commitSha':commit['sha'],
                    'commitMessage':msg,'noChangesToTeslaFile':True,
                    'provenance':'GitHub batch commit without changed file; validates publication event but not price observation'}
    return batches

def main():
    stations,digest,_size=inv.read_catalogue()
    suc=json.loads(SUC.read_text(encoding='utf-8'))
    meta=json.loads(META.read_text(encoding='utf-8'))
    batches=batch_publications()
    # Morocco's 7-Oct "publish" commit was an empty/no-price-change commit,
    # excluded by GitHub's commits?path= filter. MA never uses SuC regardless.
    # Prevent silently trusting SuC just because an October country batch could not be fetched.
    if not all(x in batches for x in ('FR','IT','CH','ES','NL','UK','BE')):
        raise SystemExit('Missing recent country-batch provenance: cannot decide Mac/SuC precedence')
    evidence=ROOT/'reports/tesla/tesla-dataset-provenance-audit-latest.json'
    if evidence.is_file():
        known=json.loads(evidence.read_text(encoding='utf-8'))
        if known.get('sources',{}).get('mac_canonical_main',{}).get('sha256')!=digest:
            raise SystemExit('Mac canonical digest drifted from stored provenance audit')
    mapped=collections.defaultdict(list)
    for item in suc:
        if not isinstance(item,dict):continue
        cc=canonical_country(item.get('countryCode'))
        if cc in COUNTRIES:
            key=mac_key(item)
            if key[1]:mapped[(cc,key[1])].append(item)
    total=collections.defaultdict(collections.Counter)
    rows=[]
    seen_suc=set()
    now=dt.datetime.now(dt.timezone.utc)
    for mac in stations:
        if not isinstance(mac,dict):continue
        cc=canonical_country(mac.get('countryCode'))
        if cc not in COUNTRIES:continue
        key=mac_key(mac)
        matched=mapped.get((cc,key[1]),[]) if key[1] else []
        station_observed_at=time_or_none(mac.get('sourceObservedAt'))
        age_days=round((now-station_observed_at).total_seconds()/86400,3) if station_observed_at else None
        batch=batches.get(cc)
        published_at=time_or_none(batch.get('publishedAt')) if batch else None
        batch_age_days=round((now-published_at).total_seconds()/86400,3) if published_at else None
        batch_recent=batch_age_days is not None and 0<=batch_age_days<10
        comparable=[s for s in matched if isinstance(s.get('pricing'),dict)
                    and isinstance(s['pricing'].get('rules'),list) and s['pricing']['rules']]
        suc_exact=comparable[0] if len(matched)==1 and len(comparable)==1 else None
        suc_time=time_or_none(suc_exact.get('sourceObservedAt') or suc_exact.get('lastUpdated')) if suc_exact else None
        choice='mac'
        reason='suc_tracker_prohibited_for_MA' if cc=='MA' else None
        observation_verified=station_observed_at is not None
        if cc!='MA':
            if observation_verified and 0<=age_days<10:
                reason='verified_mac_observation_under_10_days'
            elif batch_recent and not observation_verified:
                # Recent collection/publishing evidence is stronger than stale legacy
                # lastUpdated, but NOT a verified per-station collection timestamp.
                # Keep Mac as a provisional reference until source metadata is fixed.
                reason='recent_mac_country_batch_publication_station_observation_missing'
            elif len(matched)>1:
                reason='non_unique_suc_match'
            elif not suc_exact or not suc_time:
                reason='no_verified_suc_comparator'
            elif observation_verified and age_days>=10 and suc_time>station_observed_at:
                choice='suc_charge_tariff_only_pending_source_reconciliation'
                reason='verified_mac_observation_over_10d_suc_observation_newer'
            elif observation_verified:
                reason='verified_suc_observation_not_newer_than_mac'
            else:
                # Especially DE: no October Mac batch, and stale lastUpdated is NOT a
                # price-observation date. Report a candidate, not proven precedence.
                choice='needs_freshness_evidence'
                reason='no_station_observation_no_recent_batch_suc_candidate_only'
        comparison='not_compared'
        if suc_exact:
            try:
                comparison='same_tariff' if station_schedule(mac)==station_schedule(suc_exact) else 'different_tariff'
            except (ValueError,KeyError,TypeError) as exc:
                comparison='not_comparable_'+type(exc).__name__
        total[cc]['stations']+=1
        total[cc][choice]+=1
        total[cc][reason]+=1
        total[cc][comparison]+=1
        if matched:seen_suc.update(id(x) for x in matched)
        rows.append({
            'country':cc,'macStationId':mac.get('id'),'teslaSlug':key[1] or None,
            'matchedSuCIds':[x.get('id') for x in matched],
            'macVerifiedPriceObservedAt':mac.get('sourceObservedAt'),
            'macLegacyLastUpdatedNOTPriceObservation':mac.get('lastUpdated'),
            'macCountryBatchPublishedAt':batch.get('publishedAt') if batch else None,
            'macCountryBatchCommitSha':batch.get('commitSha') if batch else None,
            'macCountryBatchAgeDays':batch_age_days,
            'macStationObservationVerified':observation_verified,
            'macVerifiedObservationAgeDays':age_days,
            'sucPriceObservedAt':suc_exact.get('sourceObservedAt') if suc_exact else None,
            'sucSnapshotGeneratedAt':meta.get('sourceGeneratedAt'),
            'chosenReference':choice,'choiceReason':reason,
            'priceScheduleComparison':comparison,
            'sucAdditionalFeesCoverage':'not_provided' if suc_exact else None,
            'note':'Read-only. Mac country commit proves publication; does not prove observation of each station. SUC missing ancillary fees.'
        })
    unmatched=collections.Counter()
    for x in suc:
        if isinstance(x,dict) and canonical_country(x.get('countryCode')) in COUNTRIES and id(x) not in seen_suc:
            unmatched[canonical_country(x.get('countryCode'))]+=1
    report={
       'schemaVersion':'2.0-provenance-corrected',
       'generatedAt':now.isoformat(),'scopeCountries':COUNTRIES,
       'macRepository':'yass3705/tesla-charge-companion-stable@main',
       'macSourcePath':'data/tesla_stations.json','macSourceSha256':digest,
       'v9LoadedSnapshotPath':'v9-production-runtime/data/tesla_stations.json',
       'macBatchPublicationEvidence':batches,
       'sucMetadata':meta,
       'supersedesMisleadingReport':{
          'priorClaim':'1,147 stations prefer SuC based on stale lastUpdated',
          'verdict':'INVALID: lastUpdated is a legacy station metadata date and not price observation',
          'fix':'separate station sourceObservedAt, country batch publication and SuC sourceObservedAt'},
       'sourceSelectionPolicy':{
          'verifiedMacUnder10Days':'use Mac observation if available',
          'macRecentBatchNoObservedAt':'retain Mac provisionally; batch commit does not prove station-level observation',
          'oldVerifiedMacNewerSuC':'consider exact, valid, newer SuC price ONLY after reconciliation',
          'unverifiedOldMac':'needs_freshness_evidence; do NOT blindly choose SuC',
          'Morocco':'always Mac; SuC never eligible',
          'fees':'retain CPO ancillary fees; SuC lacks them'},
       'countries':{c:dict(total[c]) for c in COUNTRIES},
       'unmatchedSuCRecords':dict(unmatched),
       'macStationsAudited':len(rows),
       'detailsPath':'tesla-source-selection-station-detail-latest.json',
       'notPublishedToV9':True}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'tesla-source-selection-audit-latest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'tesla-source-selection-station-detail-latest.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    if not all(total[c]['stations'] for c in COUNTRIES):raise SystemExit('Missing Tesla coverage country')
    if total['MA']['suc_charge_tariff_only_pending_source_reconciliation']:
        raise SystemExit('Morocco policy was violated')
    if sum(total[c]['suc_charge_tariff_only_pending_source_reconciliation'] for c in COUNTRIES)>0 and all(
       not x.get('macStationObservationVerified') for x in rows):
        raise SystemExit('SuC selected without Mac observation evidence')
    print('TESLA_FRESHNESS_POLICY_AUDIT='+json.dumps({
       'macStations':len(rows),'countries':{c:dict(total[c]) for c in COUNTRIES},
       'batchPublications':batches,'unmatchedSuC':dict(unmatched)},ensure_ascii=False))
if __name__=='__main__':main()
