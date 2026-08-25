#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,hashlib,json,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
MONEY_RE=re.compile(r"(?:€\s*([0-9]+(?:[.,][0-9]+)?)|([0-9]+(?:[.,][0-9]+)?)\s*€)",re.I)
SESSION_PATTERNS=[
 re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:à|a)\s*la\s*connexion",re.I),
 re.compile(r"€\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:upon|at|for)\s*(?:the\s*)?connection",re.I),
 re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:upon|at|for)\s*(?:the\s*)?connection",re.I),
 re.compile(r"(?:forfait(?: de)?|flat rate of)\s*€?\s*([0-9]+(?:[.,][0-9]+)?)\s*€?\s*(?:par|per)\s*session",re.I),
 re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:par|per)\s*session",re.I),]
ENERGY_PATTERNS=[re.compile(r"(?:€\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(?:€\s*)?(?:par|per|/)\s*kwh(?:\s*(entam[eé]|started|starded|used|consumed|delivered|or part thereof|ou partie))?",re.I)]
TIME_MIN_PATTERNS=[re.compile(r"(?:€\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(?:€\s*)?(?:par|per|/)\s*(?:(started)\s+)?minute(?:\s*(entam[eé]e?))?",re.I)]
TIME_HOUR_BY_MIN_PATTERNS=[
 re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:par|/)\s*heure\s*,?\s*factur[eé]s?\s*[aà]\s*la\s*minute",re.I),
 re.compile(r"€\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:per|/)\s*hour\s*,?\s*billed\s*(?:by|per)\s*minute",re.I),]
FORBIDDEN=[
 r"\b(?:de|from|entre|between)\s*\d{1,2}(?::\d{2}|h\d{0,2})?\s*(?:am|pm)?\s*(?:à|a|to|-)\s*\d{1,2}",
 r"\b(?:le reste du temps|rest of the time|daytime|nighttime|nuit|jour)\b",
 r"\b(?:par tranche|per block|every\s+\d+\s+minutes?|toutes? les\s+\d+\s+minutes?)\b",
 r"\b(?:moins de|between\s+\d+\s*(?:kw|kwh)|entre\s+\d+\s*(?:kw|kwh)|au-del[aà] de\s+\d+\s*kw)\b",
 r"\b(?:sans consommation|without (?:energy )?consumption)\b",
 r"\b(?:une fois la charge terminée|once (?:the )?vehicle is recharged|once charging is complete|after (?:the )?end of (?:the )?charge|from the end of the charge|après la fin de la charge)\b",
 r"\b(?:gratuit(?:e|es|s)?|free for|free minutes?|premi[eè]res?|first\s+\d+\s+(?:minutes?|hours?))\b",
 r"\b(?:plafond|cap(?:ped)?|minimum fee|minimum de facturation)\b",
 r"\b(?:suppl[eé]mentaire|additional)\b",]
DELAY_WORD=re.compile(r"\b(?:apr[eè]s|after|au-del[aà]|beyond|[aà] partir de)\b",re.I)
PLAIN_HOUR=re.compile(r"(?:€\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*€)\s*(?:par|per|/)\s*(?:heure|hour)",re.I)
SAFE_ORDINAL_HOUR_DELAY=re.compile(r"(?:puis\s*,?\s*)?(?:à|a)\s+partir\s+de\s+la\s+(\d+)(?:er|e|ème|eme)\s+heure\s+de\s+branchement\s*,?\s*([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:par|/)\s*heure\s*,?\s*factur[eé]s?\s*[aà]\s*la\s*minute",re.I)
def norm(value:Any)->str:
 text=str(value or '').replace('\r',' ').replace('\n',' ').replace('\u202f',' ').replace('\xa0',' '); return re.sub(r'\s+',' ',text).strip().lower()
def amount(value:Any)->float:return float(str(value).replace(',','.'))
def unique_matches(patterns,text):
 matches={}
 for pattern in patterns:
  for match in pattern.finditer(text):matches[(match.start(),match.end(),match.group(0))]=match
 return list(matches.values())
def parse_exact_tariff(tariff):
 if not tariff.get('sourceValidated') or not tariff.get('tccRankable'):return None,'source_not_rankable'
 if tariff.get('isPreferential'):return None,'preferential'
 if tariff.get('currency')!='EUR':return None,'non_eur'
 components=tariff.get('components') or {}
 if components.get('status')!='parsed':return None,'not_parsed'
 raw=str(components.get('raw') or '').strip(); text=norm(raw)
 if tariff.get('isFree'):
  if float((tariff.get('maxPrice') or {}).get('amount') or 0)!=0:return None,'free_with_nonzero_cap'
  return {'currency':'EUR','free':True,'maxPriceEur':0.0},'accepted_free'
 if not raw:return None,'blank_nonfree'
 if re.search(r"termin|finished|complete|from the end of charg|end of charging|recharg|fini de charger",text,re.I):return None,'post_charge_fee_not_published'
 safe_delay=SAFE_ORDINAL_HOUR_DELAY.search(text)
 safe_delay_minutes=None;safe_delay_hourly=None;condition_text=text
 if safe_delay:
  ordinal=int(safe_delay.group(1));safe_delay_hourly=amount(safe_delay.group(2))
  if ordinal<2 or not (safe_delay_hourly>=0):return None,'invalid_delayed_hour_clause'
  safe_delay_minutes=float((ordinal-1)*60)
  condition_text=(text[:safe_delay.start()]+' '+text[safe_delay.end():]).strip()
 complex_cues=[r"\bfrom\s+\d",r"\bde\s+\d{1,2}(?:h|:)\d*",r"\bentre\s+\d",r"\bbetween\s+\d",r"\bafter\b",r"\bapr[eè]s\b",r"\b(?:a|à) partir d?[’']?\s*\d",r"\bfirst\s+(?:hour|minute)",r"\bpremi[eè]re?s?\s+(?:heure|minute)",r"\bsuppl[eé]ment\b",r"\badditional\b",r"\bnon[- ]?abonn",r"\bnon[- ]?subscriber",r"tarif pr[eé]f[eé]rentiel",r"preferential tariff",r"\bcentime"]
 if any(re.search(p,condition_text,re.I) for p in complex_cues):return None,'conditional_clause_not_published'
 for p in FORBIDDEN:
  if re.search(p,condition_text,re.I):return None,'unsupported_condition'
 if DELAY_WORD.search(condition_text):return None,'threshold_or_tier'
 session=unique_matches(SESSION_PATTERNS,text);energy=unique_matches(ENERGY_PATTERNS,text);time_min=unique_matches(TIME_MIN_PATTERNS,text);time_hour=unique_matches(TIME_HOUR_BY_MIN_PATTERNS,text)
 if len(session)>1 or len(energy)>1 or len(time_min)>1 or len(time_hour)>1:return None,'multiple_formula_components'
 if PLAIN_HOUR.search(text) and not time_hour:return None,'ambiguous_hour_billing'
 if not (session or energy or time_min or time_hour):return None,'no_supported_formula'
 exact={'currency':'EUR','free':False}; explained=[]
 if session:
  fee=amount(session[0].group(1));exact['sessionFeeEur']=fee;explained.append(fee)
 if energy:
  match=energy[0];price=amount(match.group(1));billing='started_kwh' if re.search(r"entam|started|starded|part thereof|ou partie",match.group(0),re.I) else 'linear_kwh';exact['energy']={'amount':price,'billing':billing};explained.append(price)
 if time_min:
  match=time_min[0];price=amount(match.group(1));billing='started_minute' if re.search(r"started|entam",match.group(0),re.I) else 'linear_minute';occupied_cues=(components.get('continuesWhilePluggedIn') or re.search(r"tarification continue tant|facturation continue tant|billing continues as long|pricing continues as long|charging continues as long|charge applies as long",text,re.I) or re.search(r"temps de branchement|dur[eé]e de branchement|temps de parking|connection time|duration of (?:the )?connection|parking time|time the vehicle is plugged",text,re.I));exact['time']={'amount':price,'billing':billing,'appliesTo':'occupied' if occupied_cues else 'charge'};explained.append(price)
 if time_hour:
  match=time_hour[0];hourly=amount(match.group(1));occupied_cues=(components.get('continuesWhilePluggedIn') or re.search(r"tarification continue tant|facturation continue tant|billing continues as long|pricing continues as long|charging continues as long|charge applies as long",text,re.I) or re.search(r"temps de branchement|dur[eé]e de branchement|temps de parking|connection time|duration of (?:the )?connection|parking time|time the vehicle is plugged",text,re.I));exact['time']={'amount':hourly/60.0,'billing':'started_minute','appliesTo':'occupied' if occupied_cues else 'charge','sourceHourlyAmount':hourly}
  if safe_delay_minutes is not None:
   if abs(hourly-safe_delay_hourly)>1e-9:return None,'delayed_hour_amount_mismatch'
   exact['time']['startAfterMinutes']=safe_delay_minutes;exact['time']['thresholdSemantics']='ordinal_hour_start'
  explained.append(hourly)
 source_money=sorted(round(amount(m.group(1) or m.group(2)),6) for m in MONEY_RE.finditer(text));explained_money=sorted(round(v,6) for v in explained)
 if source_money!=explained_money:return None,'unaccounted_monetary_clause'
 max_price=(tariff.get('maxPrice') or {}).get('amount')
 if max_price is not None:
  try:max_price=float(max_price)
  except (TypeError,ValueError):max_price=None
  if max_price is not None and max_price>0:exact['maxPriceEur']=max_price
 exact['sourceDescription']=raw;exact['sourceDescriptionSha256']=hashlib.sha256(raw.encode()).hexdigest();return exact,'accepted'
def display_rule(exact):
 rule={'scope':'allDay','start':'00:00','end':'24:00','billing':'kwh','currency':'EUR','pricePerKwh':0.0,'chargePerMinute':0.0,'connectionFee':float(exact.get('sessionFeeEur') or 0),'idlePerMinute':0.0,'afterMinutesRate':0.0,'afterMinutesThreshold':0.0,'afterMinutesCap':0.0,'afterMinutesCapStart':'00:00','afterMinutesCapEnd':'24:00'}
 if exact.get('free'):return rule
 energy=exact.get('energy') or {};time=exact.get('time') or {}
 if energy:rule['pricePerKwh']=float(energy['amount'])
 if time:
  threshold=float(time.get('startAfterMinutes') or 0)
  if threshold>0:rule['afterMinutesRate']=float(time['amount']);rule['afterMinutesThreshold']=threshold
  else:rule['chargePerMinute']=float(time['amount'])
 if not energy and time and not float(time.get('startAfterMinutes') or 0):rule['billing']='minute'
 return rule
def read_gzip(path):return json.load(gzip.open(path,'rt',encoding='utf-8'))
def write_gzip(path,payload):
 path.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
 with gzip.GzipFile(filename='',mode='wb',fileobj=path.open('wb'),mtime=0) as gz:gz.write(raw)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args();source=read_gzip(args.input)
 rejection=Counter();source_rankable=0;accepted_records=0;conflicting_points=0;station_rows=[];accepted_evse=0;published_configs=0
 for station in source.get('stations') or []:
  exact_points=[];station_accepted_evse=set()
  for point in station.get('chargePoints') or []:
   rankable_on_point=sum(1 for tariff in (point.get('tariffs') or []) if tariff.get('sourceValidated') and tariff.get('tccRankable'));source_rankable+=rankable_on_point
   point_kind=str(point.get('kind') or '').upper()
   if point_kind not in {'AC','DC'}:rejection['unsupported_connector_kind']+=rankable_on_point;continue
   formulas_by_power=defaultdict(dict);metadata_by_power=defaultdict(lambda:defaultdict(lambda:{'tariffIds':set(),'tariffRefs':set(),'names':set()}))
   for tariff in point.get('tariffs') or []:
    exact,reason=parse_exact_tariff(tariff)
    if exact is None:
     if tariff.get('sourceValidated') and tariff.get('tccRankable'):rejection[reason]+=1
     continue
    connector=tariff.get('connector') or {}
    try:connector_power=float(connector.get('powerKw') or point.get('powerKw') or 0)
    except (TypeError,ValueError):connector_power=0.0
    if not (connector_power>0):
     rejection['invalid_connector_power']+=1;continue
    accepted_records+=1;power_key=(point_kind,round(connector_power,3));key=json.dumps(exact,sort_keys=True,ensure_ascii=False,separators=(',',':'));formulas_by_power[power_key][key]=exact;meta=metadata_by_power[power_key][key];meta['tariffIds'].add(tariff.get('tariffId'))
    if tariff.get('tariffRef'):meta['tariffRefs'].add(str(tariff['tariffRef']))
    if tariff.get('name'):meta['names'].add(str(tariff['name']))
   point_published=False
   for (kind,connector_power),formulas in formulas_by_power.items():
    if len(formulas)!=1:
     if len(formulas)>1:conflicting_points+=1;rejection['conflicting_current_formulas']+=len(formulas)
     continue
    key,exact=next(iter(formulas.items()));meta=metadata_by_power[(kind,connector_power)][key];exact_points.append({'evseId':point.get('evseId'),'kind':kind,'powerKw':float(connector_power),'freshmileEvseId':point.get('freshmileEvseId'),'freshmileCustomRef':point.get('freshmileCustomRef'),'tariffIds':sorted(v for v in meta['tariffIds'] if v is not None),'tariffRefs':sorted(meta['tariffRefs']),'tariffNames':sorted(meta['names']),'exact':exact});point_published=True
   if point_published:station_accepted_evse.add(str(point.get('evseId') or ''))
  accepted_evse+=len([x for x in station_accepted_evse if x])
  if not exact_points:continue
  groups={}
  for point in exact_points:
   formula_key=json.dumps(point['exact'],sort_keys=True,ensure_ascii=False,separators=(',',':'));group_key=f"{point['kind']}|{point['powerKw']:.3f}|{formula_key}"
   if group_key not in groups:groups[group_key]={'kind':point['kind'],'powerKw':point['powerKw'],'exact':point['exact'],'evseIds':[],'freshmileEvseIds':[],'freshmileCustomRefs':[],'tariffIds':[],'tariffRefs':[],'tariffNames':[]}
   group=groups[group_key];group['evseIds'].append(point['evseId'])
   if point['freshmileEvseId'] is not None:group['freshmileEvseIds'].append(point['freshmileEvseId'])
   if point['freshmileCustomRef']:group['freshmileCustomRefs'].append(point['freshmileCustomRef'])
   group['tariffIds'].extend(point['tariffIds']);group['tariffRefs'].extend(point['tariffRefs']);group['tariffNames'].extend(point['tariffNames'])
  configs=[];power_variants=Counter((g['kind'],round(g['powerKw'],3)) for g in groups.values())
  for idx,group in enumerate(groups.values()):
   refs=sorted(set(str(v) for v in group['freshmileCustomRefs'] if v));provider='Freshmile direct'
   if power_variants[(group['kind'],round(group['powerKw'],3))]>1 and refs:provider+=f" (PDC {', '.join(refs)})"
   exact=group['exact'];configs.append({'id':f"freshmile-direct-{station.get('stationId')}-{idx}",'label':f"{provider} · {group['kind']} {group['powerKw']:g} kW",'kind':group['kind'],'powerKw':group['powerKw'],'stalls':len(set(group['evseIds'])),'pricing':{'type':'rules','rules':[display_rule(exact)],'freshmileExact':exact},'offerProvider':provider,'offerType':'operator_direct','freshmileDirect':True,'freshmileVerified':True,'freshmileStrictExact':True,'freshmileStationId':station.get('stationId'),'freshmileEvseIds':sorted(set(str(v) for v in group['evseIds'] if v)),'freshmileInternalEvseIds':sorted(set(group['freshmileEvseIds'])),'freshmileCustomRefs':refs,'freshmileTariffIds':sorted(set(group['tariffIds'])),'freshmileTariffRefs':sorted(set(group['tariffRefs'])),'freshmileTariffNames':sorted(set(group['tariffNames']))})
  published_configs+=len(configs);coords=station.get('coordinates') or {};station_rows.append({'stationId':station.get('stationId'),'name':station.get('name'),'address':station.get('address'),'latitude':float(coords.get('latitude')),'longitude':float(coords.get('longitude')),'configurations':configs})
 payload={'schemaVersion':'1.0.0','dataset':'freshmile-direct-tcc-v8-france','generatedAt':datetime.now(timezone.utc).isoformat(),'sourceDataset':source.get('dataset'),'sourceGeneratedAt':source.get('generatedAt'),'scope':{'countryCode':'FR','onlyDirectCpo':True,'roamingIncluded':False,'configuredRegionalNetworksIncluded':False,'regionalNetworkCandidatesMayRemain':bool((source.get('scope') or {}).get('regionalNetworkCandidatesMayRemain')),'preferentialTariffsIncluded':False,'onlyStrictTccExact':True,'unsupportedTariffsRemainNonRankable':True},'counts':{'sourceStations':int((source.get('stats') or {}).get('stationsInInventory') or 0),'sourceEvse':int((source.get('stats') or {}).get('chargePointsInInventory') or 0),'sourceRankableTariffRecords':source_rankable,'strictAcceptedTariffRecordsBeforeConflictGate':accepted_records,'strictPublishedStations':len(station_rows),'strictPublishedEvse':accepted_evse,'strictPublishedConfigurations':published_configs,'conflictingEvseExcluded':conflicting_points,'rejectedRankableRecords':sum(rejection.values())},'rejectionReasons':dict(sorted(rejection.items())),'sourceSafety':{'freshmileRecoveryEvseMatchRatePct':(source.get('quality') or {}).get('finalEvseMatchRatePct'),'freshmileSourceValidatedTariffRatePct':(source.get('quality') or {}).get('sourceValidatedTariffRatePct'),'regionalNetworkConfiguredExclusions':(source.get('regionalNetworkAudit') or {}).get('configuredNetworkCount'),'regionalNetworkCandidatesMayRemain':bool((source.get('scope') or {}).get('regionalNetworkCandidatesMayRemain')),'nearestStationSubstitutionAllowed':False,'exactEvseCustomRefRequiredBySourcePipeline':True},'stations':station_rows}
 write_gzip(args.output,payload);print(json.dumps({'output':str(args.output),'counts':payload['counts'],'rejectionReasons':payload['rejectionReasons']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()