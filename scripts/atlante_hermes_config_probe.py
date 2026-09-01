#!/usr/bin/env python3
"""Analyze a decompiled myAtlante JS/Hermes bundle and validate public client APIM config.
The decompiled source is transient. Candidate values are masked and never persisted.
Only the read-only map/detail/tariff endpoints are contacted.
"""
from __future__ import annotations
import json,re,sys,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1';TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39'
MAP=f'{BASE}/tenants/{TENANT}/map-locations?latLongBottomLeft=35%2C5&latLongTopRight=48%2C19&evseTypes=AC%2CDC%2CHPC&locationStatus=ALL&connectorTypes=CCS%2CCHADEMO%2CTYPE2'
OUT=Path('data/reports/atlante_hermes_config_probe.json')
def api(url,key,ver='2.1.0'):
 q=urllib.request.Request(url,headers={'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT','X-App-Version':ver,'X-App-Platform':'android','User-Agent':f'myAtlante/{ver} (Android)'})
 with urllib.request.urlopen(q,timeout=8) as r:return r.status,json.loads(r.read().decode())
def test(c):
 try:
  st,p=api(MAP,c);return (c,p) if st==200 and isinstance(p,dict) and isinstance(p.get('locations'),list) else None
 except:return None
def literal_candidates(text):
 # Keep only string literals from config-relevant code regions first, then opaque literals globally.
 anchors=[m.start() for m in re.finditer(r'Ocp-Apim-Subscription-Key|azure-api\.net|app-backend/v1|subscriptionKey|apiKey',text,re.I)]
 regions=[]
 for p in anchors:regions.append(text[max(0,p-20000):min(len(text),p+20000)])
 targeted=[]
 for reg in regions:
  for q,v in re.findall(r'''(["'])(.{20,120}?)\1''',reg,re.S):
   v=v.replace('\\"','"').replace("\\'", "'")
   if '\n' in v or len(set(v))<8:continue
   if re.fullmatch(r'[A-Za-z0-9_+/=-]{24,96}',v):targeted.append(v)
 # Global exact APIM-like opaque literals as fallback.
 fallback=[]
 for q,v in re.findall(r'''(["'])(.{28,64}?)\1''',text,re.S):
  if '\n' in v or len(set(v))<10:continue
  if re.fullmatch(r'[A-Za-z0-9_+/=-]{28,64}',v):fallback.append(v)
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
def main():
 path=Path(sys.argv[1]);text=path.read_text(encoding='utf-8',errors='ignore')
 targeted,fallback,anchors=literal_candidates(text)
 r,n=probe(targeted,1000);n2=0
 if not r:r,n2=probe(fallback,2500)
 rep={'source':'temporary Hermes/React Native decompilation of public myAtlante Android package','anchors':anchors,'targetedCandidateCount':len(targeted),'targetedProbed':n,'fallbackCandidateCount':len(fallback),'fallbackProbed':n2,'clientCredentialRecovered':bool(r),'clientCredentialPersisted':False,'security':{'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}}
 if not r:
  OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,indent=2)+'\n');raise SystemExit('No APIM client credential validated from decompiled bundle')
 key,mp=r;locs=[l for l in mp.get('locations',[]) if str(l.get('countryCode','')).upper()=='IT' and str(l.get('partyId','')).upper()=='ATE'];samples=[]
 for l in locs[:100]:
  lid=str(l.get('id') or '')
  if not lid:continue
  try:_,detail=api(f'{BASE}/tenants/{TENANT}/locations/{lid}',key);_,tp=api(f'{BASE}/tenants/{TENANT}/locations/{lid}/tariffs',key)
  except:continue
  tariffs=tp if isinstance(tp,list) else (tp.get('tariffs',[]) if isinstance(tp,dict) else []);rows=[]
  for t in tariffs:
   ids=t.get('identifiers') or {}
   for pc in t.get('priceComponents') or []:
    if str(pc.get('priceDimension','')).upper()=='ENERGY' and str(pc.get('currency','')).upper()=='EUR':
     v=(pc.get('price') or {}).get('incl_vat')
     if isinstance(v,(int,float)) and v>0:rows.append({'evseId':ids.get('evseId'),'connectorId':ids.get('connectorId'),'eurPerKwh':v})
  if rows:samples.append({'locationId':lid,'name':detail.get('displayName') or detail.get('locationName') or l.get('displayName'),'city':detail.get('city') or l.get('city'),'tariffs':rows[:20]})
  if len(samples)>=5:break
 rep.update({'italyAtlanteMapLocations':len(locs),'stationTariffSamples':samples});OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
 if not samples:raise SystemExit('Credential works but station tariff sample absent')
 print(json.dumps({'italyAtlanteLocations':len(locs),'stationTariffSamples':samples},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
