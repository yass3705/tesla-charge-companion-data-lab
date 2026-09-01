#!/usr/bin/env python3
"""Recover public-client myAtlante config and prove Italy station tariffs read-only.
Transient decompilation only; recovered client config is masked and never persisted.
"""
from __future__ import annotations
import json,re,sys,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1';TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39';OUT=Path('data/reports/atlante_hermes_config_probe.json')
SEC={'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}
def api(url,key,ver='2.1.0'):
 q=urllib.request.Request(url,headers={'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT','X-App-Version':ver,'X-App-Platform':'android','User-Agent':f'myAtlante/{ver} (Android)'})
 with urllib.request.urlopen(q,timeout=12) as r:return r.status,json.loads(r.read().decode())
def base_map_url(extra=None):
 q={'latLongBottomLeft':'35,5','latLongTopRight':'48,19'}
 if extra:q.update(extra)
 return f'{BASE}/tenants/{TENANT}/map-locations?'+urllib.parse.urlencode(q)
def test(c):
 try:
  st,p=api(base_map_url(),c);return (c,p) if st==200 and isinstance(p,dict) and isinstance(p.get('locations'),list) else None
 except:return None
def literal_candidates(text):
 anchors=[m.start() for m in re.finditer(r'Ocp-Apim-Subscription-Key|azure-api\.net|app-backend/v1|subscriptionKey|apiKey',text,re.I)];regions=[text[max(0,p-20000):min(len(text),p+20000)] for p in anchors];targeted=[]
 for reg in regions:
  for q,v in re.findall(r'''(["'])(.{20,120}?)\1''',reg,re.S):
   v=v.replace('\\"','"').replace("\\'", "'")
   if '\n' not in v and len(set(v))>=8 and re.fullmatch(r'[A-Za-z0-9_+/=-]{24,96}',v):targeted.append(v)
 fallback=[]
 for q,v in re.findall(r'''(["'])(.{28,64}?)\1''',text,re.S):
  if '\n' not in v and len(set(v))>=10 and re.fullmatch(r'[A-Za-z0-9_+/=-]{28,64}',v):fallback.append(v)
 return list(dict.fromkeys(targeted)),[x for x in dict.fromkeys(fallback) if x not in targeted],len(anchors)
def probe(vals,limit):
 vals=vals[:limit]
 for v in vals:print(f'::add-mask::{v}')
 with ThreadPoolExecutor(max_workers=32) as ex:
  fs=[ex.submit(test,v) for v in vals]
  for f in as_completed(fs):
   r=f.result()
   if r:return r,len(vals)
 return None,len(vals)
def listify(x):
 if isinstance(x,list):return x
 if isinstance(x,dict):
  for k in ('cpos','items','data','results'):
   if isinstance(x.get(k),list):return x[k]
 return []
def candidate_ids(c):
 vals=[]
 for k in ('id','cpoId','identifier','code','partyId','externalId','name'):
  v=c.get(k)
  if isinstance(v,(str,int)) and str(v).strip():vals.append(str(v).strip())
 return list(dict.fromkeys(vals))
def map_with_cpo(key,cpo_id):
 variants=[
  {'includeCpos':cpo_id},
  {'includeCpos':cpo_id,'evseTypes':'AC,DC,HPC','locationStatus':'ALL','connectorTypes':'CCS,CHADEMO,TYPE2'},
 ]
 for extra in variants:
  try:
   _,p=api(base_map_url(extra),key)
   locs=p.get('locations') if isinstance(p,dict) else None
   if isinstance(locs,list) and locs:return p,extra
  except:pass
 return None,None
def hydrate(key,l):
 lid=str(l.get('id') or l.get('locationId') or '')
 if not lid:return None
 try:_,d=api(f'{BASE}/tenants/{TENANT}/locations/{urllib.parse.quote(lid,safe="")}',key);return l,d
 except:return None
def main():
 text=Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore');targeted,fallback,anchors=literal_candidates(text);r,n=probe(targeted,1000);n2=0
 if not r:r,n2=probe(fallback,2500)
 rep={'source':'temporary Hermes/React Native decompilation of public myAtlante Android package','anchors':anchors,'targetedCandidateCount':len(targeted),'targetedProbed':n,'fallbackCandidateCount':len(fallback),'fallbackProbed':n2,'clientCredentialRecovered':bool(r),'clientCredentialPersisted':False,'security':SEC}
 if not r:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,indent=2)+'\n');raise SystemExit('No client config validated')
 key,_=r
 try:_,cp=api(f'{BASE}/tenants/{TENANT}/cpos',key)
 except Exception as e:rep['cpoEndpointErrorType']=type(e).__name__;cp=[]
 cpos=listify(cp);rep['cpoCount']=len(cpos)
 safe_cpos=[];atl=[]
 for c in cpos:
  if not isinstance(c,dict):continue
  safe={k:c.get(k) for k in ('id','cpoId','identifier','code','partyId','name','displayName','countryCode') if c.get(k) is not None}
  safe_cpos.append(safe)
  if 'atlante' in json.dumps(safe,ensure_ascii=False).lower():atl.append(c)
 rep['atlanteCpoCandidates']=[{k:c.get(k) for k in ('id','cpoId','identifier','code','partyId','name','displayName','countryCode') if c.get(k) is not None} for c in atl]
 rep['cpoSample']=safe_cpos[:20]
 chosen=None;chosen_id=None;chosen_extra=None
 ids=[]
 for c in atl:
  ids+=candidate_ids(c)
 # Historical identifiers are safe public CPO selectors; try only if current /cpos labels do not expose one directly.
 ids+=['ITATL','ATL','ATE']
 for cid in dict.fromkeys(ids):
  p,extra=map_with_cpo(key,cid)
  if p:chosen=p;chosen_id=cid;chosen_extra=extra;break
 if chosen is None:
  rep['cpoSelectorAttempts']=len(list(dict.fromkeys(ids)));OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');raise SystemExit('CPO list fetched but no Atlante selector produced map locations')
 locs=chosen.get('locations') or [];rep['selectedCpoIdentifier']=chosen_id;rep['selectedMapParams']=chosen_extra;rep['mapLocationCount']=len(locs)
 details=[]
 with ThreadPoolExecutor(max_workers=24) as ex:
  fs=[ex.submit(hydrate,key,l) for l in locs[:1000]]
  for f in as_completed(fs):
   x=f.result()
   if x:details.append(x)
 italy=[]
 for l,d in details:
  cc=str(d.get('countryCode') or l.get('countryCode') or '').upper();op=str(d.get('operatorName') or l.get('operatorName') or d.get('cpoName') or l.get('cpoName') or '')
  if cc in ('','IT') and ('atlante' in op.lower() or chosen_id.upper() in ('ITATL','ATL','ATE')):italy.append((l,d))
 rep['hydratedCount']=len(details);rep['italyAtlanteLocationCount']=len(italy);samples=[]
 for l,d in italy[:120]:
  lid=str(d.get('id') or l.get('id') or l.get('locationId') or '')
  try:_,tp=api(f'{BASE}/tenants/{TENANT}/locations/{urllib.parse.quote(lid,safe="")}/tariffs',key)
  except:continue
  tariffs=tp if isinstance(tp,list) else (tp.get('tariffs',[]) if isinstance(tp,dict) else []);rows=[]
  for t in tariffs:
   if not isinstance(t,dict):continue
   ids2=t.get('identifiers') or {}
   for pc in t.get('priceComponents') or []:
    if str(pc.get('priceDimension','')).upper()=='ENERGY' and str(pc.get('currency','')).upper()=='EUR':
     v=(pc.get('price') or {}).get('incl_vat')
     if isinstance(v,(int,float)) and v>0:rows.append({'evseId':ids2.get('evseId'),'connectorId':ids2.get('connectorId'),'eurPerKwh':v})
  if rows:samples.append({'locationId':lid,'name':d.get('displayName') or d.get('locationName') or l.get('displayName'),'city':d.get('city') or l.get('city'),'operatorName':d.get('operatorName') or d.get('cpoName') or l.get('operatorName') or l.get('cpoName'),'tariffs':rows[:20]})
  if len(samples)>=8:break
 rep['stationTariffSamples']=samples;OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
 if not samples:raise SystemExit('Atlante map works but station tariff sample absent')
 print(json.dumps({'selectedCpoIdentifier':chosen_id,'italyAtlanteLocations':len(italy),'stationTariffSamples':samples},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
