#!/usr/bin/env python3
"""Read-only per-station Tesla Mac/SuC precedence audit. Never publishes tariffs."""
from __future__ import annotations
import collections,datetime as dt,hashlib,json,pathlib,sys
import tariff_global_inventory_20261009 as inv
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent/'suc_tracker'))
from core import mac_key,station_schedule,parse_date
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/tariff-scenarios'
SUC=ROOT/'data/suc-tracker/tesla_stations.json'
META=ROOT/'data/suc-tracker/metadata.json'
COUNTRIES=['FR','IT','CH','DE','ES','NL','UK','MA','BE']
def time_or_none(value):
    try:return parse_date(value)
    except (ValueError,TypeError):return None
def canonical_country(cc):return 'UK' if str(cc)=='GB' else str(cc)
def main():
    stations,digest,size=inv.read_catalogue()
    suc=json.loads(SUC.read_text(encoding='utf-8'))
    meta=json.loads(META.read_text(encoding='utf-8'))
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
        fresh=time_or_none(mac.get('sourceObservedAt') or mac.get('lastUpdated'))
        valid_fresh=fresh is not None
        age_days=round((now-fresh).total_seconds()/86400,3) if valid_fresh else None
        comparable=[s for s in matched if isinstance(s.get('pricing'),dict)
                    and isinstance(s['pricing'].get('rules'),list) and s['pricing']['rules']]
        suc_exact=comparable[0] if len(matched)==1 and len(comparable)==1 else None
        suc_time=time_or_none(suc_exact.get('sourceObservedAt') or suc_exact.get('lastUpdated')) if suc_exact else None
        choice='mac'
        reason='suc_tracker_prohibited_for_MA' if cc=='MA' else None
        if cc!='MA':
            if fresh is None:
                reason='mac_source_observation_date_missing_requires_review'
            elif age_days<10:
                reason='mac_source_observation_under_10_days'
            elif len(matched)>1:
                reason='non_unique_suc_match'
            elif not suc_exact or not suc_time:
                reason='no_validated_suc_comparator'
            elif suc_time>fresh:
                choice='suc_charge_tariff_only_pending_source_reconciliation'
                reason='mac_over_10_days_suc_price_observation_newer'
            else:reason='suc_observation_not_newer_than_mac'
        status='not_compared'
        if suc_exact:
            try:
                status='same_tariff' if station_schedule(mac)==station_schedule(suc_exact) else 'different_tariff'
            except (ValueError,KeyError,TypeError) as exc:
                status='not_comparable_'+type(exc).__name__
        total[cc]['stations']+=1
        total[cc][choice]+=1
        total[cc][reason]+=1
        total[cc][status]+=1
        if matched:seen_suc.update(id(x) for x in matched)
        rows.append({
            'country':cc,'macStationId':mac.get('id'),'teslaSlug':key[1] or None,
            'matchedSuCIds':[x.get('id') for x in matched],
            'macSourceObservedAt':mac.get('sourceObservedAt') or mac.get('lastUpdated'),
            'macObservationAgeDays':age_days,
            'sucPriceObservedAt':suc_exact.get('sourceObservedAt') if suc_exact else None,
            'sucSnapshotGeneratedAt':meta.get('sourceGeneratedAt'),
            'chosenReference':choice,'choiceReason':reason,'priceScheduleComparison':status,
            'sucAdditionalFeesCoverage':'not_provided' if suc_exact else None,
            'note':'No prices published. SuC-only price cannot overwrite Mac access, idle or congestion fees.'
        })
    leftover=collections.Counter()
    for x in suc:
        if isinstance(x,dict) and canonical_country(x.get('countryCode')) in COUNTRIES and id(x) not in seen_suc:
            leftover[canonical_country(x.get('countryCode'))]+=1
    report={'generatedAt':now.isoformat(),'scopeCountries':COUNTRIES,
        'macRepository':'yass3705/tesla-charge-companion-stable@main',
        'macSourcePath':'data/tesla_stations.json','macSourceSha256':digest,
        'sucMetadata':meta,'sourceSelectionPolicy':{
            'freshMac':'source observation under 10 days, not workflow execution',
            'oldMacAndNewerSuC':'candidate SuC price only when exact unique match, valid pricing and newer observation',
            'oldMacAndOlderSuC':'keep Mac','Morocco':'force Mac, regardless of SuC record presence or freshness',
            'fees':'retain operator ancillary fees; SuC does not supply them',
            'noMatch':'do not invent a station or a tariff from unmatched ID'
        },
        'countries':{c:dict(total[c]) for c in COUNTRIES},
        'unmatchedSuCRecords':dict(leftover),
        'macStationsAudited':len(rows),'detailsPath':'tesla-source-selection-station-detail-latest.json',
        'notPublishedToV9':True}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'tesla-source-selection-audit-latest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'tesla-source-selection-station-detail-latest.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    if not all(total[c]['stations'] for c in COUNTRIES):raise SystemExit('Missing Tesla coverage country')
    if total['MA']['suc_charge_tariff_only_pending_source_reconciliation']:
        raise SystemExit('Morocco policy was violated')
    print('TESLA_FRESHNESS_POLICY_AUDIT='+json.dumps({
       'macStations':len(rows),'countries':{c:dict(total[c]) for c in COUNTRIES},
       'unmatchedSuC':dict(leftover)},ensure_ascii=False))
if __name__=='__main__':main()
