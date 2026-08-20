#!/usr/bin/env python3
"""Static-only extraction of context *key names* for FastVolt/EVOne.

No values are persisted. The probe looks for object/header/field names containing
business/organisation/organization/tenant around known read-only station routes and
globally in the public Android clients.
"""
from __future__ import annotations
import datetime as dt
import json,re,subprocess,tempfile,urllib.request,zipfile
from pathlib import Path

OUT=Path('artifacts/morocco-fastvolt-evone-context-keys');OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
APPS={'fastvolt':'ma.fastgo','evone':'ma.evplug'}
ROUTES=('/app/charging_stations/','/user/get_charging_station_details/','GetChargingStationsCall')
KEYWORDS=('business','organisation','organization','tenant')
# Extract only syntactic key/symbol names, never right-hand-side values.
KEY_PATTERNS=[
 re.compile(r"['\"]([A-Za-z][A-Za-z0-9_-]{1,64}(?:business|organisation|organization|tenant)[A-Za-z0-9_-]{0,64})['\"]\s*[:=]",re.I),
 re.compile(r"\b([A-Za-z][A-Za-z0-9_-]{1,64}(?:business|organisation|organization|tenant)[A-Za-z0-9_-]{0,64})\b\s*[:=]",re.I),
]
SENSITIVE=re.compile(r'(password|secret|token|bearer|authorization|cookie|email|phone|wallet|payment|card|account|customer|user)',re.I)

def dl(package,dest):
 for fmt in ('XAPK','APK'):
  try:
   q=urllib.request.Request(f'https://d.apkpure.com/b/{fmt}/{package}?version=latest',headers={'User-Agent':UA,'Accept':'*/*'})
   with urllib.request.urlopen(q,timeout=120) as r:data=r.read()
   if len(data)>100000:dest.write_bytes(data);return fmt,len(data)
  except Exception:pass
 return None,0

def uz(src,dst):
 dst.mkdir(parents=True,exist_ok=True)
 try:
  with zipfile.ZipFile(src) as z:
   for i in z.infolist():
    if '..' not in Path(i.filename).parts and i.file_size<180*1024*1024:z.extract(i,dst)
 except Exception:pass

def lines(path):
 try:
  if path.name in ('libapp.so','index.android.bundle','main.jsbundle'):
   return subprocess.run(['strings','-a','-n','3',str(path)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
  return path.read_text(errors='replace').splitlines()
 except Exception:return []

def extract_keys(text):
 out=[]
 for rx in KEY_PATTERNS:
  for m in rx.finditer(text):
   k=m.group(1)
   if not SENSITIVE.search(k) and k not in out:out.append(k[:80])
 return out

def inspect(name,package,root):
 pkg=root/f'{name}.pkg';fmt,size=dl(package,pkg);rec={'package':package,'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size}
 if not fmt:return rec
 tree=root/f'{name}-tree';uz(pkg,tree)
 for i,a in enumerate(list(tree.rglob('*.apk'))[:30]):uz(a,tree/f'apk_{i}')
 ls=[]
 for p in tree.rglob('*'):
  if not p.is_file():continue
  try:
   if p.stat().st_size>150*1024*1024:continue
  except OSError:continue
  if p.name in ('libapp.so','index.android.bundle','main.jsbundle','app.config') or p.suffix.lower() in ('.json','.js','.txt','.xml'):ls.extend(lines(p))
 global_counts={};near_counts={};route_windows=0
 for line in ls:
  for k in extract_keys(line):global_counts[k]=global_counts.get(k,0)+1
 for i,line in enumerate(ls):
  if not any(r.lower() in line.lower() for r in ROUTES):continue
  route_windows+=1
  window=' '.join(ls[max(0,i-30):min(len(ls),i+31)])
  for k in extract_keys(window):near_counts[k]=near_counts.get(k,0)+1
 rec.update({'route_windows_examined':route_windows,'global_context_key_names':dict(sorted(global_counts.items(),key=lambda x:(-x[1],x[0]))[:80]),'context_key_names_near_station_routes':dict(sorted(near_counts.items(),key=lambda x:(-x[1],x[0]))[:80]),'raw_values_persisted':False})
 return rec

def main():
 report={'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'raw_packages_persisted':False,'raw_bundle_context_persisted':False,'raw_values_persisted':False,'credentials_or_ids_persisted':False},'apps':{}}
 with tempfile.TemporaryDirectory(prefix='tcc-ma-context-keys-') as td:
  root=Path(td)
  for n,p in APPS.items():report['apps'][n]=inspect(n,p,root)
 (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v.get('context_key_names_near_station_routes',{}) for k,v in report['apps'].items()}))
if __name__=='__main__':main()
