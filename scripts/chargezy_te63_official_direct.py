#!/usr/bin/env python3
import csv,io,json,requests
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
META='https://www.data.gouv.fr/api/1/datasets/base-nationale-des-irve-data-gouv-infrastructures-de-recharge-pour-vehicules-electriques/'
SOURCE='https://www.te63.fr/nos-metiers/mobilite-electrique/'
s=requests.Session(); s.headers['User-Agent']='TeslaChargeCompanion-data-audit/1.0'
meta=s.get(META,timeout=30).json()
cand=[]
for x in meta.get('resources') or []:
    if str(x.get('format') or '').lower()!='csv': continue
    title=str(x.get('title') or ''); tl=title.lower(); url=str(x.get('url') or '').lower()
    if 'consolidation' not in tl or 'documentation' in tl or 'ref-table' in url: continue
    score=(2 if 'dernière version' in tl or 'derniere version' in tl else 1,
           str(x.get('last_modified') or x.get('modified') or x.get('created_at') or ''))
    cand.append((score,x))
cand.sort(key=lambda z:z[0],reverse=True)
if not cand: raise SystemExit('no current PAN consolidation CSV')
pan=cand[0][1]['url']; r=s.get(pan,timeout=120); r.raise_for_status()
text=r.content.decode('utf-8-sig','replace')
try:d=csv.Sniffer().sniff(text[:100000],delimiters=',;\t')
except:d=csv.excel
rows=list(csv.DictReader(io.StringIO(text),dialect=d))
def v(row,*names):
    for n in names:
        if row.get(n) not in (None,''): return str(row[n]).strip()
    return ''
def yes(row,*names):
    return any(v(row,n).lower() in ('true','1','oui','yes') for n in names)
target=[]
for row in rows:
    op=v(row,'nom_operateur'); net=v(row,'nom_enseigne','nom_reseau')
    if 'spie citynetworks' in op.lower() and net.strip().upper()=='CHARGEZY - TE63':
        target.append(row)
exact=[]; special=[]; gaps=[]
for row in target:
    pid=v(row,'id_pdc_itinerance'); sid=v(row,'id_station_itinerance'); name=v(row,'nom_station'); addr=v(row,'adresse_station')
    try:p=float(v(row,'puissance_nominale') or 0)
    except:p=0
    ccs=yes(row,'prise_type_combo_ccs'); cha=yes(row,'prise_type_chademo'); t2=yes(row,'prise_type_2'); ef=yes(row,'prise_type_ef')
    rec={'id_pdc_itinerance':pid,'id_station_itinerance':sid,'station':name,'address':addr,'powerKw':p}
    hay=(name+' '+addr).lower()
    if 'coustill' in hay and ('saint-germain' in hay or 'saint germain' in hay):
        special.append({**rec,'reason':'official_contactless_card_special_fixed_25_eur_requires_payment_mode_disambiguation',
                        'contactlessCardFixedEur':25.0})
        continue
    tariff=None
    if p<=22.1 and (t2 or ef) and not (ccs or cha):
        tariff={'sessionFeeEur':2.0,'energyEurPerKwh':0.59,'postChargeGraceMinutes':180,
                'postChargeEurPerMinute':0.10,'postChargeWaived':'23:00-07:00',
                'rule':'TE63 non-subscriber normal AC <=22kVA'}
    elif p<=25.1 and (ccs or cha):
        tariff={'sessionFeeEur':2.0,'energyEurPerKwh':0.59,'postChargeGraceMinutes':90,
                'postChargeEurPerMinute':0.10,'rule':'TE63 non-subscriber normal DC <=25kW'}
    elif 42.0<=p<=43.5 and t2:
        tariff={'sessionFeeEur':2.0,'energyEurPerKwh':0.69,'postChargeGraceMinutes':45,
                'postChargeEurPerMinute':0.20,'rule':'TE63 non-subscriber rapid AC <=43kVA'}
    elif 49.0<=p<=50.5 and (ccs or cha):
        tariff={'sessionFeeEur':2.0,'energyEurPerKwh':0.69,'postChargeGraceMinutes':45,
                'postChargeEurPerMinute':0.20,'rule':'TE63 non-subscriber rapid DC <=50kW'}
    if tariff: exact.append({**rec,**tariff,'sourceUrl':SOURCE})
    else: gaps.append({**rec,'connectorFlags':{'ccs':ccs,'chademo':cha,'type2':t2,'ef':ef},
                       'reason':'official_grid_not_deterministically_mapped'})
out={
 'schemaVersion':'1.0.0','dataset':'chargezy-te63-official-direct-france',
 'generatedAt':datetime.now(timezone.utc).isoformat(),'country':'FR','operator':'SPIE CityNetworks','network':'CHARGEZY - TE63',
 'classification':{'officialFirstPartyTariff':True,'directCpoOnly':True,'roamingIncluded':False,
                   'exactNetworkAndConnectorRuleRequired':True,'failClosed':True},
 'source':{'url':SOURCE,'panUrl':pan,'panLastModified':cand[0][1].get('last_modified') or cand[0][1].get('modified')},
 'officialNonSubscriberGrid':{
   'normalACUpTo22kVA':{'sessionFeeEur':2.0,'energyEurPerKwh':0.59,'postChargeEurPerMinute':0.10,'postChargeAfterMinutes':180,'waived':'23:00-07:00'},
   'normalDCUpTo25kW':{'sessionFeeEur':2.0,'energyEurPerKwh':0.59,'postChargeEurPerMinute':0.10,'postChargeAfterMinutes':90},
   'rapidAC43kVA_or_DC50kW':{'sessionFeeEur':2.0,'energyEurPerKwh':0.69,'postChargeEurPerMinute':0.20,'postChargeAfterMinutes':45},
   'specialContactlessCard':{'fixedEur':25.0,'scope':'ZAC des Coustilles, Saint-Germain-Lembron only'}
 },
 'coverage':{'panRows':len(target),'exactRows':len(exact),'specialPaymentModeRows':len(special),'gaps':len(gaps),
             'coveragePct':round(100*len(exact)/len(target),3) if target else 0},
 'exact':exact,'specialPaymentMode':special,'gaps':gaps
}
assert len(target)>=280, len(target)
assert len(exact)+len(special)+len(gaps)==len(target)
p=ROOT/'data/operator_direct/chargezy_te63_official_france.json'; p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
q=ROOT/'reports/france/spie-citynetworks/chargezy-te63-summary.json'; q.parent.mkdir(parents=True,exist_ok=True)
q.write_text(json.dumps({'generatedAt':out['generatedAt'],'coverage':out['coverage'],'specialPaymentMode':special,'gaps':gaps},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
groups={}
for row in exact:
    groups.setdefault(row['rule'],[]).append(row['id_pdc_itinerance'])
offers=[]
for idx,(rule,ids) in enumerate(sorted(groups.items()),1):
    sample=next(x for x in exact if x['rule']==rule)
    pricing_rule={'scope':'allDay','start':'00:00','end':'24:00','billing':'kwh','currency':'EUR',
                  'pricePerKwh':sample['energyEurPerKwh'],'sessionFeeEur':sample['sessionFeeEur']}
    offers.append({
      'id':f'chargezy-te63-{idx:02d}','selectionId':f'chargezy-te63-{idx:02d}',
      'provider':'Chargezy TE63 direct','countries':['FR'],'currency':'EUR','priority':132,
      'pricing':{'type':'rules','rules':[pricing_rule],
                 'postChargeFee':{'eurPerMinute':sample['postChargeEurPerMinute'],'graceMinutes':sample['postChargeGraceMinutes']}},
      'source':'TE63 official mobility tariff + exact current PAN EVSE mapping',
      'directOperatorOnly':True,'verifiedScope':'exact_evse','defaultSelected':False,
      'evseIds':sorted(ids),'operatorAliases':['CHARGEZY - TE63','Chargezy','TE63','SPIE CityNetworks'],
      'metadata':{'network':'CHARGEZY - TE63','rule':rule,'exactEvseCount':len(ids),
                  'postChargeWaived':sample.get('postChargeWaived'),'sourceUrl':SOURCE,
                  'fallback':'Electra then Electroverse'}
    })
runtime={'schemaVersion':'1.0.0','country':'FR','generatedAt':out['generatedAt'],
         'mode':'operator-direct-exact-evse','policy':{'failClosed':True,'roamingIncluded':False},
         'directOffers':offers,'subscriptionOffers':[],
         'sourceEvidence':{'panRows':len(target),'exactRows':len(exact),'specialPaymentModeRows':len(special),'gaps':len(gaps)}}
rp=ROOT/'v9-production-runtime/data/v9/france-chargezy-te63-offers.json'; rp.parent.mkdir(parents=True,exist_ok=True)
rp.write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')
print(json.dumps({'coverage':out['coverage'],'runtimeOffers':len(offers),'runtimeEvse':sum(len(x['evseIds']) for x in offers),'special':special,'gaps':gaps},ensure_ascii=False,indent=2))
