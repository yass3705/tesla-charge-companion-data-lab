#!/usr/bin/env python3
import gzip,json,hashlib
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'data/national/bump_direct_tariffs_tcc_france.json.gz'
OUT=ROOT/'v9-production-runtime/data/v9/france-bump-offers.json'
x=json.loads(gzip.decompress(SRC.read_bytes()))
groups={}
unresolved=0
quarantined=[]

def normalize_pricing(point):
  """Translate only Bump rules whose full fee semantics V9 can represent."""
  components=point.get('components') or {}
  if components.get('currency')!='EUR': return None,'unsupported_currency'
  source_rules=point.get('rules')
  rule={'scope':'allDay','start':'00:00','end':'24:00','currency':'EUR'}
  pricing={'type':'rules','rules':[rule]}
  if not source_rules:
    if components.get('parkingText') or components.get('isTariffChangingInTime'):
      return None,'missing_parsed_rules'
    if isinstance(components.get('energyEurPerKwh'),(int,float)):
      rule['pricePerKwh']=components['energyEurPerKwh']
    if isinstance(components.get('timeEurPerHour'),(int,float)):
      rule['chargingTimePerMinuteEur']=components['timeEurPerHour']/60
    if isinstance(components.get('flatFeeEur'),(int,float)):
      rule['sessionFeeEur']=components['flatFeeEur']
    if isinstance(components.get('minPriceEur'),(int,float)):
      pricing['minimumTotalEur']=components['minPriceEur']
    return pricing,None
  for source in source_rules:
    kind=source.get('kind')
    if kind=='minimum_total':
      pricing['minimumTotalEur']=source['amountEur']
    elif kind=='energy':
      rule['pricePerKwh']=source['eurPerKwh']
    elif kind=='flat_fee':
      conditions=source.get('conditions') or []
      if conditions:
        supported={'energy_above_kwh','session_duration_after_minutes'}
        if not all(condition.get('kind') in supported and isinstance(condition.get('value'),(int,float)) and condition['value']>=0 for condition in conditions):
          return None,'conditional_flat_fee_unknown'
        if any(condition['kind']=='session_duration_after_minutes' for condition in conditions) and components.get('parkingText'):
          return None,'conditional_duration_with_parking_unresolved'
        pricing.setdefault('conditionalSessionFees',[]).append({'amountEur':source['amountEur'],'conditions':conditions})
      else:
        rule['sessionFeeEur']=source['amountEur']
    elif kind=='charging_duration_surcharge':
      if source.get('afterMinutes')==0:
        rule['chargingTimePerMinuteEur']=source['eurPerMinute']
      elif isinstance(source.get('afterMinutes'),(int,float)) and source['afterMinutes']>0:
        rule.update({'afterMinutesRate':source['eurPerMinute'],
                     'afterMinutesThreshold':source['afterMinutes'],
                     'afterMinutesComponent':'TIME'})
      else:
        return None,'invalid_charging_duration_threshold'
    elif kind=='post_charge_occupancy':
      pricing['postChargeFee']={'eurPerMinute':source['eurPerMinute'],'graceMinutes':source['graceMinutes']}
    else:
      return None,'unsupported_rule_'+str(kind)
  checks=(('energyEurPerKwh','pricePerKwh',1),('flatFeeEur','sessionFeeEur',1),
          ('timeEurPerHour','chargingTimePerMinuteEur',60),('minPriceEur','minimumTotalEur',1))
  for source_key,normalized_key,multiplier in checks:
    source_value=components.get(source_key)
    target_value=(pricing if normalized_key=='minimumTotalEur' else rule).get(normalized_key)
    if source_key=='timeEurPerHour' and target_value is None and rule.get('afterMinutesComponent')=='TIME':
      target_value=rule['afterMinutesRate']
    if source_key=='flatFeeEur' and target_value is None:
      fees=pricing.get('conditionalSessionFees') or []
      if len(fees)==1:target_value=fees[0]['amountEur']
    if isinstance(source_value,(int,float)) and (target_value is None or abs(source_value-target_value*multiplier)>0.001):
      return None,'component_mismatch_'+source_key
  return pricing,None

for st in x.get('stations') or []:
  for p in st.get('points') or []:
    if not p.get('rankable'):
      unresolved+=1; continue
    evse=p.get('idPdcItinerance')
    pricing,reason=normalize_pricing(p)
    if not evse or reason:
      quarantined.append({'evseId':evse,'reason':reason or 'missing_evse_id'})
      continue
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
assert rankable+len(quarantined)==x['counts']['rankablePoints'], (rankable,len(quarantined),x['counts']['rankablePoints'])
assert unresolved==x['counts']['unresolvedPoints'], (unresolved,x['counts']['unresolvedPoints'])
assert all(set(o['pricing']['rules'][0]).isdisjoint({'kind','conditions','amountEur'}) for o in offers)
assert sum(len(o['evseIds']) for o in offers)==len({evse for o in offers for evse in o['evseIds']})
out={'schemaVersion':'1.0.0','country':'FR','generatedAt':datetime.now(timezone.utc).isoformat(),
     'mode':'operator-direct-exact-evse','policy':{'failClosed':True,'roamingIncluded':False},
     'directOffers':offers,'subscriptionOffers':[],
     'quarantinedSourceRankableEvse':quarantined,
     'sourceEvidence':{'sourceGeneratedAt':x.get('sourceGeneratedAt'),'francePoints':x['counts']['francePoints'],
                       'rankablePoints':rankable,'unresolvedPoints':unresolved,
                       'sourceRankablePoints':x['counts']['rankablePoints'],
                       'quarantinedSourceRankablePoints':len(quarantined),
                       'quarantineReasons':dict(Counter(row['reason'] for row in quarantined)),
                       'rankableCoveragePct':round(100*rankable/x['counts']['francePoints'],3)}}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'offers':len(offers),'runtimeRankablePoints':rankable,'quarantinedSourceRankablePoints':len(quarantined),'unresolvedPoints':unresolved,'quarantineReasons':out['sourceEvidence']['quarantineReasons']},indent=2))
