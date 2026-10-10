#!/usr/bin/env python3
"""Read-only Tesla Mac vs SuC-Tracker SOURCE SELECTION BY COUNTRY.

Mac collection/publishing is per country, not per station. Only inspect station
identities to identify sites present in one catalogue but not the other, plus
ambiguous identifiers. Never use legacy station lastUpdated as a price date.
Does not alter V9 or publish prices.
"""
from __future__ import annotations
import collections
import datetime as dt
import hashlib
import json
import pathlib
import sys
import urllib.request
from zoneinfo import ZoneInfo
import tesla_global_tariff_inventory_20261009 as inv

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent/'suc_tracker'))
from core import mac_key

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/tariff-scenarios'
SUC=ROOT/'data/suc-tracker/tesla_stations.json'
META=ROOT/'data/suc-tracker/metadata.json'
COUNTRIES=('FR','IT','CH','DE','ES','NL','UK','MA','BE')
PROVENANCE_URL=(
  'https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/main/'
  'data/tesla-mac-catalogue-publication.json'
)
PUBLIC_VERIFICATION_URL=(
  'https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/main/'
  'data/tesla-suc-only-public-verification.json'
)
def cc(value):
    return 'UK' if value=='GB' else value
def day(value):
    try:return dt.date.fromisoformat(str(value)[:10])
    except (ValueError,TypeError):return None
def published_date(info):
    stamp=(info or {}).get('lastMacCountryBatch') or {}
    try:
        timestamp=dt.datetime.fromisoformat(stamp['publishedAt'].replace('Z','+00:00'))
        return timestamp.astimezone(ZoneInfo('Europe/Paris')).date()
    except (KeyError,ValueError,TypeError):return None
def get_evidence():
    with urllib.request.urlopen(urllib.request.Request(
        PROVENANCE_URL,headers={'User-Agent':'TCC-Country-Mac-SuC-Audit/3.0'}),timeout=40) as f:
        return json.load(f)
def get_public_access_evidence():
    with urllib.request.urlopen(urllib.request.Request(
        PUBLIC_VERIFICATION_URL,headers={'User-Agent':'TCC-Country-Mac-SuC-Audit/3.1'}),timeout=40) as f:
        result=json.load(f)
    if result.get('schemaVersion')!=1:raise ValueError('Unknown public-access evidence schema')
    return {v['sucRowId']:v for v in result['verified']}
def primary_key(row):
    country=cc(row.get('countryCode'))
    key=mac_key(row)
    return (country,key[1]) if key[1] else (country,None)
def main():
    mac,mac_sha,_=inv.read_catalogue()
    suc=json.loads(SUC.read_text(encoding='utf8'))
    suc_meta=json.loads(META.read_text(encoding='utf8'))
    evidence=get_evidence()
    approved_public=get_public_access_evidence()
    if evidence.get('canonicalSha256')!=mac_sha:
        raise SystemExit('Mac canonical source changed during this report; retry after sync')
    now=dt.datetime.now(dt.timezone.utc)
    today=now.astimezone(ZoneInfo('Europe/Paris')).date()
    mac_groups=collections.defaultdict(list)
    suc_groups=collections.defaultdict(list)
    for station in mac:
        country=cc(station.get('countryCode'))
        if country in COUNTRIES:mac_groups[country].append(station)
    for station in suc:
        country=cc(station.get('countryCode'))
        if country in COUNTRIES:suc_groups[country].append(station)
    result={}
    exceptions=[]
    for country in COUNTRIES:
        mac_group=mac_groups[country]
        suc_group=suc_groups[country]
        if not mac_group:raise SystemExit('Mac country missing: '+country)
        repo_cc='GB' if country=='UK' else country
        mac_time=published_date(evidence['countries'].get(repo_cc))
        mac_provenance='country_mac_batch_publication'
        if mac_time is None:
            # No batch for DE: one historical date for the WHOLE country,
            # never 326 independent Mac freshness assessments.
            older=[day(s.get('lastUpdated')) for s in mac_group]
            older=[x for x in older if x]
            mac_time=max(older) if older else None
            mac_provenance='legacy_country_metadata_unverified' if older else 'unavailable'
        observations=[day(s.get('sourceObservedAt') or
                          (s.get('sucTracker') or {}).get('lastSuccessfulAt'))
                      for s in suc_group]
        suc_time=min(observations) if observations and all(observations) else None
        suc_provenance='country_minimum_observation' if suc_time else 'incomplete'
        if country=='MA':
            selected='Mac';reason='Morocco_Mac_only'
        elif mac_time and (today-mac_time).days>=0 and (today-mac_time).days<10:
            selected='Mac';reason='Mac_country_recent_under_10_days'
        elif mac_time and suc_time and suc_time>mac_time and suc_time<=today:
            selected='SuC Tracker';reason='SuC_country_observation_newer_than_Mac_country'
        else:
            selected='Mac';reason='SuC_not_newer_or_country_provenance_missing'

        # IDs only: identify stations unique to either catalogue or ambiguous
        # matches; DO NOT compare per-station prices or observation dates.
        mac_keys=collections.defaultdict(list)
        suc_keys=collections.defaultdict(list)
        for st in mac_group:mac_keys[primary_key(st)].append(st)
        for st in suc_group:suc_keys[primary_key(st)].append(st)
        mac_only=0;suc_only=0;ambiguous=0
        for key,stations in mac_keys.items():
            matches=suc_keys.get(key,[])
            if not matches:
                mac_only+=len(stations)
                for st in stations:exceptions.append({
                    'country':country,'type':'only_mac','macStationId':st.get('id'),
                    'sucStationId':None,'countrySelected':selected,
                    'outcome':'Mac station remains in V9'})
            elif len(stations)!=1 or len(matches)!=1:
                ambiguous+=len(stations)+len(matches)
                exceptions.append({'country':country,'type':'ambiguous_station_id',
                    'macStationIds':[s.get('id') for s in stations],
                    'sucStationIds':[s.get('id') for s in matches],
                    'countrySelected':selected,'outcome':'manual identity check'})
        for key,stations in suc_keys.items():
            if key not in mac_keys:
                suc_only+=len(stations)
                for st in stations:
                    newer=selected=='SuC Tracker' and country!='MA'
                    official=approved_public.get(st.get('id')) if newer else None
                    eligible=bool(official and official.get('countryCode')==repo_cc and
                                  official.get('sourceStationId')==
                                      str((st.get('sucTracker') or {}).get('sourceStationId') or '') and
                                  (st.get('pricing') or {}).get('rules') and
                                  any(float(c.get('powerKw') or 0)>0 for c in
                                      (st.get('chargingConfigurations') or [])))
                    exceptions.append({
                        'country':country,
                        'type':'only_suc_newer_public_verified' if eligible else
                                'only_suc_newer_pending_access' if newer else
                                'only_suc_parked_country_not_newer',
                        'macStationId':None,'sucStationId':st.get('id'),
                        'countrySelected':selected,
                        'sucCountryNewer':newer,
                        'officialTeslaPublicVerified':eligible,
                        'verificationUrl':official.get('officialTeslaPage') if eligible else None,
                        'accessSource':(st.get('sucTracker') or {}).get('accessSource') or 'unknown',
                        'outcome':'Eligible for V9 inclusion' if eligible else
                                  'Verify public access before inclusion' if newer else
                                  'Keep outside V9 until SuC country is newer'
                    })
        result[country]={
            'stations':len(mac_group),'sucStations':len(suc_group),
            'preferredTariffSource':selected,'reason':reason,
            'macCountryPublishedOrLegacyOn':mac_time.isoformat() if mac_time else None,
            'macEvidence':mac_provenance,'macAgeDays':(today-mac_time).days if mac_time else None,
            'sucCountryObservedOn':suc_time.isoformat() if suc_time else None,
            'sucEvidence':suc_provenance,
            'onlyMacStations':mac_only,'onlySuCStations':suc_only,'ambiguousIds':ambiguous,
            'suc_charge_tariff_only_pending_source_reconciliation':0 if country=='MA' else
                len(mac_group) if selected=='SuC Tracker' else 0,
        }
    report={
        'schemaVersion':'3.1-country-selection-suc-only-conditional',
        'generatedAt':now.isoformat(),'scopeCountries':list(COUNTRIES),
        'macRepository':'yass3705/tesla-charge-companion-stable@main',
        'macSourcePath':'data/tesla_stations.json','macSourceSha256':mac_sha,
        'macCountryBatchPublicationEvidence':evidence['countries'],
        'sucMetadata':suc_meta,
        'countrySelectionGranularity':'one source decision per country',
        'stationInspectionGranularity':'only sites missing in one catalogue or ambiguous IDs',
        'countries':result,
        'unmatchedSuCRecords':{c:result[c]['onlySuCStations'] for c in COUNTRIES},
        'macStationsAudited':sum(len(mac_groups[c]) for c in COUNTRIES),
        'stationExceptionCount':len(exceptions),
        'sucOnlyPublicVerifiedEligible':sum(x.get('officialTeslaPublicVerified',False) for x in exceptions),
        'sucOnlyNewerPendingPublicVerification':sum(x['type']=='only_suc_newer_pending_access' for x in exceptions),
        'sucOnlyParkedOlderCountry':sum(x['type']=='only_suc_parked_country_not_newer' for x in exceptions),
        'detailsPath':'tesla-source-selection-station-detail-latest.json',
        'detailsNote':'Legacy filename retained; rows now contain ONLY missing/ambiguous station exceptions',
        'notPublishedToV9':True,
        'policy':{
            'macRecent':'Mac per-country date <10 days',
            'after10Days':'SuC only if conservative SuC COUNTRY source observation newer than Mac COUNTRY date',
            'morocco':'always Mac',
            'noStationAgeComparisons':True,
            'unmatchedStations':'SuC-only parked unless SuC country newer; then include only Tesla-officially verified public sites; Morocco always Mac',
        },
        'supersedesMisleadingReport':{
            'priorClaim':'station-level lastUpdated means 1,147 SuC overrides',
            'verdict':'INVALID: country-wide Mac update metadata is authoritative'},
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'tesla-source-selection-audit-latest.json').write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'tesla-source-selection-station-detail-latest.json').write_text(
        json.dumps(exceptions,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    if country not in COUNTRIES or result['MA']['preferredTariffSource']!='Mac':
        raise SystemExit('Morocco Mac-only policy violated')
    print('TESLA_COUNTRY_SOURCE_AUDIT='+json.dumps({
      'stations':report['macStationsAudited'],
      'decisions':{c:v['preferredTariffSource'] for c,v in result.items()},
      'exceptions':len(exceptions)},ensure_ascii=False))
if __name__=='__main__':main()
