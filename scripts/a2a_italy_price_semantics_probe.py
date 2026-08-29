#!/usr/bin/env python3
"""Stratified read-only probe of current A2A public user-facing station prices."""
from __future__ import annotations
import json,re,time
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import requests,urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ROOT='https://e-movinghub.a2a.it/acEicp/'
MAP=ROOT+'jsonGetMapDashboard.action'; DETAIL=ROOT+'jsonGetCuFromAlias.action'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/138 Safari/537.36'
PRICE_RE=re.compile(r'([0-9]+(?:[,.][0-9]+)?)\s*€\s*/\s*kWh',re.I)
MIN_RE=re.compile(r'([0-9]+(?:[,.][0-9]+)?)\s*€\s*/\s*min',re.I)
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def post(s,url,obj):
    r=s.post(url,json=obj,timeout=40,verify=False,headers={'Accept':'application/json,text/javascript,*/*;q=0.1','X-Requested-With':'XMLHttpRequest'});r.raise_for_status();return r.json()
def num(rx,s):
    m=rx.search(str(s or ''))
    return float(m.group(1).replace(',','.')) if m else None
def owned(x):return isinstance(x,dict) and isinstance(x.get('assetProvider'),dict) and x['assetProvider'].get('external') is False
def main():
    s=requests.Session();s.headers.update({'User-Agent':UA,'Accept-Language':'it-IT,it;q=0.9,en;q=0.5'})
    rows=post(s,MAP,{})
    own=[x for x in rows if owned(x)]
    bytype=defaultdict(list)
    for x in own:bytype[str(x.get('type') or 'UNKNOWN').upper()].append(x)
    # Sample up to 4 geographically/order-diverse aliases per current map type.
    chosen=[]
    for typ,arr in sorted(bytype.items()):
        if not arr:continue
        idxs=sorted(set([0,len(arr)//3,(2*len(arr))//3,len(arr)-1]))
        for i in idxs:chosen.append(arr[i])
    samples=[];price_dist=Counter();penalty_dist=Counter();type_price=Counter();schema_keys=Counter();fail=[]
    for x in chosen:
        alias=str(x.get('alias'))
        try:d=post(s,DETAIL,{'aliasCu':alias})
        except Exception as e:fail.append({'alias':alias,'type':x.get('type'),'error':type(e).__name__});continue
        plugs=[]
        for ev in d.get('evseData') or []:
            if isinstance(ev,dict):schema_keys.update(ev.keys())
            for p in (ev.get('plugs') or []) if isinstance(ev,dict) else []:
                ep=num(PRICE_RE,p.get('priceList'));pm=num(MIN_RE,p.get('penaltyList'))
                if ep is not None:price_dist[f'{ep:.3f}']+=1;type_price[f"{str(x.get('type')).upper()}:{ep:.3f}"]+=1
                if pm is not None:penalty_dist[f'{pm:.3f}']+=1
                plugs.append({'id':p.get('id'),'plugId':p.get('plugId'),'plugType':p.get('plugType'),'maxPowerKw':p.get('maxPower'),'status':p.get('status'),'priceList':p.get('priceList'),'energyEurPerKwh':ep,'penaltyList':p.get('penaltyList'),'occupancyEurPerMin':pm})
        samples.append({'alias':alias,'mapType':x.get('type'),'mapStatus':x.get('statusCu'),'city':x.get('city'),'address':x.get('address'),'detailType':d.get('type'),'typeDesc':d.get('typeDesc'),'maxPowerKw':d.get('maxPower'),'costobase':d.get('costobase'),'descCostobase':d.get('descCostobase'),'assetProvider':d.get('assetProvider'),'plugs':plugs})
        time.sleep(.05)
    out={'generatedAt':now(),'security':{'accountCredentialsUsed':False,'authorizationMaterialPersisted':False,'rechargeOrAuthEndpointsCalled':False,'tlsCertificateVerificationDisabledForPublicA2aHost':True},'counts':{'mapRecords':len(rows),'a2aOwnedStations':len(own),'mapTypeDistribution':{k:len(v) for k,v in sorted(bytype.items())},'sampleStations':len(samples),'failedDetails':len(fail)},'distributions':{'plugEnergyEurPerKwh':dict(price_dist),'plugOccupancyEurPerMin':dict(penalty_dist),'mapTypeEnergy':dict(type_price),'evseObjectKeys':dict(schema_keys)},'samples':samples,'failures':fail}
    p=Path('data/reports/a2a_italy_price_semantics_probe.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'counts':out['counts'],'distributions':out['distributions'],'samples':[{'alias':q['alias'],'mapType':q['mapType'],'maxPowerKw':q['maxPowerKw'],'costobase':q['costobase'],'descCostobase':q['descCostobase'],'plugPrices':[(p['maxPowerKw'],p['priceList'],p['penaltyList']) for p in q['plugs']]} for q in samples]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
