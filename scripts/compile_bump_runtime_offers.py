#!/usr/bin/env python3
import gzip,json,hashlib
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'data/national/bump_direct_tariffs_tcc_france.json.gz'
OUT=ROOT/'v9-production-runtime/data/v9/france-bump-offers.json'
x=json.loads(gzip.decompress(SRC.read_bytes()))
groups={}
unresolved=0
for st in x.get('stations') or []:
  for p in st.get('points') or []:
    if not p.get('rankable'):
      unresolved+=1; continue
    evse=p.get('idPdcItinerance')
    if not evse: continue
    rules=p.get('rules')
    components=p.get('components') or {}
    if rules:
      pricing={'type':'rules','rules':rules}
    else:
      rule={'scope':'allDay','start':'00:00','end':'24:00','currency':'EUR'}
      if isinstance(components.get('energyEurPerKwh'),(int,float)):
        rule.update({'billing':'kwh','pricePerKwh':components['energyEurPerKwh']})
      if isinstance(components.get('timeEurPerHour'),(int,float)):
        rule['chargingTimePerMinuteEur']=components['timeEurPerHour']/60
      if isinstance(components.get('flatFeeEur'),(int,float)):
        rule['sessionFeeEur']=components['flatFeeEur']
      pricing={'type':'rules','rules':[rule]}
    key=json.dumps(pricing,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    g=groups.setdefault(key,{'pricing':pricing,'evseIds':[],'tariffIds':set()})
    g['evseIds'].append(evse)
    if p.get('tariffId'): g['tariffIds'].add(str(p['tariffId']))
offers=[]
for i,(key,g) in enumerate(sorted(groups.items()),1):
  h=hashlib.sha1(key.encode()).hexdigest()[:10]
  offers.append({
    'id':f'bump-fr-{h}','selectionId':f'bump-fr-{h}','provider':'Bump direct',
    'countries':['FR'],'currency':'EUR','priority':132,'pricing':g['pricing'],
    'source':'Bump public direct GraphQL tariff groups + exact official EVSE mapping',
    'directOperatorOnly':True,'verifiedScope':'exact_evse','defaultSelected':False,
    'evseIds':sorted(set(g['evseIds'])),'operatorAliases':['Bump'],
    'metadata':{'exactEvseCount':len(set(g['evseIds'])),'tariffIds':sorted(g['tariffIds']),
                'fallback':'Electra then Electroverse'}
  })
rankable=sum(len(o['evseIds']) for o in offers)
assert rankable==x['counts']['rankablePoints'], (rankable,x['counts']['rankablePoints'])
assert unresolved==x['counts']['unresolvedPoints'], (unresolved,x['counts']['unresolvedPoints'])
out={'schemaVersion':'1.0.0','country':'FR','generatedAt':datetime.now(timezone.utc).isoformat(),
     'mode':'operator-direct-exact-evse','policy':{'failClosed':True,'roamingIncluded':False},
     'directOffers':offers,'subscriptionOffers':[],
     'sourceEvidence':{'sourceGeneratedAt':x.get('sourceGeneratedAt'),'francePoints':x['counts']['francePoints'],
                       'rankablePoints':rankable,'unresolvedPoints':unresolved,
                       'rankableCoveragePct':x['counts']['rankableCoveragePct']}}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'offers':len(offers),'rankablePoints':rankable,'unresolvedPoints':unresolved},indent=2))
