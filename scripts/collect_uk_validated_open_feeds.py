#!/usr/bin/env python3
# Data Lab migration verification: canonical UK collector now runs from tesla-charge-companion-data-lab.
import argparse,json,time,urllib.parse,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
UA='TeslaChargeCompanion/9 UK-open-data collector'
# SmartCharging note: final page size must not exceed remaining rows advertised by meta.total.
SOURCES=[
{'name':'Clenergy EV','party_ids':['CEV'],'locations':'https://api.clenergy.online/development/pcpr/locations','tariffs':'https://api.clenergy.online/development/pcpr/tariffs','mode':'single'},
{'name':'PoGo Charge','party_ids':['POG'],'locations':'https://info.smartcharging.uk/public_feed/locations/4009','tariffs':'https://info.smartcharging.uk/public_feed/locations/4009/tariffs','mode':'pogo_hybrid'},
{'name':'Arnold Clark Charge','party_ids':['ACC'],'locations':'https://api.fuuse.io/opendata/e6397b95-1624-49cd-824d-ab2f9dfe7294/location','tariffs':'https://api.fuuse.io/opendata/e6397b95-1624-49cd-824d-ab2f9dfe7294/tariff','mode':'single'},
{'name':'Urban Fox Networks','party_ids':['UFX'],'locations':'https://api.urbanfox.network/api/opendata/locations','tariffs':'https://api.urbanfox.network/api/opendata/tariffs','mode':'offset'},
{'name':'ChargePlace Scotland','party_ids':['CPS'],'locations':'https://info.smartcharging.uk/public_feed/locations/2463','tariffs':'https://info.smartcharging.uk/public_feed/locations/2463/tariffs','mode':'offset'},
{'name':'Evolt Network','party_ids':['SSM','PO2','CP2','SS2'],'locations':'https://info.smartcharging.uk/public_feed/locations/3666','tariffs':'https://info.smartcharging.uk/public_feed/locations/3666/tariffs','mode':'offset'}]

def request_json(url,timeout=90,retries=7):
    last=None
    for attempt in range(retries):
        req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8')),dict(r.headers.items())
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,json.JSONDecodeError) as e:
            last=f'{type(e).__name__}: {e}'
            if isinstance(e,urllib.error.HTTPError) and e.code not in (429,500,502,503,504): break
            retry_after=None
            if isinstance(e,urllib.error.HTTPError):
                try: retry_after=float(e.headers.get('Retry-After')) if e.headers.get('Retry-After') else None
                except Exception: retry_after=None
            time.sleep(retry_after if retry_after is not None else min(60,3*(2**attempt)))
    raise RuntimeError(f'GET failed for {url}: {last}')

def array_from_payload(payload):
    if isinstance(payload,list): return payload
    if isinstance(payload,dict):
        for key in ('data','locations','tariffs','items','results'):
            if isinstance(payload.get(key),list): return payload[key]
    return []

def add_query(url,**params):
    p=urllib.parse.urlsplit(url); q=dict(urllib.parse.parse_qsl(p.query)); q.update({k:str(v) for k,v in params.items() if v is not None})
    return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,urllib.parse.urlencode(q),p.fragment))

def fetch_offset(url,page_size=50):
    rows=[]; offset=0; guard=0; total=None
    while True:
        current_limit=page_size if total is None else min(page_size,max(1,total-offset))
        payload,headers=request_json(add_query(url,limit=current_limit,offset=offset)); batch=array_from_payload(payload); rows.extend(batch)
        meta=payload.get('meta') if isinstance(payload,dict) else {}; meta=meta if isinstance(meta,dict) else {}
        observed_total=meta.get('total')
        if observed_total is None: observed_total=headers.get('X-Total-Count') or headers.get('x-total-count')
        try:
            if observed_total is not None: total=int(observed_total)
        except Exception: pass
        guard+=1
        if not batch or (total is not None and len(rows)>=total) or (len(batch)<current_limit and total is None): break
        offset+=len(batch)
        if guard>1000: raise RuntimeError(f'pagination guard hit for {url}')
    return rows


POGO_OFFICIAL_PRICING={'AC':0.56,'DC':0.65,'currency':'GBP','unit':'kWh','source':'https://pogocharge.com/pricing/'}

def fetch_pogo_hybrid(src):
    # SmartCharging tenant 4009 reports 159 locations but its final record
    # currently returns HTTP 500. Fetch the stable bulk portion, then probe
    # every tail row individually so one malformed row cannot hide the rest.
    smart=[]; reported_total=None; failed_offsets=[]
    for offset in (0,50,100):
        payload,_=request_json(add_query(src['locations'],limit=50,offset=offset))
        batch=array_from_payload(payload); smart.extend(batch)
        meta=payload.get('meta') if isinstance(payload,dict) else {}
        if isinstance(meta,dict) and meta.get('total') is not None:
            try: reported_total=int(meta['total'])
            except Exception: pass

    tail_end=reported_total if reported_total is not None else 159
    for offset in range(150,tail_end):
        try:
            payload,_=request_json(add_query(src['locations'],limit=1,offset=offset),retries=2)
            batch=array_from_payload(payload)
            if batch: smart.extend(batch)
            else: failed_offsets.append(offset)
        except Exception:
            failed_offsets.append(offset)

    # Deduplicate defensively by SmartCharging location id.
    dedup={}
    for loc in smart:
        if isinstance(loc,dict) and loc.get('id') is not None:
            dedup[str(loc.get('id'))]=loc
    smart=list(dedup.values())

    # Current public PoGo pricing is network-wide by AC/DC. Preserve the
    # source tariff ids for audit, but give TCC a stable current tariff join.
    for loc in smart:
        for evse in loc.get('evses') or []:
            for c in evse.get('connectors') or []:
                original=list(c.get('tariff_ids') or [])
                if original: c['_source_tariff_ids']=original
                ptype=str(c.get('power_type') or '').upper()
                if ptype.startswith('DC'):
                    c['tariff_ids']=['POGO-DIRECT-DC']
                    c['tcc_direct_price_gbp_per_kwh']=POGO_OFFICIAL_PRICING['DC']
                elif ptype.startswith('AC'):
                    c['tariff_ids']=['POGO-DIRECT-AC']
                    c['tcc_direct_price_gbp_per_kwh']=POGO_OFFICIAL_PRICING['AC']

    tariffs=[
        {'country_code':'GB','party_id':'POG','id':'POGO-DIRECT-AC','currency':'GBP',
         'elements':[{'price_components':[{'type':'ENERGY','price':POGO_OFFICIAL_PRICING['AC'],'vat':None,'step_size':1}]}],
         'source':POGO_OFFICIAL_PRICING['source'],'tcc_current_direct_tariff':True},
        {'country_code':'GB','party_id':'POG','id':'POGO-DIRECT-DC','currency':'GBP',
         'elements':[{'price_components':[{'type':'ENERGY','price':POGO_OFFICIAL_PRICING['DC'],'vat':None,'step_size':1}]}],
         'source':POGO_OFFICIAL_PRICING['source'],'tcc_current_direct_tariff':True}
    ]
    audit={
        'smartChargingReportedTotal':reported_total,
        'smartChargingRecovered':len(smart),
        'failedOffsets':failed_offsets,
        'coverageComplete':reported_total is not None and len(smart)>=reported_total and not failed_offsets,
        'coveragePct':round((len(smart)/reported_total)*100,2) if reported_total else None,
        'pricingComplete':True,
        'directPricing':POGO_OFFICIAL_PRICING,
        'note':'PoGo public SmartCharging location offset 158 returned HTTP 500 on 2026-09-28; all other 158/159 rows were recovered. No inferred location is inserted.'
    }
    return smart,tariffs,audit

def fetch_source(src):
    if src['mode']=='pogo_hybrid':
        locations,tariffs,audit=fetch_pogo_hybrid(src)
        return locations,tariffs,audit
    if src['mode']=='offset':
        locations=fetch_offset(src['locations'],50)
        time.sleep(1.0)
        tariffs=fetch_offset(src['tariffs'],50)
        return locations,tariffs,None
    locations=array_from_payload(request_json(src['locations'])[0])
    if src['name']=='Arnold Clark Charge':
        time.sleep(5.0)
    else:
        time.sleep(0.5)
    tariffs=array_from_payload(request_json(src['tariffs'])[0])
    return locations,tariffs,None

def summarize(locations,tariffs):
    evses=connectors=0; linked=set(); statuses={}; parties=set(); usages={}
    for loc in locations:
        if not isinstance(loc,dict): continue
        if loc.get('party_id'): parties.add(str(loc['party_id']))
        for evse in loc.get('evses') or []:
            evses+=1; status=str(evse.get('status') or 'UNKNOWN'); statuses[status]=statuses.get(status,0)+1
            for c in evse.get('connectors') or []:
                connectors+=1
                for tid in c.get('tariff_ids') or []:
                    tid=str(tid); linked.add(tid)
                    usages.setdefault(tid,[]).append({
                        'locationId':loc.get('id'),'locationName':loc.get('name'),'address':loc.get('address'),
                        'city':loc.get('city'),'postalCode':loc.get('postal_code'),
                        'evseId':evse.get('evse_id') or evse.get('uid') or evse.get('id'),
                        'evseStatus':status,'connectorId':c.get('id'),
                        'maxElectricPower':c.get('max_electric_power'),'lastUpdated':c.get('last_updated') or evse.get('last_updated')
                    })
    tariff_ids={str(t.get('id')) for t in tariffs if isinstance(t,dict) and t.get('id') is not None}
    missing=linked-tariff_ids
    missing_usages={tid:usages.get(tid,[]) for tid in sorted(missing)}
    return {'locations':len(locations),'evses':evses,'connectors':connectors,'tariffs':len(tariffs),'partyIdsObserved':sorted(parties),'evseStatuses':statuses,'connectorTariffIds':len(linked),'resolvedTariffIds':len(linked&tariff_ids),'missingTariffIds':sorted(missing),'missingTariffUsages':missing_usages,'orphanTariffIds':len(tariff_ids-linked),'status':'complete' if locations and not missing else 'partial'}



CPS_TARIFF_OVERRIDES={
 '3387a23a-0e18-4632-9edd-4038bf165d91':{
   'country_code':'GB','party_id':'CPS','id':'3387a23a-0e18-4632-9edd-4038bf165d91','currency':'GBP',
   'elements':[{'price_components':[{'type':'ENERGY','price':0.57,'step_size':1}]}],
   'source':'Dundee City Council tariff from 2 June 2025','source_url':'https://www.drivedundeeelectric.co.uk/news/2025/05/21/electric-vehicle-charging-tariff-update-commencing-2nd-of-june-2025','tcc_manual_exact_override':True},
 '3ca85d89-1ef0-4393-8013-e598de0a5f73':{
   'country_code':'GB','party_id':'CPS','id':'3ca85d89-1ef0-4393-8013-e598de0a5f73','currency':'GBP',
   'elements':[{'price_components':[{'type':'FLAT','price':1.00,'step_size':1},{'type':'ENERGY','price':0.35,'step_size':1}]}],
   'tcc_minimum_fee_gbp':2.00,'source':'SEPA tariff published by ChargePlace Scotland','source_url':'https://chargeplacescotland.org/tariff/1st-september-2024-tariff-update/','tcc_manual_exact_override':True},
 '5a59d27e-06ff-4e4d-a7b4-3d38df625bed':{
   'country_code':'GB','party_id':'CPS','id':'5a59d27e-06ff-4e4d-a7b4-3d38df625bed','currency':'GBP',
   'elements':[{'price_components':[{'type':'ENERGY','price':0.40,'step_size':1}]}],
   'source':'North Lanarkshire Council current standard/fast tariff','source_url':'https://www.northlanarkshire.gov.uk/roads-parking-and-active-travel/electric-vehicle-charging/frequently-asked-questions','tcc_manual_exact_override':True},
 '705793bb-35cb-47aa-acba-abb8cc0f26f6':{
   'country_code':'GB','party_id':'CPS','id':'705793bb-35cb-47aa-acba-abb8cc0f26f6','currency':'GBP',
   'elements':[{'price_components':[{'type':'ENERGY','price':0.40,'step_size':1}]}],
   'source':'Fife Council current 7/22kW tariff','source_url':'https://www.fife.gov.uk/roads-travel-parking/electric-vehicle-network','tcc_manual_exact_override':True},
 '8b29e3a9-6904-4be2-af5b-1ef5c3c341fd':{
   'country_code':'GB','party_id':'CPS','id':'8b29e3a9-6904-4be2-af5b-1ef5c3c341fd','currency':'GBP',
   'elements':[{'price_components':[{'type':'ENERGY','price':0.50,'step_size':1}]}],
   'tcc_overstay':'GBP 10 after 6 hours','source':'University of St Andrews tariff published by ChargePlace Scotland','source_url':'https://chargeplacescotland.org/charge-point-tariffs/','tcc_manual_exact_override':True},
 'c1f90aac-2dae-4374-8a89-5692043f9044':{
   'country_code':'GB','party_id':'CPS','id':'c1f90aac-2dae-4374-8a89-5692043f9044','currency':'GBP',
   'elements':[{'price_components':[{'type':'ENERGY','price':0.40,'step_size':1}]}],
   'tcc_minimum_fee_gbp':1.00,'source':'West Lothian Council current slow/fast tariff','source_url':'https://www.westlothian.gov.uk/ev-charging','tcc_manual_exact_override':True},
 'c87a9ed3-24bd-44aa-9e19-efc1a3a7d6c6':{
   'country_code':'GB','party_id':'CPS','id':'c87a9ed3-24bd-44aa-9e19-efc1a3a7d6c6','currency':'GBP',
   'elements':[{'price_components':[{'type':'ENERGY','price':0.60,'step_size':1}]}],
   'source':'Dundee & Angus College tariff effective 1 July 2025','source_url':'https://chargeplacescotland.org/tariff/1st-july-2025-tariff-update/','tcc_manual_exact_override':True},
 'ce851197-82e4-4afe-b3cd-ba5aab5cacc6':{
   'country_code':'GB','party_id':'CPS','id':'ce851197-82e4-4afe-b3cd-ba5aab5cacc6','currency':'GBP',
   'elements':[{'price_components':[{'type':'ENERGY','price':0.50,'step_size':1}]}],
   'tcc_minimum_fee_gbp':1.50,'source':'The Crichton Trust tariff published by ChargePlace Scotland','source_url':'https://www.chargeplacescotland.org/tariff/1st-march-tariff-update-3/','tcc_manual_exact_override':True},
 'dc13dfd1-4b34-4020-b69f-a839c6baefa3':{
   'country_code':'GB','party_id':'CPS','id':'dc13dfd1-4b34-4020-b69f-a839c6baefa3','currency':'GBP',
   'elements':[{'price_components':[{'type':'FLAT','price':1.00,'step_size':1},{'type':'ENERGY','price':0.40,'step_size':1}]}],
   'source':'West Dunbartonshire Council slow/fast tariff','source_url':'https://chargeplacescotland.org/tariff/1st-june-tariff-update-announcement/','tcc_manual_exact_override':True},
 'f71fc44d-bdae-44f8-9075-90433602a9ee':{
   'country_code':'GB','party_id':'CPS','id':'f71fc44d-bdae-44f8-9075-90433602a9ee','currency':'GBP',
   'elements':[{'price_components':[{'type':'FLAT','price':1.00,'step_size':1},{'type':'ENERGY','price':0.40,'step_size':1}]}],
   'source':'Glasgow City Council current standard charging tariff','source_url':'https://www.chargeplacescotland.org/glasgow-city-council-tariffs/','tcc_manual_exact_override':True}
}

EVOLT_TARIFF_OVERRIDES={
    'bc7334e2-0c50-4f8b-9377-fcf55ccb4f37': {
        'country_code':'GB','party_id':'SSM','id':'bc7334e2-0c50-4f8b-9377-fcf55ccb4f37','currency':'GBP',
        'elements':[{'price_components':[{'type':'ENERGY','price':0.56,'vat':None,'step_size':1}]}],
        'source':'City of Edinburgh Council 22kW Fast tariff / Granton Western Village evidence',
        'source_urls':['https://www.edinburgh.gov.uk/public-transport/find-electric-vehicle-charging-points-edinburgh/2','https://www.edinburgh.gov.uk/public-transport/find-electric-vehicle-charging-points-edinburgh/3'],
        'tcc_manual_exact_override':True
    }
}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',default='artifacts/uk-validated-open-feeds.json'); ap.add_argument('--only',action='append'); args=ap.parse_args()
    wanted=set(args.only or []); selected=[s for s in SOURCES if not wanted or s['name'] in wanted]
    if wanted and len(selected)!=len(wanted): raise SystemExit('Unknown source(s): '+', '.join(sorted(wanted-{s['name'] for s in SOURCES})))
    result={'schemaVersion':1,'country':'GB','retrievedAt':datetime.now(timezone.utc).isoformat(),'policy':'Only operator-published or operator-linked open feeds already validated during the UK first/second pass are collected. No tariff extrapolation between stations or CPOs.','sources':[]}; failures=[]
    for src in selected:
        print(f"Collecting {src['name']}...",flush=True)
        try:
            locations,tariffs,source_audit=fetch_source(src)
            if src['name']=='Evolt Network':
                existing={str(t.get('id')) for t in tariffs if isinstance(t,dict)}
                tariffs.extend(v for k,v in EVOLT_TARIFF_OVERRIDES.items() if k not in existing)
            if src['name']=='ChargePlace Scotland':
                existing={str(t.get('id')) for t in tariffs if isinstance(t,dict)}
                tariffs.extend(v for k,v in CPS_TARIFF_OVERRIDES.items() if k not in existing)
            summary=summarize(locations,tariffs)
            if source_audit is not None:
                summary['sourceAudit']=source_audit
                if src['name']=='PoGo Charge':
                    if source_audit.get('coverageComplete') and not summary.get('missingTariffIds'):
                        summary['status']='complete'
                    else:
                        summary['status']='partial_location_feed'
                    summary['pricingStatus']='complete' if source_audit.get('pricingComplete') else 'partial'
            result['sources'].append({'name':src['name'],'partyIdsExpected':src['party_ids'],'endpoints':{'locations':src['locations'],'tariffs':src['tariffs']},'summary':summary,'sourceAudit':source_audit,'locations':locations,'tariffs':tariffs})
            print(json.dumps({'name':src['name'],**summary}),flush=True)
        except Exception as e:
            failures.append({'name':src['name'],'error':str(e)}); print(f"{src['name']} failed: {e}",flush=True)
    result['summary']={'requestedSources':len(selected),'successfulSources':len(result['sources']),'failedSources':len(failures),'totalLocations':sum(x['summary']['locations'] for x in result['sources']),'totalEvses':sum(x['summary']['evses'] for x in result['sources']),'totalConnectors':sum(x['summary']['connectors'] for x in result['sources']),'completeSources':sum(x['summary']['status']=='complete' for x in result['sources']),'partialSources':sum(x['summary']['status']=='partial' for x in result['sources'])}; result['failures']=failures
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result['summary']),flush=True)
    if failures: raise SystemExit(2)
if __name__=='__main__': main()
