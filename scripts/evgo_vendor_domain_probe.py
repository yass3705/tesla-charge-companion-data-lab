#!/usr/bin/env python3
"""Lightweight sanitized EVGO vendor/domain discovery.

Read-only, no login, no mutation. Downloads the public Android package to a temporary
folder, extracts printable strings, and persists only domain-frequency and marker-count
summaries. No raw bundle lines, query strings, credentials, tokens, account or payment
data are persisted.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/evgo-vendor-domain-lite'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.4)'
DOMAIN=re.compile(r'(?i)(?:[a-z0-9][a-z0-9-]{0,62}\.){1,6}(?:com|ma|app|io|net|cloud|tech|dev|co|eu)')
IGNORE=('googleapis.com','google.com','gstatic.com','googleusercontent.com','firebaseio.com','firebaseapp.com','bugsnag.com','smartbear.com','developer.mozilla.org','github.com','w3.org','reactnative.dev','react.dev','swmansion.com','auth0.com','sentry.io','stripe.com','apple.com','microsoft.com','apkpure.com')
VENDORS=('monta','spirii','virta','driivz','greenflux','ampeco','chargecloud','plugsurfing','has-to-be','beenergised','numocity','saascharge','lastmile','chargepoint','evconnect','nareva','evgo')
MARKERS=('evses/search','locations/withevse','ongoingsessionbyevseid','session:start:pricing','pricingperiods','idle-fee','chargepointtag','baseurl','base_url','apiurl','api_url','remoteconfig','remote config','websocket','socket.io')

def dl(dest:Path):
 for fmt in ('XAPK','APK'):
  try:
   req=urllib.request.Request(f'https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest',headers={'User-Agent':UA,'Accept':'*/*'})
   with urllib.request.urlopen(req,timeout=120) as r:data=r.read()
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

def text_lines(path:Path):
 try:
  if path.name in ('libapp.so','index.android.bundle','main.jsbundle') or path.suffix.lower() in ('.arsc','.dex'):
   return subprocess.run(['strings','-a','-n','4',str(path)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
  return path.read_text(errors='replace').splitlines()
 except Exception:return []

def main():
 result={'schema_version':1,'package':PACKAGE,'policy':{'read_only':True,'no_login':True,'no_mutations':True,'raw_package_persisted':False,'raw_credentials_persisted':False,'raw_lines_persisted':False}}
 with tempfile.TemporaryDirectory(prefix='evgo-domain-lite-') as td:
  root=Path(td);pkg=root/'evgo.pkg';fmt,size=dl(pkg);result.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
  if not fmt:
   (OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return
  tree=root/'tree';unzip(pkg,tree)
  for n,a in enumerate(list(tree.rglob('*.apk'))[:30]):unzip(a,tree/f'apk_{n}')
  domains=Counter(); vendor=Counter(); markers=Counter(); files_scanned=0; lines_scanned=0
  for p in tree.rglob('*'):
   if not p.is_file():continue
   try:sz=p.stat().st_size
   except OSError:continue
   if sz>150*1024*1024:continue
   if not (p.name in ('libapp.so','index.android.bundle','main.jsbundle','app.config','AndroidManifest.xml','resources.arsc') or p.suffix.lower() in ('.json','.js','.txt','.xml','.dex')):continue
   files_scanned+=1
   for line in text_lines(p):
    lines_scanned+=1; low=line.lower()
    for v in VENDORS:
     if v in low:vendor[v]+=low.count(v)
    for m in MARKERS:
     if m in low:markers[m]+=low.count(m)
    for d in DOMAIN.findall(low):
     d=d.lower().strip('.')
     if any(d==x or d.endswith('.'+x) for x in IGNORE):continue
     if any(k in d for k in ('api','ev','charge','ocpp','station','mobility','nareva','evgo','monta','spirii','virta','driivz','greenflux','ampeco','cloud')):
      domains[d]+=1
  result['files_scanned']=files_scanned;result['lines_scanned']=lines_scanned
  result['vendor_keyword_counts']=dict(vendor)
  result['marker_counts']=dict(markers)
  result['candidate_domains']=[{'domain':d,'occurrences':n} for d,n in domains.most_common(100)]
 (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'download_ok':result.get('download_ok'),'vendors':result.get('vendor_keyword_counts',{}),'markers':result.get('marker_counts',{}),'domains':result.get('candidate_domains',[])[:30]},ensure_ascii=False))

if __name__=='__main__':main()
