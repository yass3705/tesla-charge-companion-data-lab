#!/usr/bin/env python3
"""Read-only active IRVE LEFT JOIN with validated first-party CPO, Electra eMSP, Electroverse.

EVSE identity=normalized IRVE PDC itinerance; group by IRVE EVSE highest nominal kW.
Only positive IRVE dynamic status. eMSPs use PUBLISHED tariff overlay tiles, not
source locations without tariff. CPO coverage is strictly documented extractor-set,
not an extrapolation to every CPO in France. Missing CPO goes to separate buckets.
"""
from collections import defaultdict,Counter
from pathlib import Path
from datetime import datetime,timezone
import gzip,json,re,math
ROOT=Path(__file__).resolve().parents[1]
def load(path):
 p=ROOT/path
 with (gzip.open(p,'rt',encoding='utf-8') if str(p).endswith('.gz') else p.open('r',encoding='utf-8')) as f:return json.load(f)
def key(s):return re.sub('[^A-Z0-9]','',str(s or '').upper())
def number(v):
 try:
  f=float(v)
  return f if math.isfinite(f) and f>0 else None
 except (TypeError,ValueError):return None
def priced(v):
 if v is None or v=='' or v==[] or v=={}:return False
 if isinstance(v,bool):return v
 if isinstance(v,dict):return bool(v)
 return True
def put(k,source,guard=True):
 if not guard:return
 k=key(k)
 if k and k in active and k in station_by_pdc:
  cpo[k].add(source);per_source[source].add(k)
def by_list(file,field,id_field,price_field,extra=None):
 data=load(file)
 for row in data.get(field,[]):
  if not isinstance(row,dict):continue
  idval=row.get(id_field)
  price=row.get(price_field)
  if idval is None or price is None:continue
  if extra and not extra(row):continue
  if priced(price):put(idval,file)
def valid_offer(o):
 p=o.get('pricing') or {}
 return isinstance(p,dict) and (bool(p.get('rules')) or p.get('type') in ('free','flatRate'))
# IRVE state
irve=load('data/national/france-irve-static-v9/all.json.gz')
dynamic=load('data/national/france-irve-dynamic-status-v9.json.gz')
if 'enServicePdcIds' not in dynamic:raise SystemExit('FAIL CLOSED: no positive en_service PDC evidence')
asof=datetime.fromisoformat(dynamic['generatedAt'].replace('Z','+00:00'))
if abs((datetime.now(timezone.utc)-asof).total_seconds())>72*3600:raise SystemExit('FAIL CLOSED: stale dynamic IRVE evidence')
active={key(x) for x in dynamic['enServicePdcIds']}
if len(active)!=dynamic['states']['en_service']:raise SystemExit('FAIL CLOSED: state count mismatch')
station_by_pdc={}
power_by_pdc={}
company_by_pdc={}
identity_conflicts=set()
for row in irve:
 sid=str(row[0]);comp=' '.join(str(x or '') for x in (row[5],row[11] if len(row)>11 else None)).upper()
 for cfg in row[8] or []:
  kw=number(cfg[3] if len(cfg)>3 else None)
  for id in (cfg[6] if len(cfg)>6 and isinstance(cfg[6],list) else []):
   p=key(id)
   if not p:continue
   if p in station_by_pdc and station_by_pdc[p]!=sid:identity_conflicts.add(p)
   station_by_pdc[p]=sid
   if kw and kw>power_by_pdc.get(p,0):power_by_pdc[p]=kw
   company_by_pdc[p]=comp
if identity_conflicts:raise SystemExit(f'FAIL CLOSED: {len(identity_conflicts)} IRVE PDC keys with conflicting station IDs')
active&=set(station_by_pdc)
# Unique, verified direct CPO price attribution at EVSE.
cpo=defaultdict(set);per_source=defaultdict(set);errors=[]
files=[
 ('data/operator_direct/freshmile_chargepoint_exact_france.json','exact','id_pdc_itinerance','stationPrice',None),
 ('data/operator_direct/vianeo_chargepoint_exact_france.json','exact','id_pdc_itinerance','stationPrice',None),
 ('data/operator_direct/atlante_chargepoint_exact_france.json','exact','id_pdc_itinerance','stationPrice',None),
 ('data/operator_direct/easycharge_official_exact_france.json','exact','id_pdc_itinerance','energyEurPerKwh',None),
 ('data/operator_direct/metropolis_spie_official_france.json','exact','id_pdc_itinerance','energyEurPerKwh',None),
 ('data/operator_direct/chargezy_te63_official_france.json','exact','id_pdc_itinerance','energyEurPerKwh',None),
 ('data/operator_direct/driveco_evse_tariffs.json','resolved','evseId','tariff',None),
 ('data/operator_direct/etotem_official_france_tiled.json','pdcTariffOverlay','id_pdc_itinerance','tariff_text',None),
 ('data/operator_direct/stations_e_official_france.json','evseTariffs','id_pdc_itinerance','directAdHoc',None),
 ('data/operator_direct/citeos_irve_exact_france.json','tariffs','evseId','tarification',None),
 ('data/operator_direct/road_eflux_exact_france.json','pdcTariffOverlay','id_pdc_itinerance','price_components',lambda x:x.get('exact_pricing_visible') is True and x.get('no_pricing_info') is not True),
 ('data/operator_direct/ubitricity_fr_direct_access_exact_2026-10-04.json','detailRows','evseId','pricePerKwhEur',None),
 ('data/operator_direct/zephyre_epowerdirect_exact_france_20260925.json','records','evseId','tariff',None),
 ('data/operator_direct/reveo_national_exact_evse_tariffs.json','connectors','evse_id','tariffs',None),
]
for f,field,idfield,pricefield,validator in files:
 try:by_list(f,field,idfield,pricefield,validator)
 except Exception as e:errors.append({'file':f,'error':str(e)[:300]})
# Ionity official first-party, exact per PDC
for loc in load('data/operator_direct/ionity_exact_france.json').get('stations',[]):
 for co in loc.get('connectors',[]):
  put(co.get('sourceEvseId'),'ionity_official_exact',priced(co.get('adhocPrice')))
# Powerdot: exact IRVE reference from charged connector or verified charger IRVE IDs.
for row in load('data/national/powerdot_direct_france.json.gz').get('chargers',[]):
 if not row.get('ok'):continue
 evs=row.get('irvePdcIds') or []
 connectors=(row.get('charger') or {}).get('connectors') or []
 for co in connectors:
  if not priced(co.get('tariff')):continue
  pr=key(co.get('physicalReference'))
  if pr in station_by_pdc:put(pr,'powerdot_exact_charger_tariff')
  elif len(evs)==1:put(evs[0],'powerdot_single_evse_charger_tariff')
# Operator-direct Allego, each EVSE explicit rankable direct
for row in load('data/national/allego_direct_stations_france.json.gz').get('evses',[]):
 put(row.get('evseId'),'allego_direct_exact',bool(row.get('directEurPerKwh') is not None or row.get('parsedEnergyRateEurPerKwh') is not None) and bool(row.get('isOwnNetwork') is not False))
# Atlante direct; connector ad-hoc first-party
for loc in load('data/national/atlante_direct_stations_france_latest.json.gz').get('locations',[]):
 for v in loc.get('connectors',[]):
  put(v.get('evseId'),'atlante_first_party_ad_hoc',bool(v.get('pricePerKwhEur') is not None or v.get('tariffs')))
# Ionity other national copy not counted twice.
# Bump first-party station exact PDC -> tariff map
for loc in load('data/national/bump_direct_tariffs_graphql_france.json.gz').get('stations',[]):
 for p in ((loc.get('match') or {}).get('points') or []):
  put(p.get('idPdcItinerance'),'bump_graphql_evse_direct',p.get('mapped') is True and priced(p.get('tariff')))
# WAAT: only when single unambiguous power on station and rankable direct group.
for loc in load('data/national/waat_monta_direct_tariffs_france.json.gz').get('stations',[]):
 groups=[x for x in loc.get('rankableGroups',[]) if number(x.get('directEurPerKwh'))]
 pows={round(float(p),2) for p in loc.get('powerKwValues') or [] if number(p)}
 if len(groups)==1 and len(pows)==1:
  for k in loc.get('evseIds') or []:put(k,'waat_monta_single_rankable_group')
# National FIRST-PARTY tariff verified as uniform by operator; never extrapolate to concession or MSP.
for k in active:
 operator=company_by_pdc.get(k,'')
 if 'FASTNED' in operator:put(k,'fastned_national_direct')
 if 'LIDL' in operator:put(k,'lidl_france_official_direct')
 if 'IECHARGE' in operator.replace(' ',''):put(k,'iecharge_official_direct')
# Tariff overlays: published and validated engine offers, not raw collection presence.
def emsp_set(directory,offer_key):
 m=load(directory+'/manifest.json');result=set();ids_count=0;ambig=Counter();fl=0
 for tile in m.get('tiles') or []:
  o=load(directory+'/'+tile['file'])
  for row in o.get(offer_key) or []:
   if not valid_offer(row):continue
   targets=[key(i) for i in row.get('evseIds') or [] if key(i)]
   if len(targets)!=1:ambig['non_single_target']+=1;continue
   ident=targets[0]
   if ident in active:
    result.add(ident);ids_count+=1
    if not row.get('metadata',{}).get('identityMode'):ambig['missing_identity_mode']+=1
   fl+=1
 return result,{'activeOfferRows':ids_count,'totalValidOfferRows':fl,'activeUniqueEvses':len(result),'manifestGeneratedAt':m.get('generatedAt'),'manifestTiles':len(m.get('tiles') or []),'flags':dict(ambig)}
electra,em=emsp_set('data/platforms/electra/france','emspOffers')
electroverse,ev=emsp_set('data/platforms/electroverse/france-evse','emspOffers')
# Coinciding power variants count only one EVSE for requested EVSE (not line) cardinality.
power_counts=defaultdict(Counter);coverage=Counter();by_prefix=defaultdict(Counter)
for k in sorted(active):
 if k not in power_by_pdc:bucket='PUISSANCE_INCONNUE'
 else:
  v=power_by_pdc[k]
  bucket=('%g'%v)+' kW'
 c=bool(cpo.get(k));e=k in electra;v=k in electroverse
 label=('CPO+' if c else '')+('Electra+' if e else '')+('Electroverse+' if v else '')
 label=label.rstrip('+') or 'aucun_tarif_valide'
 power_counts[bucket][label]+=1
 coverage[label]+=1
 if c:by_prefix[k[:5]][label]+=1
def kw_order(s):
 if s=='PUISSANCE_INCONNUE':return -1
 try:return float(s.split(' ')[0])
 except:return -2
records=[{'powerKw':x,**{g:power_counts[x][g] for g in (
 'CPO','CPO+Electra','CPO+Electroverse','CPO+Electra+Electroverse',
 'Electra','Electroverse','Electra+Electroverse','aucun_tarif_valide')},
 'activeEvses':sum(power_counts[x].values())} for x in sorted(power_counts,key=kw_order)]
output={'generatedAt':datetime.now(timezone.utc).isoformat(),
 'definition':'IRVE left join by normalized PDC ID (only explicitly en_service). 1 row per EVSE grouped by highest IRVE nominal kW. CPO=enumerated actual verified first-party direct tariff sources; eMSP=validated published EVSE offers, not raw matching. Exclusive category partition.',
 'notComplete':bool(errors),
 'sourceSnapshotDates':{'irveDynamic':dynamic.get('generatedAt'),'ElectraEMSP':em['manifestGeneratedAt'],'Electroverse':ev['manifestGeneratedAt']},
 'scopes':{'IRVEActive':len(active),'IRVEActiveWithPower':sum(k in power_by_pdc for k in active),'CPOPricedEvses':len(cpo),'ElectraPublishedPricedEvses':len(electra),'ElectroversePublishedPricedEvses':len(electroverse)},
 'requestedFour':{s:coverage[s] for s in ('CPO','CPO+Electra','CPO+Electroverse','CPO+Electra+Electroverse')},
 'otherBuckets':{s:coverage[s] for s in ('Electra','Electroverse','Electra+Electroverse','aucun_tarif_valide')},
 'coverageCheckSum':sum(coverage.values()),
 'byPower':records,'sourceCPOCount':{s:len(v) for s,v in sorted(per_source.items(),key=lambda x:-len(x[1]))},
 'electraOverlay':em,'electroverseOverlay':ev,
 'extractorErrors':errors,
 'cpoPolicy':'Conservative documented subset (not national exhaustive tariff coverage); no price inherited solely by station/coordinates except strictly single-class WAAT or vetted national CPO tariff. GPS mapping not promoted to EVSE without existing validated offer.'}
out=ROOT/'reports/france/irve-tariff-left-join-20261009.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('IRVE_TARIFF_LEFT_JOIN_RESULT='+json.dumps({k:v for k,v in output.items() if k not in ('byPower','sourceCPOCount')},ensure_ascii=False,separators=(',',':')))
print('IRVE_TARIFF_BY_POWER='+json.dumps(output['byPower'],ensure_ascii=False,separators=(',',':')))
print('IRVE_CPO_SOURCE_COVERAGE='+json.dumps(output['sourceCPOCount'],ensure_ascii=False,separators=(',',':')))
if errors:raise SystemExit('FAIL CLOSED: operator direct source errors '+repr(errors))
