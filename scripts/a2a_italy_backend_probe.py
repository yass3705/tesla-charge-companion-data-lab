#!/usr/bin/env python3
"""Discover and validate the public A2A E-moving map/detail read endpoints.

Read-only probe. It uses only the public map page and station alias 519, already
visible on the public map. No login, recharge, payment or account endpoint is
called. A2A's public host currently presents a TLS chain that the GitHub runner
cannot validate, so this research probe disables certificate validation only
for this known public host and records that limitation explicitly. Data from
this host is never treated as authoritative without PUN/official cross-checks.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE='https://e-movinghub.a2a.it/acEicp/publicMapCMS.action'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/138 Safari/537.36'
VERIFY_TLS=False

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def shape(x):
    if isinstance(x,list): return {'type':'list','length':len(x),'sampleKeys':sorted(list(x[0].keys()))[:30] if x and isinstance(x[0],dict) else []}
    if isinstance(x,dict): return {'type':'dict','keys':sorted(list(x.keys()))[:50]}
    return {'type':type(x).__name__}
def stationish_count(x):
    if isinstance(x,list):
        return sum(1 for v in x if isinstance(v,dict) and any(k in v for k in ('alias','lat','long','statusCu','assetProvider')))
    if isinstance(x,dict):
        for k in ('data','result','stations','chargingUnits','list'):
            v=x.get(k)
            if isinstance(v,list): return stationish_count(v)
    return 0

def request_attempt(s,method,url,data=None,params=None):
    t=time.time(); out={'method':method,'url':url,'dataKeys':sorted((data or {}).keys()),'paramKeys':sorted((params or {}).keys())}
    try:
        r=s.request(method,url,data=data,params=params,timeout=35,headers={'Accept':'application/json,text/javascript,*/*;q=0.1','X-Requested-With':'XMLHttpRequest'},allow_redirects=True,verify=VERIFY_TLS)
        out.update({'httpStatus':r.status_code,'elapsedMs':round((time.time()-t)*1000),'contentType':r.headers.get('content-type'),'bytes':len(r.content),'finalUrl':r.url})
        try:
            j=r.json(); out['json']=True; out['shape']=shape(j); out['stationishCount']=stationish_count(j)
            if isinstance(j,list): out['sample']=j[:1]
            elif isinstance(j,dict): out['sample']={k:j[k] for k in list(j)[:6]}
        except Exception:
            out['json']=False; out['textPrefix']=r.text[:240]
    except Exception as e:
        out['error']=type(e).__name__; out['message']=str(e)[:240]
    return out

def main():
    s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'it-IT,it;q=0.9,en;q=0.5'})
    report={'generatedAt':now(),'sourcePage':BASE,'security':{'accountCredentialsUsed':False,'authorizationMaterialPersisted':False,'cookiesPersisted':False,'rechargeOrAuthEndpointsCalled':False,'tlsCertificateVerificationDisabledForPublicA2aHost':True},'page':{},'assetContexts':[],'mapAttempts':[],'detailAttempts':[],'detected':{}}
    html=''
    try:
        r=s.get(BASE,timeout=35,verify=VERIFY_TLS); html=r.text
        report['page']={'httpStatus':r.status_code,'bytes':len(r.content),'contentType':r.headers.get('content-type'),'finalUrl':r.url,'transientCookieNames':sorted(s.cookies.keys())}
    except Exception as e:
        report['page']={'error':type(e).__name__,'message':str(e)[:240]}
    assets=[BASE]
    if html:
        for src in re.findall(r'<script[^>]+src=["\']([^"\']+)',html,re.I):
            u=urljoin(BASE,src)
            if urlparse(u).netloc==urlparse(BASE).netloc and u not in assets: assets.append(u)
    for u in assets[:40]:
        try:
            text=html if u==BASE else s.get(u,timeout=30,verify=VERIFY_TLS).text
        except Exception: continue
        for needle in ('jsonGetMapDashboard','jsonGetCuFromAlias'):
            start=0
            while True:
                i=text.find(needle,start)
                if i<0: break
                report['assetContexts'].append({'asset':u,'needle':needle,'context':text[max(0,i-180):i+260].replace('\n',' ')})
                start=i+len(needle)
                if sum(1 for x in report['assetContexts'] if x['asset']==u and x['needle']==needle)>=5: break
    root=BASE.rsplit('/',1)[0]+'/'
    map_variants=[root+'publicMapCMS!jsonGetMapDashboard.action',root+'publicMapCMS.action',root+'jsonGetMapDashboard.action']
    detail_variants=[root+'publicMapCMS!jsonGetCuFromAlias.action',root+'publicMapCMS.action',root+'jsonGetCuFromAlias.action']
    for u in map_variants:
        for method in ('POST','GET'):
            params={'method':'jsonGetMapDashboard'} if u.endswith('publicMapCMS.action') else None
            a=request_attempt(s,method,u,params=params); report['mapAttempts'].append(a)
            if a.get('json') and (a.get('stationishCount') or 0)>100:
                report['detected']['map']={'method':method,'url':a.get('finalUrl') or u,'requestParams':params or {},'stationishCount':a['stationishCount']}; break
        if 'map' in report['detected']: break
    for u in detail_variants:
        for method in ('POST','GET'):
            params={'method':'jsonGetCuFromAlias'} if u.endswith('publicMapCMS.action') else None
            payload={'aliasCu':'519'}
            a=request_attempt(s,method,u,data=payload if method=='POST' else None,params={**(params or {}),**(payload if method=='GET' else {})}); report['detailAttempts'].append(a)
            sample=a.get('sample'); txt=json.dumps(sample,ensure_ascii=False) if sample is not None else ''
            if a.get('json') and ('evseData' in txt or 'costobase' in txt or 'assetProvider' in txt):
                report['detected']['detail']={'method':method,'url':a.get('finalUrl') or u,'requestField':'aliasCu','sampleAlias':'519'}; break
        if 'detail' in report['detected']: break
    report['security']['transientPublicSessionCookieUsed']=bool(s.cookies)
    report['page'].pop('transientCookieNames',None)
    p=Path('data/reports/a2a_italy_backend_probe.json'); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'page':report['page'],'detected':report['detected'],'assetContexts':len(report['assetContexts'])},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
