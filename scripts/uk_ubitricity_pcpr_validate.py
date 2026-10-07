#!/usr/bin/env python3
"""Validate PCPR prices against public PAYG details, then compile exact offers.
PCPR prices exclude VAT; PAYG detail prices include VAT. Preserve OCPI element
order. Provider stop times ending :59 include that last minute, corroborated
by PAYG bands and the official pricing page. Never guess a missing tariff.
"""
import copy, gzip, json, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DAYS = ['MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY']
PORTAL = 'https://api.shell.com/ubitricity/direct-access/api/direct-access/locations/'

def minute(value):
    h,m = map(int,value.split(':'))
    if not (0 <= h <= 24 and 0 <= m < 60 and (h < 24 or m == 0)):
        raise ValueError('invalid time')
    return h*60+m

def price(pc, gross):
    if pc.get('type',pc.get('dimensionType')) != 'ENERGY' or pc.get('step_size',pc.get('stepSize')) != 1:
        raise ValueError('unsupported price component')
    v=Decimal(str(pc['price']))
    if v < 0: raise ValueError('negative price')
    if not gross:
        if pc.get('vat') != 20: raise ValueError('unknown VAT')
        v *= Decimal('1.2')
    return float(v.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))

def grid(elements, day, gross=False):
    result=[None]*1440
    for el in elements:
        r=el.get('restrictions') or {}
        allowed={'startTime','stopTime'} if gross else {'start_time','end_time','day_of_week','min_duration'}
        if set(r)-allowed or r.get('min_duration',0) != 0: raise ValueError('unsupported restrictions')
        if not gross and r.get('day_of_week') and DAYS[day] not in r['day_of_week']: continue
        start=minute(r.get('startTime' if gross else 'start_time','00:00'))
        raw_end=r.get('stopTime' if gross else 'end_time','24:00')
        end=minute(raw_end)
        if raw_end.endswith(':59'): end+=1
        if end <= start: raise ValueError('unsupported overnight range')
        pcs=el.get('priceComponents' if gross else 'price_components',[])
        if len(pcs)!=1: raise ValueError('unsupported multiple dimensions')
        cost=price(pcs[0],gross)
        for m in range(start,end):
            if result[m] is None: result[m]=cost
    if any(v is None for v in result): raise ValueError('incomplete daily coverage')
    return result

def public_sample(eid,cid,tid):
    req=urllib.request.Request(PORTAL+eid,headers={'User-Agent':'TeslaChargeCompanion/9 PAYG validation'})
    with urllib.request.urlopen(req,timeout=45) as r: payload=json.load(r)
    matches=[t for e in payload.get('evses',[]) if e.get('id')==eid for c in e.get('connectors',[]) if str(c.get('id'))==cid for t in c.get('tariffs',[]) if str(t.get('id'))==tid]
    if len(matches)!=1: raise ValueError('exact PAYG connector tariff missing or ambiguous')
    t=matches[0]
    if t.get('currency')!='GBP': raise ValueError('PAYG currency mismatch')
    # Only sanitized tariff evidence is stored, never authorizationReference.
    return {'evseId':eid,'connectorId':cid,'tariffId':tid,
            'currentDayTariffs':t.get('currentDayTariffs'), 'nextDayTariffs':t.get('nextDayTariffs')}

def hm(m): return f'{m//60:02d}:{m%60:02d}'

def rules_for(week,idle):
    groups=defaultdict(list)
    for d,values in enumerate(week):
        start=0
        while start<1440:
            rate=.05 if idle and 480 <= start < 1200 else 0
            end=start+1
            while end<1440 and values[end]==values[start] and (.05 if idle and 480 <= end < 1200 else 0)==rate: end+=1
            groups[(start,end,values[start],rate)].append(DAYS[d])
            start=end
    return [{'scope':'allDay' if a==0 and b==1440 else 'timeWindow','start':hm(a),'end':hm(b),
             'billing':'kwh','currency':'GBP','pricePerKwh':v,'chargePerMinute':0,'connectionFee':0,
             'idlePerMinute':0,'postChargeRate':rate,'postChargeGraceMinutes':60,
             'days':None if len(days)==7 else days,'ocpiDurationBands':[]}
            for (a,b,v,rate),days in groups.items()]

def main():
    raw=json.load(gzip.open(ROOT/'data/national/uk_ubitricity_pcpr.json.gz','rt'))
    by_key={}; refs=defaultdict(list); seen=set()
    for t in raw['tariffs']:
        k=(t.get('country_code'),t.get('party_id'),str(t['id']))
        if k in by_key: raise ValueError('duplicate compound tariff identity')
        by_key[k]=t
    for l in raw['locations']:
        if l.get('country_code')!='GB' or l.get('party_id')!='UBI' or l.get('operator',{}).get('name')!='Ubitricity': raise ValueError('unexpected CPO/country scope')
        k=(l['country_code'],l['party_id'],str(l['id']))
        if k in seen: raise ValueError('duplicate location identity')
        seen.add(k)
        for e in l.get('evses',[]):
            for c in e.get('connectors',[]):
                ids=c.get('tariff_ids',[])
                if len(ids)==1: refs[(l['country_code'],l['party_id'],str(ids[0]))].append((e.get('evse_id'),str(c['id'])))
    now=datetime.now(timezone.utc); day=now.astimezone(__import__('zoneinfo').ZoneInfo('Europe/London')).weekday()
    valid={}; evidence={}; rejected={}
    for key,pairs in refs.items():
        tid=key[2]
        try:
            t=by_key[key]
            if t.get('currency')!='GBP': raise ValueError('unsupported currency')
            week=[grid(t['elements'],d) for d in range(7)]
            samples=[]
            for eid,cid in dict.fromkeys([pairs[0],pairs[-1]]):
                s=public_sample(eid,cid,tid)
                if grid(s['currentDayTariffs'],day,True)!=week[day] or grid(s['nextDayTariffs'],(day+1)%7,True)!=week[(day+1)%7]:
                    raise ValueError('PCPR/PAYG time-band or price conflict')
                samples.append(s)
            valid[key]=week; evidence[tid]=samples
        except (ValueError,KeyError,TypeError,OSError) as ex:
            rejected[tid]=str(ex) if isinstance(ex,(ValueError,KeyError,TypeError)) else 'public PAYG validation unavailable'
    if not valid: raise ValueError('no tariff passed independent PAYG verification')
    locations=copy.deepcopy(raw['locations']); priced=0; exclusions=Counter(); ids=set(); affected=set()
    for l in locations:
        if l.get('time_zone')!='Europe/London' or l.get('publish') is not True: raise ValueError('non-public or unknown timezone')
        for e in l.get('evses',[]):
            eid=e.get('evse_id')
            for c in e.get('connectors',[]):
                cid=str(c['id']); k=(l['country_code'],l['party_id'],str((c.get('tariff_ids') or [''])[0]))
                identity=(eid,cid)
                if not eid or identity in ids: raise ValueError('duplicate or missing connector identity')
                ids.add(identity)
                if len(c.get('tariff_ids',[]))!=1 or k not in valid:
                    exclusions[rejected.get(k[2],'missing or ambiguous exact tariff')]+=1; affected.add(l['id']); c['tariff_ids']=[]; continue
                w=c.get('max_electric_power'); idle=isinstance(w,(float,int)) and 7000<=w<=22000
                c['validatedV9Offer']={'id':f'ubitricity-pcpr:{l["id"]}:{eid}:{cid}:{k[2]}','provider':'Ubitricity','kind':'direct','subscriptionId':None,
                    'countries':['GB'],'currency':'GBP','stationIds':[str(l['id'])],'evseIds':[eid],
                    'pricing':{'type':'rules','timeZone':'Europe/London','rules':rules_for(valid[k],idle)},
                    'metadata':{'connectorId':cid,'tariffId':k[2],'scope':'cpo_direct_payg_verified','collectedAt':raw['collectedAt'],
                                'vatIncluded':True,'paygVerification':True,'idleFeeSource':'https://ubitricity.com/en/driver/pricing/' if idle else None}}
                c['tariff_ids']=[]; priced+=1
    source={'id':'ubitricity-pcpr-payg','name':'Ubitricity','pricingScope':'cpo_direct_payg_verified','locations':locations,'tariffs':[]}
    report={'collectedAt':raw['collectedAt'],'validatedAt':now.isoformat(),'locations':len(locations),'connectors':len(ids),
            'pricedConnectors':priced,'unpricedConnectors':len(ids)-priced,'affectedLocations':len(affected),
            'validTariffIds':[k[2] for k in valid],'rejectedTariffs':rejected,'exclusionReasons':dict(exclusions),
            'countries':dict(Counter(l['country'] for l in locations)), 'otherCountriesAccessible':False,
            'crossCountryConclusion':'Complete unfiltered token feed contains GB only; FR/NL/DE require separately authorized scope',
            'pricingPolicy':'exact connector tariff, gross VAT, ordered OCPI elements, PAYG current/next day cross-check, London timezone',
            'publishedToV9':False,'status':'validated_runtime_input_ready','credentialsPersisted':False}
    outputs={'data/national/uk_ubitricity_v9.json.gz':{'collectedAt':raw['collectedAt'],'sources':[source]},
             'reports/uk/ubitricity-pcpr-validation-latest.json':report,
             'data/operator_direct/ubitricity_uk_pcpr_payg_evidence.json':{'validatedAt':now.isoformat(),'tariffs':evidence,'rejectedTariffs':rejected}}
    for path,obj in outputs.items():
        target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True)
        body=(json.dumps(obj,separators=(',',':'))+'\n').encode()
        target.write_bytes(gzip.compress(body,mtime=0) if path.endswith('.gz') else body)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
