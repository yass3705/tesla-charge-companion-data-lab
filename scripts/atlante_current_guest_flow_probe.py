#!/usr/bin/env python3
"""Reproduce the current public myAtlante guest flow and return station tariff samples.

Input is a transient Hermes decompilation of the public Android client. The client APIM
credential is masked and never persisted. Only GET guest endpoints are called.
"""
from __future__ import annotations
import json,re,sys,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1'
TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39'
OUT=Path('data/reports/atlante_current_guest_flow_probe.json')
SEC={'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}

def api(url,key):
    req=urllib.request.Request(url,headers={'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT','X-App-Version':'2.1.0','X-App-Platform':'android','User-Agent':'myAtlante/2.1.0 (Android)'})
    with urllib.request.urlopen(req,timeout=12) as r:
        return r.status,json.loads(r.read().decode())

def literals(text):
    anchors=[m.start() for m in re.finditer(r'Ocp-Apim-Subscription-Key|azure-api\.net|app-backend/v1|subscriptionKey|apiKey',text,re.I)]
    vals=[]
    for p in anchors:
        reg=text[max(0,p-20000):min(len(text),p+20000)]
        for q,v in re.findall(r'''(["'])(.{20,120}?)\1''',reg,re.S):
            v=v.replace('\\"','"').replace("\\'", "'")
            if '\n' not in v and len(set(v))>=8 and re.fullmatch(r'[A-Za-z0-9_+/=-]{24,96}',v): vals.append(v)
    return list(dict.fromkeys(vals)),len(anchors)

def validate_key(c):
    try:
        st,p=api(f'{BASE}/tenants/{TENANT}/cpos',c)
        return (c,p) if st==200 and isinstance(p,(dict,list)) else None
    except Exception:return None

def find_lists(x,path=''):
    out=[]
    if isinstance(x,list):
        if x and all(isinstance(v,dict) for v in x): out.append((path,x))
        for i,v in enumerate(x[:30]): out.extend(find_lists(v,f'{path}[{i}]'))
    elif isinstance(x,dict):
        for k,v in x.items(): out.extend(find_lists(v,f'{path}.{k}' if path else str(k)))
    return out

def safe_scalars(d):
    out={}
    for k,v in d.items():
        if isinstance(v,(str,int,float,bool)) or v is None:
            s=str(v) if v is not None else ''
            if len(s)<=180: out[k]=v
    return out

def map_url(selector):
    q={'latLongBottomLeft':'35,5','latLongTopRight':'48,19','includeCpos':selector}
    return f'{BASE}/tenants/{TENANT}/map-locations?'+urllib.parse.urlencode(q)

def map_locations(payload):
    if isinstance(payload,dict):
        for k in ('locations','items','data','results'):
            v=payload.get(k)
            if isinstance(v,list): return v
    if isinstance(payload,list): return payload
    return []

def map_try(key,selector):
    try:
        _,p=api(map_url(selector),key); locs=map_locations(p)
        return (selector,p,locs) if locs else None
    except Exception:return None

def detail(key,l):
    lid=str(l.get('id') or l.get('locationId') or l.get('location_id') or '')
    if not lid:return None
    try:
        _,d=api(f'{BASE}/tenants/{TENANT}/locations/{urllib.parse.quote(lid,safe="")}',key);return l,d
    except Exception:return None

def tariff_rows(tp):
    if isinstance(tp,list): ts=tp
    elif isinstance(tp,dict):
        ts=[]
        for k in ('tariffs','items','data','results'):
            if isinstance(tp.get(k),list):ts=tp[k];break
    else:ts=[]
    rows=[]
    for t in ts:
        if not isinstance(t,dict):continue
        ids=t.get('identifiers') or {}
        for pc in t.get('priceComponents') or []:
            if not isinstance(pc,dict):continue
            if str(pc.get('priceDimension') or '').upper()!='ENERGY' or str(pc.get('currency') or '').upper()!='EUR':continue
            price=pc.get('price') or {}; v=price.get('incl_vat') if isinstance(price,dict) else None
            if isinstance(v,(int,float)) and v>0:rows.append({'evseId':ids.get('evseId'),'connectorId':ids.get('connectorId'),'eurPerKwh':v})
    return rows

def main():
    text=Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore');cands,anchors=literals(text)
    for c in cands: print(f'::add-mask::{c}')
    found=None
    with ThreadPoolExecutor(max_workers=16) as ex:
        fs=[ex.submit(validate_key,c) for c in cands]
        for f in as_completed(fs):
            r=f.result()
            if r:found=r;break
    rep={'source':'current public myAtlante Android guest flow','anchors':anchors,'credentialCandidateCount':len(cands),'clientCredentialRecovered':bool(found),'clientCredentialPersisted':False,'security':SEC}
    if not found:
        OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,indent=2)+'\n');raise SystemExit('No public client credential validated on /cpos')
    key,cpo_payload=found
    lists=find_lists(cpo_payload);rep['cpoListPaths']=[{'path':p,'count':len(v)} for p,v in lists[:30]]
    cpo_rows=[]
    for _,lst in lists:
        cpo_rows.extend(lst)
    # de-duplicate visible objects
    uniq=[];seen=set()
    for c in cpo_rows:
        safe=safe_scalars(c);sig=json.dumps(safe,sort_keys=True,ensure_ascii=False)
        if sig not in seen:seen.add(sig);uniq.append((c,safe))
    rep['cpoVisibleSample']=[s for _,s in uniq[:30]]
    atl=[(c,s) for c,s in uniq if 'atlante' in json.dumps(s,ensure_ascii=False).lower()]
    rep['atlanteCpoCandidates']=[s for _,s in atl]
    selectors=[]
    for c,s in atl:
        # all public scalar identifiers from the Atlante CPO object; values that are plainly prose/URLs are skipped
        for k,v in s.items():
            if not isinstance(v,(str,int)):continue
            sv=str(v).strip()
            if not sv or len(sv)>100 or sv.startswith(('http://','https://')):continue
            if any(t in k.lower() for t in ('id','code','party','identifier','name','key','value')):selectors.append(sv)
    selectors += ['ITATL','ATL','ATE']
    selectors=list(dict.fromkeys(selectors))
    for s in selectors: print('Trying public CPO selector field length',len(s))
    chosen=None
    with ThreadPoolExecutor(max_workers=min(12,max(1,len(selectors)))) as ex:
        fs=[ex.submit(map_try,key,s) for s in selectors]
        for f in as_completed(fs):
            r=f.result()
            if r:chosen=r;break
    rep['selectorAttemptCount']=len(selectors)
    if not chosen:
        OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');raise SystemExit('/cpos works but no Atlante includeCpos selector returned locations')
    selector,payload,locs=chosen;rep['selectedCpoSelector']=selector;rep['mapLocationCount']=len(locs)
    hydrated=[]
    with ThreadPoolExecutor(max_workers=20) as ex:
        fs=[ex.submit(detail,key,l) for l in locs[:500]]
        for f in as_completed(fs):
            r=f.result()
            if r:hydrated.append(r)
    rep['hydratedLocationCount']=len(hydrated);samples=[]
    for l,d in hydrated:
        lid=str(d.get('id') or l.get('id') or l.get('locationId') or '')
        if not lid:continue
        try:_,tp=api(f'{BASE}/tenants/{TENANT}/locations/{urllib.parse.quote(lid,safe="")}/tariffs',key)
        except Exception:continue
        rows=tariff_rows(tp)
        if rows:
            samples.append({'locationId':lid,'name':d.get('displayName') or d.get('locationName') or l.get('displayName') or l.get('name'),'city':d.get('city') or l.get('city'),'operatorName':d.get('operatorName') or d.get('cpoName') or l.get('operatorName') or l.get('cpoName'),'tariffs':rows[:20]})
        if len(samples)>=10:break
    rep['stationTariffSamples']=samples
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
    if not samples:raise SystemExit('Atlante locations found but tariff endpoint yielded no positive EUR energy component')
    print(json.dumps({'selectedCpoSelector':selector,'locations':len(locs),'stationTariffSamples':samples},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
