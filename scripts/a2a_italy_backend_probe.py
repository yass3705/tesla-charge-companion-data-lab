#!/usr/bin/env python3
"""Validate current public A2A E-moving map/detail read endpoints.
Read-only; no login/recharge/payment/account endpoint. TLS verification is
explicitly disabled only for the known public A2A host because its current
certificate chain is not accepted by the GitHub runner; all tariff data remains
subject to PUN and official-commercial cross-checks.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests,urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ROOT='https://e-movinghub.a2a.it/acEicp/'
PAGE=ROOT+'publicMapCMS.action'; MAP=ROOT+'jsonGetMapDashboard.action'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/138 Safari/537.36'
SEARCH_TERMS=('openDetails','jsonGetMapDashboard','jsonGetCuFromAlias','costobase','penaltyCost','evseData','statusMeters','aliasCu','jsonGetCu','getCu')
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def is_detail(j):
    if isinstance(j,dict):
        if any(k in j for k in ('evseData','costobase','statusMeters','penaltyCost')):return True
        return any(is_detail(v) for v in j.values() if isinstance(v,(dict,list)))
    if isinstance(j,list):return any(is_detail(v) for v in j[:10])
    return False
def req(s,method,url,*,form=None,params=None,json_body=None):
    t=time.time();o={'method':method,'url':url,'form':form or {},'params':params or {},'jsonBody':json_body}
    try:
        r=s.request(method,url,data=form,params=params,json=json_body,timeout=40,verify=False,allow_redirects=True,headers={'Accept':'application/json,text/javascript,*/*;q=0.1','X-Requested-With':'XMLHttpRequest'})
        o.update({'httpStatus':r.status_code,'elapsedMs':round((time.time()-t)*1000),'bytes':len(r.content),'contentType':r.headers.get('content-type'),'finalUrl':r.url})
        try:
            j=r.json();o['json']=True;o['_json']=j;o['shape']={'type':type(j).__name__,'length':len(j) if isinstance(j,list) else None,'keys':sorted(j.keys())[:50] if isinstance(j,dict) else None}
        except Exception:o['json']=False;o['textPrefix']=r.text[:300]
    except Exception as e:o['error']=type(e).__name__;o['message']=str(e)[:250]
    return o
def owned(r):return isinstance(r,dict) and isinstance(r.get('assetProvider'),dict) and r['assetProvider'].get('external') is False
def slim(o):
    x={k:v for k,v in o.items() if k!='_json'};j=o.get('_json')
    if isinstance(j,dict):x['sample']={k:j[k] for k in list(j)[:12]}
    elif isinstance(j,list):x['sample']=j[:1]
    return x
def main():
    s=requests.Session();s.headers.update({'User-Agent':UA,'Accept-Language':'it-IT,it;q=0.9,en;q=0.5'})
    out={'generatedAt':now(),'sourcePage':PAGE,'security':{'accountCredentialsUsed':False,'authorizationMaterialPersisted':False,'cookiesPersisted':False,'rechargeOrAuthEndpointsCalled':False,'tlsCertificateVerificationDisabledForPublicA2aHost':True},'page':{},'assetContexts':[],'assetsScanned':[],'map':{},'detailAttempts':[],'detected':{}}
    try:r=s.get(PAGE,timeout=40,verify=False);html=r.text;out['page']={'httpStatus':r.status_code,'bytes':len(r.content),'contentType':r.headers.get('content-type'),'finalUrl':r.url}
    except Exception as e:html='';out['page']={'error':type(e).__name__,'message':str(e)[:250]}
    assets=[PAGE]
    for src in re.findall(r'<script[^>]+src=["\']([^"\']+)',html,re.I):
        u=urljoin(PAGE,src)
        if urlparse(u).netloc==urlparse(PAGE).netloc and u not in assets:assets.append(u)
    for u in assets[:60]:
        try:text=html if u==PAGE else s.get(u,timeout=35,verify=False).text
        except Exception:continue
        hits=[]
        for term in SEARCH_TERMS:
            pos=0
            for _ in range(8):
                i=text.find(term,pos)
                if i<0:break
                hits.append(term);out['assetContexts'].append({'asset':u,'needle':term,'context':text[max(0,i-320):i+520].replace('\n',' ')})
                pos=i+len(term)
        if hits:out['assetsScanned'].append({'asset':u,'hits':sorted(set(hits))})
    ma=req(s,'POST',MAP,json_body={});mj=ma.get('_json');rows=mj if isinstance(mj,list) else [];own=[x for x in rows if owned(x)]
    out['map']={'method':'POST','url':MAP,'records':len(rows),'publicOwnedRecords':len(own)}
    if len(rows)>100:out['detected']['map']={'method':'POST','url':MAP,'records':len(rows),'publicOwnedRecords':len(own)}
    selected=next((x for x in own if x.get('alias') is not None),None) or next((x for x in rows if isinstance(x,dict) and x.get('alias') is not None),None)
    alias=str(selected.get('alias')) if selected else None;out['map']['selectedAlias']=alias
    if selected:out['map']['selectedMapRecord']={k:selected.get(k) for k in ('id','alias','name','type','statusCu','city','address','lat','long','assetProvider')}
    if alias:
        # Modern frontend uses application/json for map calls. Try the legacy-named detail route with JSON first,
        # then a few narrow variants only; exact frontend contexts above remain the primary discovery evidence.
        models=[{'aliasCu':alias},{'userNation':'IT','aliasCu':alias}]
        for u in (ROOT+'jsonGetCuFromAlias.action',ROOT+'jsonGetCuFromAlias'):
            for model in models:
                a=req(s,'POST',u,json_body=model);j=a.get('_json');out['detailAttempts'].append(slim(a))
                if a.get('json') and is_detail(j):out['detected']['detail']={'method':'POST','url':a.get('finalUrl') or u,'requestJson':model,'sampleAlias':alias};break
            if 'detail' in out['detected']:break
    out['security']['transientPublicSessionCookieUsed']=bool(s.cookies)
    p=Path('data/reports/a2a_italy_backend_probe.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'page':out['page'],'map':out['map'],'detected':out['detected'],'assetsScanned':out['assetsScanned'],'assetContexts':out['assetContexts'][:40],'detailAttempts':out['detailAttempts']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
