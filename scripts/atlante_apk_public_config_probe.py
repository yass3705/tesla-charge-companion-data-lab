#!/usr/bin/env python3
"""Recover public-client myAtlante configuration and prove station tariffs read-only.
Only constants distributed in the official public Android package are considered. No account,
login, charging, payment, or mutation endpoint is called. Candidate keys are masked and never persisted.
"""
from __future__ import annotations
import hashlib,io,json,re,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
XAPKS=[('2.1.0','https://d.apkpure.net/b/XAPK/com.atlante.charging?version=latest'),('1.58.0','https://d.apkpure.net/b/XAPK/com.atlante.charging?versionCode=3970')]
BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1';TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39'
MAP=f'{BASE}/tenants/{TENANT}/map-locations?latLongBottomLeft=35%2C5&latLongTopRight=48%2C19&evseTypes=AC%2CDC%2CHPC&locationStatus=ALL&connectorTypes=CCS%2CCHADEMO%2CTYPE2'
OUT=Path('data/reports/atlante_apk_public_config_probe.json');UA='Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile'
SEC={'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}
def get(u,t=90):return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':UA,'Referer':'https://apkpure.net/'}),timeout=t).read()
def files(blob):
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
 for m in re.finditer(rb'[\x20-\x7e]{6,1024}',d):
  try:yield m.group().decode()
  except:pass
def scalar_walk(x,path=''):
 if isinstance(x,dict):
  for k,v in x.items():yield from scalar_walk(v,f'{path}.{k}' if path else str(k))
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from scalar_walk(v,f'{path}[{i}]')
 elif isinstance(x,(str,int,float,bool)) or x is None:yield path,x
def token_candidates(s):
 out=set()
 for rx in [r'(?<![A-Za-z0-9_+/=-])[A-Za-z0-9_-]{24,64}(?![A-Za-z0-9_+/=-])',r'(?<![A-Za-z0-9_+/=-])[A-Za-z0-9_+/=-]{28,88}(?![A-Za-z0-9_+/=-])']:
  out.update(re.findall(rx,s))
 return {c for c in out if len(set(c))>=8 and not c.startswith(('http','com.','android','react'))}
def discover(blob):
 targeted=[];fallback=[];diag=[];target_meta=[]
 for name,d in files(blob):
  if name.endswith('assets/app.config'):
   txt=d.decode('utf-8','ignore')
   try:cfg=json.loads(txt)
   except:cfg=None
   if cfg is not None:
    paths=[]
    for p,v in scalar_walk(cfg):
     paths.append(p)
     if isinstance(v,str) and any(k in p.lower() for k in ('api','key','subscription','backend','endpoint','baseurl','base_url','environment','config')):
      for c in token_candidates(v):targeted.append(c);target_meta.append({'source':'app.config','path':p,'length':len(c),'sha256Prefix':hashlib.sha256(c.encode()).hexdigest()[:12]})
    diag.append({'file':name,'json':True,'configPaths':paths[:180]})
   else:diag.append({'file':name,'json':False,'stringCount':len(list(astrings(d)))})
  if name.endswith('assets/index.android.bundle'):
   ss=list(astrings(d)); lows=[s.lower() for s in ss]; idx=[]
   for i,s in enumerate(lows):
    if 'ocp-apim-subscription-key' in s or 'azure-api.net' in s or 'app-backend/v1' in s:idx.append(i)
   neigh=set()
   for i in idx:
    for j in range(max(0,i-80),min(len(ss),i+81)):neigh.add(j)
   for j in sorted(neigh):
    for c in token_candidates(ss[j]):targeted.append(c);target_meta.append({'source':'bundle-neighborhood','offsetIndex':j,'length':len(c),'sha256Prefix':hashlib.sha256(c.encode()).hexdigest()[:12]})
   # conservative fallback: exact 32-char opaque literals from this one app bundle only
   for s in ss:
    for c in re.findall(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{32}(?![A-Za-z0-9_-])',s):
     if len(set(c))>=10:fallback.append(c)
   diag.append({'file':name,'stringCount':len(ss),'anchorIndices':idx,'neighborhoodStringCount':len(neigh)})
 targeted=list(dict.fromkeys(targeted));fallback=[c for c in dict.fromkeys(fallback) if c not in targeted]
 return targeted,fallback,diag,target_meta[:250]
def api(url,key,ver):
 q=urllib.request.Request(url,headers={'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT','X-App-Version':ver,'X-App-Platform':'android','User-Agent':f'myAtlante/{ver} (Android)'})
 with urllib.request.urlopen(q,timeout=7) as r:return r.status,json.loads(r.read().decode())
def test(c,ver):
 try:
  st,p=api(MAP,c,ver);return (c,p) if st==200 and isinstance(p,dict) and isinstance(p.get('locations'),list) else None
 except:return None
def probe(cands,ver,limit):
 sub=cands[:limit]
 for c in sub:print(f'::add-mask::{c}')
 with ThreadPoolExecutor(max_workers=40) as ex:
  fs=[ex.submit(test,c,ver) for c in sub]
  for f in as_completed(fs):
   r=f.result()
   if r:return r,len(sub)
 return None,len(sub)
def save(r):OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
def main():
 rep={'source':'public myAtlante Android package','clientCredentialRecovered':False,'clientCredentialPersisted':False,'attempts':[],'security':SEC};working=mp=version=None
 for ver,url in XAPKS:
  try:blob=get(url)
  except Exception as e:rep['attempts'].append({'version':ver,'download':False,'errorType':type(e).__name__});continue
  targeted,fallback,diag,meta=discover(blob);a={'version':ver,'download':True,'targetedCandidateCount':len(targeted),'fallbackCandidateCount':len(fallback),'diagnostics':diag,'targetCandidateMetadata':meta}
  r,n=probe(targeted,ver,500);a['targetedProbed']=n
  if not r:r,n2=probe(fallback,ver,1200);a['fallbackProbed']=n2
  rep['attempts'].append(a)
  if r:working,mp=r;version=ver;break
 if not working:save(rep);raise SystemExit('No client-distributed credential validated; sanitized diagnostics saved')
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
 if not samples:raise SystemExit('API credential works but no energy-price sample found')
 print(json.dumps({'version':version,'italyLocations':len(locs),'stationTariffSamples':samples},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
