#!/usr/bin/env python3
"""Recover public-client myAtlante config and prove Italy station tariffs read-only.
Transient decompilation only; recovered client config is masked and never persisted.
"""
from __future__ import annotations
import collections,json,re,sys,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1';TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39'
MAP=f'{BASE}/tenants/{TENANT}/map-locations?latLongBottomLeft=35%2C5&latLongTopRight=48%2C19&evseTypes=AC%2CDC%2CHPC&locationStatus=ALL&connectorTypes=CCS%2CCHADEMO%2CTYPE2'
OUT=Path('data/reports/atlante_hermes_config_probe.json');SEC={'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}
def api(url,key,ver='2.1.0'):
 q=urllib.request.Request(url,headers={'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT','X-App-Version':ver,'X-App-Platform':'android','User-Agent':f'myAtlante/{ver} (Android)'})
 with urllib.request.urlopen(q,timeout=10) as r:return r.status,json.loads(r.read().decode())
def test(c):
 try:
  st,p=api(MAP,c);return (c,p) if st==200 and isinstance(p,dict) and isinstance(p.get('locations'),list) else None
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
def hydrate(key,l):
 lid=str(l.get('id') or '')
 if not lid:return None
 try:_,d=api(f'{BASE}/tenants/{TENANT}/locations/{lid}',key);return l,d
 except:return None
def main():
 text=Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore');targeted,fallback,anchors=literal_candidates(text);r,n=probe(targeted,1000);n2=0
 if not r:r,n2=probe(fallback,2500)
 rep={'source':'temporary Hermes/React Native decompilation of public myAtlante Android package','anchors':anchors,'targetedCandidateCount':len(targeted),'targetedProbed':n,'fallbackCandidateCount':len(fallback),'fallbackProbed':n2,'clientCredentialRecovered':bool(r),'clientCredentialPersisted':False,'security':SEC}
 if not r:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,indent=2)+'\n');raise SystemExit('No client config validated')
 key,mp=r;alllocs=mp.get('locations') or [];rep['mapLocationCount']=len(alllocs);details=[]
 with ThreadPoolExecutor(max_workers=24) as ex:
  fs=[ex.submit(hydrate,key,l) for l in alllocs[:800]]
  for f in as_completed(fs):
   x=f.result()
   if x:details.append(x)
 italy=[]
 for l,d in details:
  cc=str(d.get('countryCode') or l.get('countryCode') or '').upper();op=str(d.get('operatorName') or l.get('operatorName') or '');party=str(d.get('partyId') or l.get('partyId') or '').upper()
  if cc=='IT' and 'atlante' in op.lower():italy.append((l,d))
 rep['hydratedCount']=len(details);rep['italyAtlanteLocationCount']=len(italy);rep['italyIdentityCounts']=dict(collections.Counter(f"{str(d.get('partyId') or l.get('partyId') or '').upper()}|{str(d.get('operatorName') or l.get('operatorName') or '')}" for l,d in italy))
 samples=[]
 for l,d in italy[:80]:
  lid=str(d.get('id') or l.get('id') or '')
  try:_,tp=api(f'{BASE}/tenants/{TENANT}/locations/{lid}/tariffs',key)
  except:continue
  tariffs=tp if isinstance(tp,list) else (tp.get('tariffs',[]) if isinstance(tp,dict) else []);rows=[]
  for t in tariffs:
   ids=t.get('identifiers') or {}
   for pc in t.get('priceComponents') or []:
    if str(pc.get('priceDimension','')).upper()=='ENERGY' and str(pc.get('currency','')).upper()=='EUR':
     v=(pc.get('price') or {}).get('incl_vat')
     if isinstance(v,(int,float)) and v>0:rows.append({'evseId':ids.get('evseId'),'connectorId':ids.get('connectorId'),'eurPerKwh':v})
  if rows:samples.append({'locationId':lid,'name':d.get('displayName') or d.get('locationName') or l.get('displayName'),'city':d.get('city') or l.get('city'),'partyId':d.get('partyId') or l.get('partyId'),'operatorName':d.get('operatorName') or l.get('operatorName'),'tariffs':rows[:20]})
  if len(samples)>=8:break
 rep['stationTariffSamples']=samples;OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
 if not samples:raise SystemExit('Credential valid but no direct Italy tariff sample after live identity resolution')
 print(json.dumps({'italyAtlanteLocations':len(italy),'identityCounts':rep['italyIdentityCounts'],'stationTariffSamples':samples},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
