#!/usr/bin/env python3
"""Resolve current myAtlante includeCpos encoding and fetch direct station tariffs.
Public Android client constants only; no login/account/charging/payment/mutation calls.
"""
from __future__ import annotations
import json,re,sys,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1';TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39';OUT=Path('data/reports/atlante_current_cpo_selector_probe.json')
SEC={'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}
def api(url,key):
 q=urllib.request.Request(url,headers={'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT','X-App-Version':'2.1.0','X-App-Platform':'android','User-Agent':'myAtlante/2.1.0 (Android)'})
 with urllib.request.urlopen(q,timeout=12) as r:return r.status,json.loads(r.read().decode())
def candidates(text):
 anchors=[m.start() for m in re.finditer(r'Ocp-Apim-Subscription-Key|azure-api\.net|app-backend/v1|subscriptionKey|apiKey',text,re.I)];vals=[]
 for p in anchors:
  reg=text[max(0,p-20000):min(len(text),p+20000)]
  for q,v in re.findall(r'''(["'])(.{20,120}?)\1''',reg,re.S):
   v=v.replace('\\"','"').replace("\\'", "'")
   if '\n' not in v and len(set(v))>=8 and re.fullmatch(r'[A-Za-z0-9_+/=-]{24,96}',v):vals.append(v)
 return list(dict.fromkeys(vals)),len(anchors)
def keytest(c):
 try:
  st,p=api(f'{BASE}/tenants/{TENANT}/cpos',c);return (c,p) if st==200 and isinstance(p,(list,dict)) else None
 except:return None
def maplocs(p):
 if isinstance(p,list):return p
 if isinstance(p,dict):
  for k in ('locations','items','data','results'):
   if isinstance(p.get(k),list):return p[k]
 return []
def mapcall(key,selector):
 variants=[
  {'latLongBottomLeft':'35,5','latLongTopRight':'48,19','includeCpos':selector},
  {'latLongBottomLeft':'35,5','latLongTopRight':'48,19','includeCpos':selector,'locationStatus':'ALL'},
  {'latLongBottomLeft':'35,5','latLongTopRight':'48,19','includeCpos':selector,'evseTypes':'AC,DC,HPC','connectorTypes':'CCS,CHADEMO,TYPE2'},
 ]
 for q in variants:
  try:
   _,p=api(f'{BASE}/tenants/{TENANT}/map-locations?'+urllib.parse.urlencode(q),key);locs=maplocs(p)
   if locs:return selector,q,locs
  except:pass
 return None
def detail(key,l):
 lid=str(l.get('id') or l.get('locationId') or l.get('location_id') or '')
 if not lid:return None
 try:_,d=api(f'{BASE}/tenants/{TENANT}/locations/{urllib.parse.quote(lid,safe="")}',key);return l,d
 except:return None
def prices(tp):
 ts=tp if isinstance(tp,list) else next((tp[k] for k in ('tariffs','items','data','results') if isinstance(tp,dict) and isinstance(tp.get(k),list)),[])
 rows=[]
 for t in ts:
  if not isinstance(t,dict):continue
  ids=t.get('identifiers') or {}
  for pc in t.get('priceComponents') or []:
   if not isinstance(pc,dict):continue
   if str(pc.get('priceDimension') or '').upper()!='ENERGY' or str(pc.get('currency') or '').upper()!='EUR':continue
   pr=pc.get('price') or {};v=pr.get('incl_vat') if isinstance(pr,dict) else None
   if isinstance(v,(int,float)) and v>0:rows.append({'evseId':ids.get('evseId'),'connectorId':ids.get('connectorId'),'eurPerKwh':v})
 return rows
def main():
 text=Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore');cs,anchors=candidates(text)
 for c in cs:print(f'::add-mask::{c}')
 found=None
 with ThreadPoolExecutor(max_workers=16) as ex:
  fs=[ex.submit(keytest,c) for c in cs]
  for f in as_completed(fs):
   r=f.result()
   if r:found=r;break
 rep={'source':'current public myAtlante Android guest API','clientCredentialRecovered':bool(found),'clientCredentialPersisted':False,'anchors':anchors,'security':SEC}
 if not found:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,indent=2)+'\n');raise SystemExit('client credential unresolved')
 key,_=found
 pairs=[('IT','ATE'),('IT','ATL'),('IT','WRM')];sels=[]
 for cc,party in pairs:
  sels += [f'{cc}*{party}',f'{cc}{party}',f'{cc}-{party}',f'{cc}_{party}',f'{cc}/{party}',f'{cc}:{party}',party]
 # Multi-CPO encodings used by typical query builders.
 base=[f'{cc}*{p}' for cc,p in pairs]
 sels += [','.join(base),';'.join(base),'|'.join(base)]
 sels=list(dict.fromkeys(sels));rep['selectorCandidatesTested']=sels
 chosen=None
 with ThreadPoolExecutor(max_workers=12) as ex:
  fs=[ex.submit(mapcall,key,s) for s in sels]
  for f in as_completed(fs):
   r=f.result()
   if r:chosen=r;break
 if not chosen:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');raise SystemExit('no OCPI selector format returned map locations')
 selector,q,locs=chosen;rep['selectedCpoSelector']=selector;rep['selectedMapQuery']=q;rep['mapLocationCount']=len(locs)
 hydrated=[]
 with ThreadPoolExecutor(max_workers=24) as ex:
  fs=[ex.submit(detail,key,l) for l in locs[:700]]
  for f in as_completed(fs):
   r=f.result()
   if r:hydrated.append(r)
 rep['hydratedLocationCount']=len(hydrated);samples=[]
 for l,d in hydrated:
  lid=str(d.get('id') or l.get('id') or l.get('locationId') or '')
  if not lid:continue
  try:_,tp=api(f'{BASE}/tenants/{TENANT}/locations/{urllib.parse.quote(lid,safe="")}/tariffs',key)
  except:continue
  rows=prices(tp)
  if rows:samples.append({'locationId':lid,'name':d.get('displayName') or d.get('locationName') or l.get('displayName') or l.get('name'),'city':d.get('city') or l.get('city'),'countryCode':d.get('countryCode') or l.get('countryCode'),'partyId':d.get('partyId') or l.get('partyId'),'operatorName':d.get('operatorName') or d.get('cpoName') or l.get('operatorName') or l.get('cpoName'),'tariffs':rows[:20]})
  if len(samples)>=10:break
 rep['stationTariffSamples']=samples;OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
 if not samples:raise SystemExit('map locations resolved but no station price returned')
 print(json.dumps({'selector':selector,'locations':len(locs),'samples':samples},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
