#!/usr/bin/env python3
"""Read-only myAtlante national extraction. Credential supplied only via environment."""
import os, json, time, argparse, urllib.request, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone

ROOT='https://pdefweushaapiam01.azure-api.net/app-backend/v1/tenants/390c3ff9-b41c-42dc-aa48-1dd51ad6ce39'
COUNTRIES={'FR': ('ATL', (41,-6,52,10)), 'IT': ('ATE',(35,6,48,19))}
OFFLINE=False
RESUME=False
def now(): return datetime.now(timezone.utc).isoformat()
def write(p, data):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def request(path):
    headers={'Ocp-Apim-Subscription-Key':os.environ['ATLANTE_API_SUBSCRIPTION_KEY'],'Accept-Language':'fr','X-App-Version':'2.1.0','X-App-Platform':'android','Accept':'application/json'}
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(ROOT+path,headers=headers),timeout=45) as r: return json.load(r)
        except Exception:
            if attempt==3: raise
            time.sleep(2**attempt)
def simple_price(t):
    cs=t.get('priceComponents') or []
    if len(cs)!=1: return None
    c=cs[0]
    if c.get('priceDimension')!='ENERGY' or c.get('currency')!='EUR' or c.get('conditions') or c.get('surchargeName'): return None
    v=c.get('validity') or {}
    for section in v.values():
        if isinstance(section,dict) and any(x is not None and x!=[] and x!={} and x!='' for x in section.values()): return None
    p=(c.get('price') or {}).get('incl_vat')
    return p if isinstance(p,(int,float)) and p>=0 else None
def run(country,out,workers):
    party,bbox=COUNTRIES[country]; dest=out/country; started=now()
    prior=json.loads((dest/'report.json').read_text()) if OFFLINE and (dest/'report.json').exists() else {}
    if prior: started=prior['startedAt']
    def map_area(box,label):
        a,b,c,d=box
        q=urllib.parse.urlencode({'latLongBottomLeft':f'{a},{b}','latLongTopRight':f'{c},{d}','evseTypes':'AC,DC,HPC','locationStatus':'ALL','includeCpos':country+party})
        raw=dest/'raw'/f'map-{label}.json'
        data=json.loads(raw.read_text()) if (OFFLINE or (RESUME and raw.exists())) else request('/map-locations?'+q)
        if not OFFLINE and not raw.exists(): write(raw,data)
        return data
    national=map_area(bbox,'national')
    inventory={}; checks=[]
    def absorb(data,label):
        ls=data.get('locations') or []; ss=data.get('locationSummaries') or []
        checks.append({'area':label,'locations':len(ls),'summaries':len(ss)})
        for s in ls:
            if s.get('countryCode')==country and s.get('partyId')==party: inventory[s['id']]=s
        return bool(ss)
    absorb(national,'national'); national_ids=set(inventory)
    a,b,c,d=bbox; m=(a+c)/2; n=(b+d)/2
    boxes=[(a,b,m,n),(a,n,m,d),(m,b,c,n),(m,n,c,d)]
    pending=[(box,str(i),0) for i,box in enumerate(boxes)]
    while pending:
        box,label,depth=pending.pop(0)
        data=map_area(box,label)
        clustered=absorb(data,label)
        if clustered:
            if depth>=5: raise RuntimeError('Unresolved map clusters at '+label)
            a,b,c,d=box;m=(a+c)/2;n=(b+d)/2
            pending.extend((bb,label+'-'+str(i),depth+1) for i,bb in enumerate([(a,b,m,n),(a,n,m,d),(m,b,c,n),(m,n,c,d)]))
    print(country,'inventory',len(inventory),'national',len(national_ids),'added by tiles',len(set(inventory)-national_ids),flush=True)
    locations=[];errors=[];dimensions=Counter();tariff_count=0
    def hydrate(s):
        sid=s['id']; dp=dest/'raw'/'details'/(sid+'.json');tp=dest/'raw'/'tariffs'/(sid+'.json')
        detail=json.loads(dp.read_text()) if (OFFLINE or (RESUME and dp.exists())) else request('/locations/'+sid)
        if not OFFLINE and not dp.exists(): write(dp,detail)
        tariffs=json.loads(tp.read_text()) if (OFFLINE or (RESUME and tp.exists())) else request('/locations/'+sid+'/tariffs')
        if not OFFLINE and not tp.exists(): write(tp,tariffs)
        op=str(detail.get('operatorName') or '').strip()
        if detail.get('id')!=sid or detail.get('countryCode')!=country or detail.get('partyId')!=party or (op and 'atlante' not in op.lower()): raise ValueError('Operator or identifier mismatch: '+sid)
        idx={}
        for t in tariffs:
            ids=t.get('identifiers') or {}; k=(ids.get('evseId'),ids.get('connectorId'));idx.setdefault(k,[]).append(t)
        connectors=[]
        for e in detail.get('evses') or []:
            for c in e.get('connectors') or []:
                ts=idx.get((e.get('evseId'),c.get('evseConnectorId')),[])
                ps=[simple_price(t) for t in ts]
                price=ps[0] if ps and all(p is not None and p==ps[0] for p in ps) else None
                connectors.append({'evseId':e.get('evseId'),'connectorId':c.get('evseConnectorId'),'connectorType':c.get('evseCommonConnectorType'),'powerType':c.get('evsePowerType'),'powerKw':c.get('max_electric_power'),'status':e.get('evseStatus'),'statusLastUpdated':e.get('statusLastUpdated'),'pricePerKwhEur':price,'tariffs':ts})
        loc={k:detail.get(k) for k in ['id','locationId','countryCode','partyId','operatorName','subOperatorName','address','postalCode','city','coordinates','locationOpenTwentyFourSeven','openingTimes']}
        loc['name']=detail.get('displayName') or detail.get('locationName');loc['connectors']=connectors
        loc['operatorVerification']='countryCode+partyId+operatorName' if op else 'countryCode+partyId; operatorName missing in source'
        matched={(c['evseId'],c['connectorId']) for c in connectors}
        loc['unmatchedTariffs']=[t for k,ts in idx.items() if k not in matched for t in ts]
        return loc,tariffs
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(hydrate,s):sid for sid,s in inventory.items()}
        for i,f in enumerate(as_completed(fs),1):
            try:
                loc,ts=f.result();locations.append(loc);tariff_count+=len(ts)
                dimensions.update(c.get('priceDimension','UNKNOWN') for t in ts for c in t.get('priceComponents',[]))
            except Exception as e: errors.append({'id':fs[f],'error':str(e)})
            if i%25==0 or i==len(fs): print(country,'hydrated',i,'/',len(fs),'errors',len(errors),flush=True)
    connectors=[c for l in locations for c in l['connectors']]
    prices=Counter(str(c['pricePerKwhEur']) for c in connectors if c['pricePerKwhEur'] is not None)
    report={'startedAt':started,'completedAt':now(),'country':country,'cpo':country+party,'scope':'Stations Atlante publiees par myAtlante, tarif direct sans abonnement; partenaires et Atlante Go exclus. France: metropole et Corse. Italie: peninsule et iles dans le rectangle indique.','boundingBox':bbox,'coverageChecks':checks,'nationalMapStations':len(national_ids),'tileAddedStations':len(set(inventory)-national_ids),'inventoryStations':len(inventory),'extractedStations':len(locations),'connectorCount':len(connectors),'tariffRecords':tariff_count,'pricedConnectors':sum(prices.values()),'unpricedConnectors':len(connectors)-sum(prices.values()),'unmatchedTariffs':sum(len(l['unmatchedTariffs']) for l in locations),'priceCounts':dict(sorted(prices.items(),key=lambda kv:float(kv[0]))),'dimensions':dict(dimensions),'errors':errors}
    report['operatorNameMissingStations']=sum(not l.get('operatorName') for l in locations)
    if OFFLINE:
        report['completedAt']=prior.get('completedAt',report['completedAt']);report['normalizedAt']=now();report['rebuiltFromSavedRaw']=True
    write(dest/'report.json',report);write(dest/'stations.json',{'metadata':report,'locations':sorted(locations,key=lambda l:l['id'])})
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--countries',nargs='+',choices=COUNTRIES,default=['FR','IT']);p.add_argument('--out',type=Path,default=Path('results'));p.add_argument('--workers',type=int,default=8);p.add_argument('--rebuild-from-raw',action='store_true');p.add_argument('--resume',action='store_true');args=p.parse_args()
    OFFLINE=args.rebuild_from_raw
    RESUME=args.resume
    if not OFFLINE and not os.environ.get('ATLANTE_API_SUBSCRIPTION_KEY'): p.error('Set ATLANTE_API_SUBSCRIPTION_KEY')
    for country in args.countries: run(country,args.out,max(1,min(args.workers,12)))
