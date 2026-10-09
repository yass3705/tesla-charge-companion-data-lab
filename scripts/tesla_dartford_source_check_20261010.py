#!/usr/bin/env python3
"""Grounded comparison for Dartford Tesla Service Centre across Mac and SuC datasets."""
import json, pathlib, urllib.request, datetime, hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/tesla/dartford-source-check-latest.json'
URL='https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/main/data/tesla_stations.json'
req=urllib.request.Request(URL,headers={'User-Agent':'TCC-Dartford-Source-Audit/1.0'})
with urllib.request.urlopen(req,timeout=90) as resp:
    raw=resp.read()
mac=json.loads(raw)
suc=json.loads((ROOT/'data/suc-tracker/tesla_stations.json').read_bytes())
def contains_dartford(record):
    return 'dartford' in json.dumps(record,ensure_ascii=False).lower()
def find_matches(records):
    return [r for r in records if isinstance(r,dict) and contains_dartford(r)]
def describe(row):
    configs=row.get('chargingConfigurations') or []
    pricing=row.get('pricing') or {}
    return {
       'id':row.get('id'),
       'name':row.get('name'),'countryCode':row.get('countryCode'),
       'teslaUrl':row.get('teslaUrl'),'lastUpdated':row.get('lastUpdated'),
       'sourceObservedAt':row.get('sourceObservedAt'),
       'pricing':pricing,
       'configurations':[{
          'id':c.get('id'),'powerKw':c.get('powerKw'),
          'pricing':c.get('pricing'),
          'ruleCount':len((c.get('pricing') or {}).get('rules') or [])
       } for c in configs],
       'stationRuleCount':len(pricing.get('rules') or []),
       'source':row.get('source'),
       'sucTracker':row.get('sucTracker')
    }
mac_hits=list(map(describe,find_matches(mac)))
suc_hits=list(map(describe,find_matches(suc)))
report={
    'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'macPath':'tesla-charge-companion-stable/data/tesla_stations.json',
    'macSha256':hashlib.sha256(raw).hexdigest(),
    'macTotalStations':len(mac),'sucPath':'tesla-charge-companion-data-lab/data/suc-tracker/tesla_stations.json',
    'sucTotalStations':len(suc),
    'macDartfordCount':len(mac_hits),'sucDartfordCount':len(suc_hits),
    'macDartford':mac_hits,'sucDartford':suc_hits,
    'expectedStation':'tesla-dartford-uk-tesla-service-centre',
    'comment':'Actual source pricing only; screenshot member/nonmember tariffs not inserted into station data by this audit'
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('DARTFORD_SOURCE_RESULT='+json.dumps({
    'macCount':len(mac_hits),'sucCount':len(suc_hits),
    'mac':[{ 'id':x['id'],'name':x['name'],'stationRuleCount':x['stationRuleCount'],
             'configs':[{ 'id':c['id'],'count':c['ruleCount'],'rules':c['pricing'].get('rules') if c['pricing'] else []}
                for c in x['configurations']] }for x in mac_hits],
    'suc':[{ 'id':x['id'],'name':x['name'],'stationRuleCount':x['stationRuleCount'],
             'configs':[{ 'id':c['id'],'count':c['ruleCount'],'rules':c['pricing'].get('rules') if c['pricing'] else []}
                for c in x['configurations']] }for x in suc_hits]
},ensure_ascii=False))
