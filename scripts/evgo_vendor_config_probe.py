#!/usr/bin/env python3
"""Sanitized vendor/config discovery for Morocco EVGO Android client.

Read-only, no login and no mutation. Public Android packages are downloaded only into a
temporary directory. The report persists only counts, harmless vendor/config symbols and
sanitized domain names. Client keys, JWTs, query strings, account/payment data and raw
packages are never persisted.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/evgo-vendor-config'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.3)'
DOMAIN=re.compile(r'(?i)(?:[a-z0-9][a-z0-9-]{0,62}\.){1,5}(?:com|ma|app|io|net|cloud|tech|dev|co|eu)')
LONG=re.compile(r'\b[A-Za-z0-9_-]{40,}\b')
SENSITIVE=re.compile(r'(?i)(password|secret|authorization|bearer|cookie|access[_-]?token|refresh[_-]?token|client[_-]?secret|payment|wallet|card|invoice|email|phone|customer|account)')
VENDORS=('monta','spirii','virta','driivz','greenflux','ampeco','chargecloud','plugsurfing','has-to-be','beenergised','numocity','saascharge','lastmile','chargepoint','evconnect','nareva','evgo')
MARKERS=('baseurl','base_url','apiurl','api_url','backend','endpoint','environment','remoteconfig','remote config','expo_update_url','expo updates','evses/search','locations/withEVSE','ongoingSessionByEvseId','session:start:pricing','pricingPeriods','idle-fee','chargePointTag')
IGNORE=('googleapis.com','google.com','gstatic.com','googleusercontent.com','firebaseio.com','firebaseapp.com','bugsnag.com','smartbear.com','developer.mozilla.org','github.com','w3.org','reactnative.dev','react.dev','swmansion.com','auth0.com','sentry.io','stripe.com','apple.com','microsoft.com')

def clean(s:str)->str:
 s=LONG.sub('[REDACTED]',s)
 s=re.sub(r'(?i)(bearer\s+)[^\s,;"\']+',r'\1[REDACTED]',s)
 s=re.sub(r'https?://([^\s/?"\']+)[^\s"\']*',lambda m:'https://'+m.group(1)+'/[PATH_REDACTED]',s)
 return s[:1000]

def dl(dest:Path):
 for fmt in ('XAPK','APK'):
  try:
   q=urllib.request.Request(f'https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest',headers={'User-Agent':UA,'Accept':'*/*'})
   with urllib.request.urlopen(q,timeout=120) as r:data=r.read()
   if len(data)>100000:dest.write_bytes(data);return fmt,len(data)
  except Exception:pass
 return None,0

def unzip(src:Path,dst:Path):
 dst.mkdir(parents=True,exist_ok=True)
 try:
  with zipfile.ZipFile(src) as z:
   for i in z.infolist():
    if '..' not in Path(i.filename).parts and i.file_size<180*1024*1024:z.extract(i,dst)
 except Exception:pass

def strings(p:Path):
 try:
  if p.name in ('libapp.so','index.android.bundle','main.jsbundle') or p.suffix.lower() in ('.arsc','.dex'):
   return subprocess.run(['strings','-a','-n','4',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
  return p.read_text(errors='replace').splitlines()
 except Exception:return []

def main():
 result={'schema_version':1,'package':PACKAGE,'policy':{'read_only':True,'no_login':True,'no_mutations':True,'raw_package_persisted':False,'raw_credentials_persisted':False,'query_strings_persisted':False}}
 with tempfile.TemporaryDirectory(prefix='evgo-vendor-config-') as td:
  root=Path(td);pkg=root/'evgo.pkg';fmt,size=dl(pkg);result.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
  if not fmt:(OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return
  tree=root/'tree';unzip(pkg,tree)
  for n,a in enumerate(list(tree.rglob('*.apk'))[:30]):unzip(a,tree/f'apk_{n}')
  lines=[]
  for p in tree.rglob('*'):
   if not p.is_file():continue
   try:sz=p.stat().st_size
   except OSError:continue
   if sz>150*1024*1024:continue
   if p.name in ('libapp.so','index.android.bundle','main.jsbundle','app.config','AndroidManifest.xml','resources.arsc') or p.suffix.lower() in ('.json','.js','.txt','.xml','.dex'):
    for x in strings(p):
     if x and len(x)<5000:lines.append((str(p.relative_to(tree)),x))
  joined='\n'.join(x for _,x in lines).lower()
  result['vendor_keyword_counts']={v:joined.count(v.lower()) for v in VENDORS}
  domains=Counter()
  contexts=[]
  for src,line in lines:
   low=line.lower()
   for d in DOMAIN.findall(low):
    d=d.lower().strip('.')
    if any(d==x or d.endswith('.'+x) for x in IGNORE):continue
    if any(k in d for k in ('api','ev','charge','monta','spirii','virta','nareva','evgo','ocpp','station','mobility')):
     domains[d]+=1
   if (any(v in low for v in VENDORS) or any(m.lower() in low for m in MARKERS)) and not SENSITIVE.search(low):
    c=clean(line.strip())
    if c and c not in (x['line'] for x in contexts):contexts.append({'source':src,'line':c})
  result['candidate_domains']=[{'domain':d,'occurrences':n} for d,n in domains.most_common(80)]
  result['config_vendor_signals']=contexts[:160]
  result['marker_counts']={m:joined.count(m.lower()) for m in MARKERS}
 (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'download_ok':result.get('download_ok'),'vendors':{k:v for k,v in result.get('vendor_keyword_counts',{}).items() if v},'domains':result.get('candidate_domains',[])[:20],'markers':{k:v for k,v in result.get('marker_counts',{}).items() if v}}))
if __name__=='__main__':main()
