#!/usr/bin/env python3
"""P1 exact EVSE + P2 validated published overlays + P3 new GPS/technical source candidates.

Source of truth: IRVE static IDs with explicit positive IRVE dynamic states.
P1/P2 are priced and already published *in Data Lab overlay*, not necessarily V9 UI.
P3 only if otherwise unmatched PDC can be uniquely assigned a HOMOGENEOUS source
tariff by station location, full station EVSE count, power, and identifier evidence.
P3 is UNPUBLISHED CANDIDATE evidence pending CPO/address audit; never silently
activate its tariff in V9. All counts deduplicate PDCs across tiers.
"""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip,json,runpy,math,re
R=Path(__file__).resolve().parents[1]
# Load reproducible P1/P2 sets, IRVE operational facts and 10m match primitives.
t=runpy.run_path(str(R/'scripts/audit_fr_two_level_tariff_join_20261009.py'))
base=t['base']; norm=t['n']; load=t['load']; number=t['num']
active=t['active']; cpo=t['cpo']
station=t['station']; bypdc=t['station_by_pdc']; unique_near=t['unique_near']; power_ok=t['power_ok']
E1=t['Eexact']; V1=t['Vexact']
E2=base['electra']; V2=base['electroverse']
src_electra=t['electra_source']; src_evr=t['ecache']; mapping_evr=t['evmap']
assert E1<=E2 and V1<=V2
def cpo_compatible(source, target):
 """Restrict to positive CPO evidence; no accidental cross-CPO fallback."""
 if not source:return False
 s=norm(source);names=[norm(target.get('operator')),norm(target.get('brand'))]
 if len(s)<4:return False
 return any(bool(x) and (x==s or (len(s)>5 and len(x)>5 and (x in s or s in x))) for x in names)
def payment_signature(price):
 if not isinstance(price,dict):return None
 # Do not infer per-connector validity from partial or complex tariffs.
 return json.dumps(price,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def match_station(point,n_source,peak,kind):
 near=unique_near(point)
 if not near:return None,'no_unique_station_within_10m'
 sid=near[1];target=station[sid]
 if not n_source or n_source!=len(target['ids']):return None,'evse_count_differs'
 if not power_ok(peak,target['maxp'],kind,target['kind']):return None,'peak_power_out_of_tolerance'
 return (sid,near[0]),None
# Source: independent Electra GraphQL stations with at least one chargeTariff,
# not hypothetical existence in inventory.
erej=Counter();ecandidates=defaultdict(list);eby_source={}
for pk,source in src_electra.items():
 tariffs=source.get('chargeTariffs') or []
 if not tariffs:continue
 target_raw=source.get('evses') or []
 if not target_raw:continue
 # Require exactly one identical simple standalone tariff profile for ALL EVSEs.
 # Restrictions/components require pricing parser and are not guessed.
 if len(tariffs)!=len(target_raw):
  erej['tariff_count_not_evse_count']+=1
  # Homogeneous single tariff may apply to full station only when source explicitly says so.
  if len(tariffs)!=1:continue
 sigs={payment_signature(o) for o in tariffs}
 if None in sigs or len(sigs)!=1:erej['tariff_heterogeneous']+=1;continue
 spec=tariffs[0]
 elements=spec.get('elements') or []
 if len(elements)!=1:erej['complex_elements']+=1;continue
 e=elements[0]
 restrictions=e.get('restrictions') or {}
 if any(v not in (None,[],{},'') for v in restrictions.values()):
  erej['complex_restrictions']+=1;continue
 pcs=e.get('priceComponents') or []
 if not pcs or any(str(z.get('type') or '').upper() not in ('ENERGY','FLAT','TIME','PARKING_TIME') for z in pcs):
  erej['unsupported_pricing_components']+=1;continue
 if not any(str(z.get('type') or '').upper()=='ENERGY' and number(z.get('price')) is not None for z in pcs):
  erej['no_energy_price']+=1;continue
 coord=source.get('coordinates') or {}
 peak=(number(source.get('maxPower')) or 0)/1000
 kinds=' '.join(map(str,source.get('connectorTypes') or [])).upper()
 kind=('DC' if any(z in kinds for z in ('CCS','CHADEMO','COMBO','NACS')) or peak>=50 else 'AC' if any(z in kinds for z in ('TYPE2','TYPE 2','SCHUKO')) else 'UNKNOWN')
 found,reason=match_station((coord.get('latitude'),coord.get('longitude')),len({str(x.get('id') or x.get('evseId') or i) for i,x in enumerate(target_raw)}),peak,kind)
 if not found:erej[reason]+=1;continue
 sid,dist=found;target=station[sid]
 # No raw source may claim PDC IDs from a different station.
 src_ids={norm(z.get('evseId')) for z in target_raw if norm(z.get('evseId'))}
 if any(by_pdc is not None and by_pdc!=sid for k in src_ids if (by_pdc:=bypdc.get(k))):
  erej['explicit_id_points_to_different_station']+=1;continue
 src_cpo=(source.get('cpo') or {}).get('name')
 if not cpo_compatible(src_cpo,target):
  erej['cpo_not_independently_verified']+=1;continue
 # Need independent per-EVSE assignment: station-wide tariff is identical.
 # With mixed source charging profiles, this parser rejects complex situations.
 uncovered=target['ids']&active-E2
 if not uncovered:
  erej['all_active_targets_already_published']+=1;continue
 ecandidates[sid].append({'source':pk,'dist':dist,'ids':sorted(uncovered),'tariff':next(iter(sigs)),'cpo':src_cpo})
 erej['technically_matched_candidate_source']+=1
E3=set();E3examples=[]
for sid,rows in ecandidates.items():
 if len(rows)!=1:
  erej['duplicate_sources_same_target']+=len(rows);continue
 z=rows[0];E3.update(z['ids'])
 if len(E3examples)<30:E3examples.append({'stationId':sid,'sourceLocationId':z['source'],'activeUnmatchedPdcCount':len(z['ids']),'dist':round(z['dist'],2),'cpo':z['cpo']})
assert not E3&E2
# Electroverse cache entries: priced connectors with no direct CPO identifier cannot
# establish a NEW verified association solely by GPS. Separate technical candidates.
vrej=Counter();vcandidates=defaultdict(list)
V3_possible=set();V3_validated=set()
for shard in load('data/electroverse/tariff_cache/manifest.json')['shards']:
 data=load('data/electroverse/tariff_cache/'+shard['file'])
 for pk,item in (data.get('stations') or {}).items():
  m=mapping_evr.get(str(pk))
  if not m:continue
  stationid=str(m.get('irveStationId') or '')
  if stationid not in station or not station[stationid]['ids']&active:continue
  tar=item.get('tariff') or {}
  evses=tar.get('evses') or []
  if not evses:continue
  signatures=set();all_powers=[];dc=False;ac=False;is_priced=True
  for evse in evses:
   conns=evse.get('connectors') or []
   if not conns:is_priced=False;break
   for conn in conns:
    power=number(conn.get('kilowatts'))
    if power:all_powers.append(power)
    std=str((conn.get('standard') or {}).get('name') if isinstance(conn.get('standard'),dict) else conn.get('standard') or '').upper()
    if any(x in std for x in ('CCS','COMBO','CHADEMO','NACS','DC')):dc=True
    if any(x in std for x in ('TYPE2','TYPE 2','T2','SCHUKO')):ac=True
    pcs=conn.get('priceComponents') or []
    if not pcs or conn.get('complexPricingDetail'):is_priced=False;break
    # Conservative: EVSE prices only if simple absolute components with same values.
    normcomponents=tuple((str(x.get('__typename')),str(x.get('formattedValue'))) for x in pcs)
    if any('None' in x[1] for x in normcomponents):is_priced=False;break
    signatures.add(normcomponents)
   if not is_priced:break
  if not is_priced or len(signatures)!=1 or not all_powers:
   vrej['pricing_complex_or_heterogeneous']+=1;continue
  rawpoint=(m.get('electroverse') or {})
  knd='DC' if dc and max(all_powers)>=30 else 'AC' if ac else 'DC' if max(all_powers)>=50 else 'UNKNOWN'
  found,reason=match_station((rawpoint.get('lat'),rawpoint.get('lon')),len({str(x.get('pk') or x.get('physicalReference') or i) for i,x in enumerate(evses)}),max(all_powers),knd)
  if not found:vrej[reason]+=1;continue
  sid,dist=found
  if sid!=stationid:vrej['mapping_other_station']+=1;continue
  target=station[sid]
  src_ids={norm(e.get('physicalReference')) for e in evses if norm(e.get('physicalReference'))}
  if any(bypdc.get(k) not in (None,sid) for k in src_ids):
   vrej['explicit_id_points_to_different_station']+=1;continue
  uncovered=(target['ids']&active)-V2
  if not uncovered:vrej['all_active_targets_already_published']+=1;continue
  # No independent physical CPO identity in the cached Electroverse payload.
  # Mark as technical candidates only; never silently treat as verified.
  vcandidates[sid].append({'source':pk,'dist':dist,'ids':sorted(uncovered),'sig':next(iter(signatures))})
  vrej['technically_matched_candidate_source']+=1
V3_examples=[]
for sid,rows in vcandidates.items():
 if len(rows)!=1:
  vrej['duplicate_sources_same_target']+=len(rows);continue
  V3_possible.update(rows[0]['ids'])
  if len(V3_examples)<25:V3_examples.append({'stationId':sid,'sourceLocationId':rows[0]['source'],'activeUnmatchedPdcCount':len(rows[0]['ids']),'dist':round(rows[0]['dist'],2)})
# V3_possible is not promoted into proven totals until independent CPO/address validation.
# E3 also audit candidates, although Electra CPO independently verified; track both
# verified pipeline candidates and the strictly approved P1+P2 core.
assert not V3_possible&V2
TYPES=['CPO','CPO+Electra','CPO+Electroverse','CPO+Electra+Electroverse','Electra','Electroverse','Electra+Electroverse','aucun_tarif_valide']
def classify(e,v):
 total=Counter();byPower=defaultdict(Counter)
 for k in active:
  labs=['CPO'] if k in cpo else []
  if k in e:labs.append('Electra')
  if k in v:labs.append('Electroverse')
  group='+'.join(labs) if labs else 'aucun_tarif_valide'
  total[group]+=1
  kw=base['power_by_pdc'].get(k)
  key=('%g'%kw)+' kW' if kw else 'PUISSANCE_INCONNUE'
  byPower[key][group]+=1
 return total,byPower
levels={}
for name,e,v in [('P1',E1,V1),('P1_P2',E2,V2),('P1_P2_P3_ElectraEligible',E2|E3,V2),('P1_P2_P3_allTechnicalCandidates',E2|E3,V2|V3_possible)]:
 a,by=classify(e,v)
 levels[name]={'coverage':dict(a),'fourBuckets':{x:a[x] for x in TYPES[:4]},'withCPO':sum(a[x] for x in TYPES[:4]),'withAnySource':len(active)-a['aucun_tarif_valide'],'power':[{ 'powerKw':kw,**{x:val[x] for x in TYPES},'total':sum(val.values())} for kw,val in sorted(by.items(),key=lambda i:float(i[0].split()[0]) if i[0]!='PUISSANCE_INCONNUE' else -1)]}
for level in levels.values():assert sum(level['coverage'].values())==len(active)
output={'generatedAt':datetime.now(timezone.utc).isoformat(),'branch':'audit/irve-tariff-left-join-20261009',
 'activeStatusAsOf':base['dynamic'].get('generatedAt'),
 'countEVSEActive':len(active),'CPOPriced':len(cpo),
 'matchMethod':'P1 literal normalized EVSE ID; P2 existing published verified identityMode overlays (exact, curated, technical, homogeneous); P3 previously unpublished candidate at 10 m + full station EVSE count + AC/DC max power + homogeneous tariffs + uniqueness. No nonpublic EVSE targeted.',
 'priorityCounts':{'Electra':{'P1':len(E1),'P2Additional':len(E2-E1),'P3TechnicalCandidateAdditional':len(E3),'P1P2':len(E2),'P1P2P3Candidate':len(E2|E3)},
  'Electroverse':{'P1':len(V1),'P2Additional':len(V2-V1),'P3TechnicalCandidateAdditional':len(V3_possible),'P3ApprovedIndependentCpoEvidence':0,'P1P2':len(V2),'P1P2P3Candidate':len(V2|V3_possible)}},
 'levels':levels,'incrementalCandidateEvses':{'electra':len(E3),'electroverse':len(V3_possible)},
 'diagnostics':{'Electra':dict(erej),'Electroverse':dict(vrej)},'examples':{'Electra':E3examples,'Electroverse':V3_examples},
 'policy':'Conservative audit: P3 not published. Any new EVSE candidate requires independent station CPO/address validation before moving into P2 overlay. Source CPO direct evidence list is not exhaustive of France.'}
path=R/'reports/france/irve-p1-p2-p3-tariff-correspondences-20261009.json';path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
print('IRVE_P123_TOTALS='+json.dumps({k:v for k,v in output.items() if k not in ('levels','examples')},ensure_ascii=False,separators=(',',':')))
print('IRVE_P123_FOUR_BUCKETS='+json.dumps({k:v['fourBuckets'] for k,v in levels.items()},ensure_ascii=False,separators=(',',':')))
print('IRVE_P123_BY_POWER='+json.dumps({k:[x for x in v['power'] if x['total']>=400] for k,v in levels.items()},ensure_ascii=False,separators=(',',':')))
