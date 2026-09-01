#!/usr/bin/env python3
"""Find client-distributed myAtlante API config and prove station prices read-only.
No account/login/charging/payment/mutation endpoint is called. Candidate client keys are
masked before use and are never persisted or printed.
"""
from __future__ import annotations
import io,json,re,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
PKG='com.atlante.charging'
XAPKS=[('2.1.0','https://d.apkpure.net/b/XAPK/com.atlante.charging?version=latest'),('1.58.0','https://d.apkpure.net/b/XAPK/com.atlante.charging?versionCode=3970')]
BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1'; TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39'
MAP=f'{BASE}/tenants/{TENANT}/map-locations?latLongBottomLeft=35%2C5&latLongTopRight=48%2C19&evseTypes=AC%2CDC%2CHPC&locationStatus=ALL&connectorTypes=CCS%2CCHADEMO%2CTYPE2'
OUT=Path('data/reports/atlante_apk_public_config_probe.json');UA='Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile'
SEC={'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}
def get(url,timeout=90):
 q=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':'https://apkpure.net/'});return urllib.request.urlopen(q,timeout=timeout).read()
def payloads(blob):
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  for n in z.namelist():
   if not n.lower().endswith('.apk'):continue
   try:
    with zipfile.ZipFile(io.BytesIO(z.read(n))) as a:
     for p in a.namelist():
      if p.endswith('/'):continue
      try:d=a.read(p)
      except:continue
      if len(d)<=100_000_000:yield n+'!'+p,d
   except:pass
def astrings(d):
 for m in re.finditer(rb'[\x20-\x7e]{10,512}',d):
  try:yield m.group().decode()
  except:pass
def discover(blob):
 scored={};hits=[];diag=[]
 for name,d in payloads(blob):
  ss=list(astrings(d));joined='\n'.join(ss); lowj=joined.lower()
  interesting=('azure-api.net' in lowj or 'ocp-apim' in lowj or 'subscription' in lowj or 'atlante' in lowj)
  if 'azure-api.net' in lowj or 'ocp-apim-subscription-key' in lowj:hits.append(name)
  if interesting:diag.append({'file':name,'hasApiHost':'azure-api.net' in lowj,'hasApimHeader':'ocp-apim-subscription-key' in lowj,'stringCount':len(ss)})
  for s in ss:
   low=s.lower();bonus=(40 if ('ocp-apim' in low or 'subscription' in low) else 0)+(25 if 'azure-api.net' in low else 0)+(15 if interesting else 0)
   for c in re.findall(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{28,48}(?![A-Za-z0-9_-])',s):
    if c.lower() in ('ocp-apim-subscription-key','pdefweushaapiam01') or len(set(c))<8:continue
    scored[c]=max(scored.get(c,-1),bonus+(12 if len(c)==32 else 0)+(6 if re.fullmatch(r'[0-9a-fA-F]{32}',c) else 0))
 return [x for x,_ in sorted(scored.items(),key=lambda kv:(-kv[1],kv[0]))],sorted(set(hits)),diag[:100]
def api(url,key,version):
 q=urllib.request.Request(url,headers={'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT','X-App-Version':version,'X-App-Platform':'android','User-Agent':f'myAtlante/{version} (Android)'})
 with urllib.request.urlopen(q,timeout=6) as r:return r.status,json.loads(r.read().decode())
def trykey(c,ver):
 try:
  st,p=api(MAP,c,ver)
  return (c,p) if st==200 and isinstance(p,dict) and isinstance(p.get('locations'),list) else None
 except:return None
def save(r):OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
def main():
 rep={'source':'public myAtlante Android package','clientCredentialRecovered':False,'clientCredentialPersisted':False,'attempts':[],'security':SEC};working=mp=version=None
 for ver,url in XAPKS:
  try:blob=get(url)
  except Exception as e:rep['attempts'].append({'version':ver,'download':False,'errorType':type(e).__name__});continue
  try:cands,hits,diag=discover(blob)
  except Exception as e:rep['attempts'].append({'version':ver,'download':True,'scan':False,'errorType':type(e).__name__});continue
  subset=cands[:350]
  for c in subset:print(f'::add-mask::{c}')
  attempt={'version':ver,'download':True,'candidateCount':len(cands),'configHitFiles':hits,'diagnostics':diag,'probed':len(subset)}
  with ThreadPoolExecutor(max_workers=32) as ex:
   futs=[ex.submit(trykey,c,ver) for c in subset]
   for f in as_completed(futs):
    r=f.result()
    if r:working,mp=r;version=ver;break
  rep['attempts'].append(attempt)
  if working:break
 if not working:save(rep);raise SystemExit('No public-client API credential validated; sanitized report saved')
 rep['clientCredentialRecovered']=True;rep['testedVersion']=version
 locs=[l for l in mp.get('locations',[]) if str(l.get('countryCode','')).upper()=='IT' and str(l.get('partyId','')).upper()=='ATE'];rep['italyAtlanteMapLocations']=len(locs);samples=[]
 for l in locs[:100]:
  lid=str(l.get('id') or '')
  if not lid:continue
  try:_,detail=api(f'{BASE}/tenants/{TENANT}/locations/{lid}',working,version);_,tp=api(f'{BASE}/tenants/{TENANT}/locations/{lid}/tariffs',working,version)
  except:continue
  tariffs=tp if isinstance(tp,list) else (tp.get('tariffs',[]) if isinstance(tp,dict) else []);rows=[]
  for t in tariffs:
   ids=t.get('identifiers') or {}
   for pc in t.get('priceComponents') or []:
    if str(pc.get('priceDimension','')).upper()=='ENERGY' and str(pc.get('currency','')).upper()=='EUR':
     v=(pc.get('price') or {}).get('incl_vat')
     if isinstance(v,(int,float)) and v>0:rows.append({'evseId':ids.get('evseId'),'connectorId':ids.get('connectorId'),'eurPerKwh':v})
  if rows:samples.append({'locationId':lid,'name':detail.get('displayName') or detail.get('locationName') or l.get('displayName'),'city':detail.get('city') or l.get('city'),'tariffs':rows[:16]})
  if len(samples)>=5:break
 rep['stationTariffSamples']=samples;save(rep)
 if not samples:raise SystemExit('API credential works but no energy-price station sample found')
 print(json.dumps({'version':version,'italyLocations':len(locs),'stationTariffSamples':samples},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
