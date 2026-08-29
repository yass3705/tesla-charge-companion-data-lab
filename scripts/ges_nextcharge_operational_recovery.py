#!/usr/bin/env python3
"""Retry only operational GES EVSE missing from the national NextCharge candidate.

Recovery remains exact-identity only: PUN ITGESE<n> must equal NextCharge
uidConnector <n>. Wider geographic searches are discovery aids only and never
constitute a match by themselves.
"""
from __future__ import annotations
import argparse,gzip,json,math,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL="https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
PREFIX="ITGESE"
RECOGNIZED_PRICE_KEYS={"energy","time","parking","session"}
ASYNC_FETCH=r"""
const done=arguments[arguments.length-1], path=arguments[0], params=arguments[1];
const ctrl=new AbortController(), timer=setTimeout(()=>ctrl.abort(),20000);
fetch('/apps/map/apis/'+path,{method:'POST',credentials:'same-origin',signal:ctrl.signal,
 headers:{'client-type':'webapp','Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
 body:new URLSearchParams(params).toString()}).then(async r=>{clearTimeout(timer);const t=await r.text();let j=null;try{j=JSON.parse(t)}catch(e){};
 done({ok:r.ok,httpStatus:r.status,json:j,textPrefix:j?null:t.slice(0,300)});
}).catch(e=>{clearTimeout(timer);done({error:String(e&&e.name||e),message:String(e).slice(0,220)});});
"""

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def fnum(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except Exception:return None
def coords(e):
    c=e.get('coordinates')
    if isinstance(c,list) and len(c)>=2:
        a,b=fnum(c[0]),fnum(c[1]);return (a,b) if a is not None and b is not None else None
    return None
def uid_from_eid(eid):
    s=str(eid or '').upper()
    if s.startswith(PREFIX) and s[len(PREFIX):].isdigit():return int(s[len(PREFIX):])
    return None
def dist_m(a,b):
    lat1,lon1,lat2,lon2=map(math.radians,[a[0],a[1],b[0],b[1]])
    dlat,dlon=lat2-lat1,lon2-lon1
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(h)))
def captcha(x):
    try:return 'CAPTCHA_REQUIRED' in json.dumps(x,ensure_ascii=False).upper()
    except Exception:return False
def api(driver,path,params):return driver.execute_async_script(ASYNC_FETCH,path,params)
def tariff_snapshot(c):
    tariff=(c.get('tariff') or {}) if isinstance(c,dict) else {}
    charge=(tariff.get('charge') or {}) if isinstance(tariff,dict) else {}
    prices=(charge.get('prices') or {}) if isinstance(charge,dict) else {}
    restrictions=(charge.get('restrictions') or {}) if isinstance(charge,dict) else {}
    prices={str(k):v for k,v in prices.items()} if isinstance(prices,dict) else {}
    unknown=sorted(set(prices)-RECOGNIZED_PRICE_KEYS)
    numeric=bool(prices) and not unknown and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v)) for v in prices.values())
    usable=str(tariff.get('currency') or '').upper()=='EUR' and numeric
    return {'currency':tariff.get('currency'),'prices':prices,'restrictions':restrictions,'preAuth':tariff.get('preAuth'),'recognizedPriceKeysOnly':not unknown,'unknownPriceKeys':unknown,'numericRecognizedPrices':numeric,'consumerTariffSnapshotUsable':usable}
def connectors(driver,sid,os_type,app_version):
    out=[];seen=set();fails=[]
    for page in range(4):
        x=api(driver,'stationConnectors',{'idStation':str(sid),'reservable':'0','limit':'100','offset':str(page*100),'osType':str(os_type),'appVersion':str(app_version)})
        if captcha(x):return out,'CAPTCHA_REQUIRED',fails
        if not isinstance(x,dict) or not x.get('ok'):
            fails.append({'page':page,'httpStatus':x.get('httpStatus') if isinstance(x,dict) else None});break
        arr=((x.get('json') or {}).get('data') or [])
        if not isinstance(arr,list):break
        added=0
        for c in arr:
            key=str(c.get('uidConnector')) if isinstance(c,dict) else repr(c)
            if key not in seen:seen.add(key);out.append(c);added+=1
        if not bool((x.get('json') or {}).get('hasMore')) and len(arr)<100:break
        if not arr or not added:break
    return out,None,fails

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pun',required=True);ap.add_argument('--candidate',required=True);args=ap.parse_args()
    with gzip.open(args.pun,'rt',encoding='utf-8') as f:pun=json.load(f)
    with gzip.open(args.candidate,'rt',encoding='utf-8') as f:cand=json.load(f)
    matched={str(e.get('evseId') or '').upper() for e in cand.get('entries',[])}
    targets=[]
    for e in pun.get('evses',[]):
        eid=str(e.get('evseId') or '').upper()
        if str(e.get('partyId') or '').upper()!='GES' or e.get('operationalState')!='operational' or eid in matched:continue
        u=uid_from_eid(eid);c=coords(e)
        if u is not None and c:targets.append((eid,u,c,e))
    targets.sort()
    opts=Options();opts.page_load_strategy='none'
    for x in ('--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1440,1600','--lang=it-IT','--disable-geolocation'):opts.add_argument(x)
    d=webdriver.Chrome(options=opts);d.set_script_timeout(30)
    cache={};recovered=[];unresolved=[];failures=[];stopped=None;request_counts=Counter();browser_errors=[]
    levels=[
      {'name':'wide_1_5km','dlat':0.014,'dlon':0.020,'maxm':1600,'cap':100},
      {'name':'wide_5km','dlat':0.045,'dlon':0.065,'maxm':5200,'cap':220},
    ]
    try:
        d.set_page_load_timeout(20)
        try:d.get(MAP_URL)
        except TimeoutException:browser_errors.append('page_load_timeout')
        time.sleep(7)
        rt=d.execute_script("""const s=n=>{try{return typeof window[n]==='undefined'?null:window[n]}catch(e){return null}};return {osType:s('osType'),appVersion:s('appVersion')};""") or {}
        os_type=rt.get('osType') or 'desktop';app_version=rt.get('appVersion') or '6.1.4'
        for i,(eid,uid,(lat,lon),pe) in enumerate(targets,1):
            found=None;attempts=[]
            for lvl in levels:
                grid=api(d,'stationsGrid',{'lonSW':str(lon-lvl['dlon']),'lonNE':str(lon+lvl['dlon']),'latSW':str(lat-lvl['dlat']),'latNE':str(lat+lvl['dlat']),'favorites':'false','userCountry':'IT','owner':'ITGES','osType':str(os_type),'appVersion':str(app_version),'idGroupProvider':''})
                request_counts['stationsGrid']+=1
                if captcha(grid):stopped='CAPTCHA_REQUIRED';break
                if not isinstance(grid,dict) or not grid.get('ok'):
                    failures.append({'evseId':eid,'kind':'grid','level':lvl['name'],'httpStatus':grid.get('httpStatus') if isinstance(grid,dict) else None});continue
                arr=((grid.get('json') or {}).get('data') or [])
                near=[]
                for g in arr if isinstance(arr,list) else []:
                    try:gc=(float(g.get('latitude')),float(g.get('longitude')))
                    except Exception:continue
                    dm=dist_m((lat,lon),gc)
                    if dm<=lvl['maxm']:near.append((dm,g))
                near.sort(key=lambda x:x[0]);attempts.append({'level':lvl['name'],'gridStations':len(arr) if isinstance(arr,list) else 0,'withinRadius':len(near)})
                for dm,g in near[:lvl['cap']]:
                    sid=g.get('idStation')
                    if sid is None:continue
                    sid=str(sid)
                    if sid not in cache:
                        cs,stop,pfails=connectors(d,sid,os_type,app_version);cache[sid]=(cs,stop,pfails);request_counts['stationConnectorsStations']+=1
                    cs,stop,pfails=cache[sid]
                    if stop:stopped=stop;break
                    if pfails:failures.append({'evseId':eid,'kind':'connectors','idStation':sid,'pages':pfails})
                    for c in cs:
                        try:cu=int(c.get('uidConnector'))
                        except Exception:continue
                        if cu!=uid:continue
                        snap=tariff_snapshot(c)
                        found={'evseId':eid,'uidConnector':uid,'punStationId':pe.get('stationId'),'coordinates':[lat,lon],'punSourceStatus':pe.get('sourceStatus'),'punOperationalState':pe.get('operationalState'),'punPowerKw':pe.get('maxPowerKw'),'nextChargeStationId':sid,'nextChargeDistanceFromPunM':round(dm,2),'nextChargeConnectorStatus':c.get('status'),'nextChargePowerMaxKw':c.get('powerMax'),'current':c.get('current'),'standard':c.get('standard'),'tariffSnapshot':{k:v for k,v in snap.items() if k!='consumerTariffSnapshotUsable'},'commercialLayer':'emsp','emsp':'NextCharge','billedBy':'Go Electric Stations S.r.l.s.','identityRule':'ITGESE + uidConnector','exactIdentityMatch':True,'consumerTariffSnapshotUsable':snap['consumerTariffSnapshotUsable'],'rankableAsCpoDirectTariff':False,'rankableAsNextChargeEmspTariff':snap['consumerTariffSnapshotUsable'],'commercialSemantics':'NextCharge consumer/eMSP tariff shown for the connector before charge; not assumed to equal the underlying CPO direct tariff','recoveryLevel':lvl['name']}
                        break
                    if found or stopped:break
                if found or stopped:break
            if stopped:break
            if found:recovered.append(found)
            else:unresolved.append({'evseId':eid,'uidConnector':uid,'coordinates':[lat,lon],'punPowerKw':pe.get('maxPowerKw'),'punSourceStatus':pe.get('sourceStatus'),'attempts':attempts})
            if i%10==0:print(f'progress {i}/{len(targets)} recovered={len(recovered)} unresolved={len(unresolved)}')
    finally:d.quit()
    out={'generatedAt':now(),'security':{'accountCredentialsUsed':False,'sessionTokenSent':False,'captchaBypassed':False,'paymentWalletChargeEndpointsCalled':False},'diagnostics':{'browserErrors':browser_errors,'stoppedReason':stopped},'counts':{'operationalMissingTargets':len(targets),'recoveredExactEvse':len(recovered),'recoveredUsableTariffEvse':sum(1 for x in recovered if x.get('consumerTariffSnapshotUsable')),'unresolvedEvse':len(unresolved),'uniqueNextChargeStationsQueried':len(cache),'failures':len(failures),'requestCounts':dict(request_counts)},'recovered':recovered,'unresolved':unresolved,'failureSample':failures[:100]}
    p=Path('data/reports/ges_nextcharge_operational_recovery.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out['counts'],ensure_ascii=False,indent=2));print(json.dumps(out['diagnostics'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
