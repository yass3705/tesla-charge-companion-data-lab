#!/usr/bin/env python3
import gzip,json,os
SRC='data/national/waat_monta_direct_tariffs_france.json.gz'
OUT='data/publish/waat_direct_tariffs_tcc_france.json'
with gzip.open(SRC,'rt',encoding='utf-8') as f:p=json.load(f)
assert p['dataset']=='waat-monta-direct-tariffs-france'
assert p['schemaVersion']=='2.0.0'
assert p['scope']['directCpoOnly'] is True and p['scope']['roamingIncluded'] is False
assert p['counts']['inventoryStations']==571 and p['counts']['mapHttp200']==571 and p['counts']['mapErrors']==0
stations=[]; safe_count=0
for s in p['stations']:
    configs=[]
    for c in s.get('integrationConfigs',[]):
        if c.get('rankable') is not True: continue
        price=float(c['directEurPerKwh']); kind=c['kind']; power=float(c['powerKw'])
        assert kind in ('AC','DC') and power>0 and price>0 and c.get('groupIds')
        configs.append({'kind':kind,'powerKw':power,'directEurPerKwh':price,'groupIds':c['groupIds']})
        safe_count+=1
    stations.append({
      'stationId':s['stationIdNormalized'],
      'name':s.get('stationName') or '',
      'address':s.get('address') or '',
      'coordinates':s.get('coordinates'),
      'configs':configs
    })
assert len(stations)==571 and safe_count==507
by_group={}
for s in p['stations']:
    for g in s.get('montaGroups',[]):by_group[g['montaGroupId']]=g
assert by_group[631961]['rankable'] and by_group[631961]['kind']=='DC' and abs(by_group[631961]['directEurPerKwh']-.42)<1e-9
assert by_group[494949]['rankable'] and by_group[494949]['kind']=='AC' and abs(by_group[494949]['directEurPerKwh']-.28)<1e-9
assert by_group[714420]['rankable'] and by_group[714420]['kind']=='DC' and abs(by_group[714420]['directEurPerKwh']-.62)<1e-9
assert not by_group[811653]['rankable'] and by_group[811653]['blockingReason']=='price_range'
assert all(811653 not in c['groupIds'] for s in stations for c in s['configs'])
out={
 'schemaVersion':'1.0.0','dataset':'waat-direct-tariffs-tcc-france','operator':'WAAT','country':'FR',
 'generatedAt':p['generatedAt'],
 'source':{'dataset':'waat-monta-direct-tariffs-france','sourceType':p['source']['type']},
 'scope':{'directCpoOnly':True,'roamingIncluded':False,'stationSpecificPricing':True,'unresolvedCasesNeverRankable':True},
 'counts':{'franceStations':571,'rankableStations':sum(bool(s['configs']) for s in stations),'rankableConfigs':safe_count,'unresolvedStations':sum(not s['configs'] for s in stations)},
 'stations':stations
}
os.makedirs(os.path.dirname(OUT),exist_ok=True)
with open(OUT,'w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'))
print(json.dumps(out['counts'],indent=2))
