#!/usr/bin/env python3
"""Validate current public A2A E-moving map/detail read endpoints.

Read-only. No login, recharge, payment or account endpoint. The public A2A host
currently has a TLS chain the GitHub runner cannot validate, so certificate
validation is disabled only for this host and the limitation is recorded.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests,urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT='https://e-movinghub.a2a.it/acEicp/'
PAGE=ROOT+'publicMapCMS.action'
MAP=ROOT+'jsonGetMapDashboard.action'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/138 Safari/537.36'

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def is_detail(j):
    if isinstance(j,dict):
        if any(k in j for k in ('evseData','costobase','statusMeters')): return True
        for k in ('data','result','chargingUnit','cu'):
            if isinstance(j.get(k),dict) and is_detail(j[k]): return True
    return False
def request(s,method,url,*,data=None,params=None):
    t=time.time(); o={'method':method,'url':url,'data':data or {},'params':params or {}}
    try:
        r=s.request(method,url,data=data,params=params,timeout=40,verify=False,allow_redirects=True,headers={'Accept':'application/json,text/javascript,*/*;q=0.1','X-Requested-With':'XMLHttpRequest'})
        o.update({'httpStatus':r.status_code,'elapsedMs':round((time.time()-t)*1000),'bytes':len(r.content),'contentType':r.headers.get('content-type'),'finalUrl':r.url})
        try:
            j=r.json();o['json']=True;o['_json']=j
            o['shape']={'type':type(j).__name__,'length':len(j) if isinstance(j,list) else None,'keys':sorted(j.keys())[:50] if isinstance(j,dict) else None}
        except Exception:
            o['json']=False;o['textPrefix']=r.text[:300]
    except Exception as e:o['error']=type(e).__name__;o['message']=str(e)[:250]
    return o

def public_owned(row):
    if not isinstance(row,dict): return False
    ap=row.get('assetProvider')
    if isinstance(ap,dict) and ap.get('external') is False: return True
    return False

def slim_attempt(o):
    x={k:v for k,v in o.items() if k!='_json'}
    j=o.get('_json')
    if isinstance(j,dict):x['sample']={k:j[k] for k in list(j)[:12]}
    elif isinstance(j,list):x['sample']=j[:1]
    return x

def main():
    s=requests.Session();s.headers.update({'User-Agent':UA,'Accept-Language':'it-IT,it;q=0.9,en;q=0.5'})
    out={'generatedAt':now(),'sourcePage':PAGE,'security':{'accountCredentialsUsed':False,'authorizationMaterialPersisted':False,'cookiesPersisted':False,'rechargeOrAuthEndpointsCalled':False,'tlsCertificateVerificationDisabledForPublicA2aHost':True},'page':{},'assetContexts':[],'map':{},'detailAttempts':[],'detected':{}}
    html=''
    try:
        r=s.get(PAGE,timeout=40,verify=False);html=r.text;out['page']={'httpStatus':r.status_code,'bytes':len(r.content),'contentType':r.headers.get('content-type'),'finalUrl':r.url}
    except Exception as e:out['page']={'error':type(e).__name__,'message':str(e)[:250]}
    assets=[PAGE]
    if html:
        for src in re.findall(r'<script[^>]+src=["\']([^"\']+)',html,re.I):
            u=urljoin(PAGE,src)
            if urlparse(u).netloc==urlparse(PAGE).netloc and u not in assets:assets.append(u)
    for u in assets[:50]:
        try:text=html if u==PAGE else s.get(u,timeout=35,verify=False).text
        except Exception:continue
        for needle in ('jsonGetMapDashboard','jsonGetCuFromAlias','aliasCu'):
            pos=0;hits=0
            while hits<8:
                i=text.find(needle,pos)
                if i<0:break
                out['assetContexts'].append({'asset':u,'needle':needle,'context':text[max(0,i-220):i+360].replace('\n',' ')})
                pos=i+len(needle);hits+=1
    ma=request(s,'POST',MAP);mj=ma.get('_json')
    rows=mj if isinstance(mj,list) else []
    owned=[x for x in rows if public_owned(x)]
    out['map']={'method':'POST','url':MAP,'httpStatus':ma.get('httpStatus'),'json':ma.get('json',False),'records':len(rows),'publicOwnedRecords':len(owned)}
    if len(rows)>100:out['detected']['map']={'method':'POST','url':MAP,'records':len(rows),'publicOwnedRecords':len(owned)}
    selected=None
    for x in owned:
        if x.get('alias') is not None:selected=x;break
    if selected is None:
        for x in rows:
            if isinstance(x,dict) and x.get('alias') is not None:selected=x;break
    alias=str(selected.get('alias')) if selected else None
    out['map']['selectedAlias']=alias
    if selected:out['map']['selectedMapRecord']={k:selected.get(k) for k in ('id','alias','name','type','statusCu','city','address','lat','long','assetProvider')}
    if alias:
        urls=[ROOT+'jsonGetCuFromAlias.action',ROOT+'publicMapCMS!jsonGetCuFromAlias.action',ROOT+'publicMapCMS.action']
        fields=['aliasCu','alias','aliasCU','idCu']
        stop=False
        for u in urls:
            for field in fields:
                for method in ('POST','GET'):
                    data={field:alias} if method=='POST' else None
                    params={field:alias} if method=='GET' else None
                    if u.endswith('publicMapCMS.action'):
                        params={**(params or {}),'method':'jsonGetCuFromAlias'}
                    a=request(s,method,u,data=data,params=params);j=a.get('_json')
                    out['detailAttempts'].append(slim_attempt(a))
                    if a.get('json') and is_detail(j):
                        out['detected']['detail']={'method':method,'url':a.get('finalUrl') or u,'requestField':field,'sampleAlias':alias,'topLevelKeys':sorted(j.keys())[:40] if isinstance(j,dict) else []};stop=True;break
                if stop:break
            if stop:break
    out['security']['transientPublicSessionCookieUsed']=bool(s.cookies)
    p=Path('data/reports/a2a_italy_backend_probe.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'page':out['page'],'map':out['map'],'detected':out['detected'],'assetContexts':out['assetContexts'][:8],'detailAttemptsSummary':[{k:a.get(k) for k in ('method','url','data','params','httpStatus','json','shape','textPrefix')} for a in out['detailAttempts']]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
