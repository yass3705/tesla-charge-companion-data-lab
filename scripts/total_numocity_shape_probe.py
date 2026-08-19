#!/usr/bin/env python3
"""Infer TotalEnergies/Numocity read-only request shape from the public Android client.

No network calls to charging backends are made. The script only downloads the public app
package, scans local client strings around known Numocity route names, and persists aggregate
counts of nearby HTTP verbs / harmless parameter names. No raw strings, credentials, tokens,
query values or account/payment data are persisted.
"""
from __future__ import annotations
import json,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path

PACKAGE='com.namp.totalev'
OUT=Path('artifacts/total-numocity-shape'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
ROUTES=('qr-connector','get-connector-status','connector-status','station','charger','location')
VERBS=('get','post','put','patch','delete')
PARAMS=('connectorid','connector_id','chargerid','charger_id','stationid','station_id','evseid','evse_id','latitude','longitude','lat','lng','qr','qrcode','qr_code')

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

def lines(path:Path):
 try:
  if path.name in ('libapp.so','index.android.bundle','main.jsbundle') or path.suffix.lower() in ('.arsc','.dex'):
   return subprocess.run(['strings','-a','-n','3',str(path)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
  return path.read_text(errors='replace').splitlines()
 except Exception:return []

def main():
 result={'schema_version':1,'package':PACKAGE,'policy':{'read_only':True,'no_login':True,'no_mutations':True,'backend_requests_made':False,'raw_package_persisted':False,'raw_strings_persisted':False,'raw_credentials_persisted':False}}
 with tempfile.TemporaryDirectory(prefix='total-numocity-shape-') as td:
  root=Path(td);pkg=root/'total.pkg';fmt,size=dl(pkg);result.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
  if not fmt:
   (OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return
  tree=root/'tree';unzip(pkg,tree)
  for n,a in enumerate(list(tree.rglob('*.apk'))[:30]):unzip(a,tree/f'apk_{n}')
  all_lines=[]
  for p in tree.rglob('*'):
   if not p.is_file():continue
   try:sz=p.stat().st_size
   except OSError:continue
   if sz>150*1024*1024:continue
   if p.name in ('libapp.so','index.android.bundle','main.jsbundle','app.config','AndroidManifest.xml','resources.arsc') or p.suffix.lower() in ('.json','.js','.txt','.xml','.dex'):
    all_lines.extend(x for x in lines(p) if x and len(x)<5000)
  route_hits=Counter(); nearby_verbs={r:Counter() for r in ROUTES}; nearby_params={r:Counter() for r in ROUTES}
  lows=[x.lower() for x in all_lines]
  for i,low in enumerate(lows):
   for route in ROUTES:
    if route in low:
     route_hits[route]+=low.count(route)
     lo=max(0,i-10);hi=min(len(lows),i+11);block=' '.join(lows[lo:hi])
     for v in VERBS:
      if v in block:nearby_verbs[route][v]+=block.count(v)
     for p in PARAMS:
      if p in block:nearby_params[route][p]+=block.count(p)
  result['route_hits']=dict(route_hits)
  result['nearby_http_verb_counts']={r:dict(c) for r,c in nearby_verbs.items() if c}
  result['nearby_parameter_name_counts']={r:dict(c) for r,c in nearby_params.items() if c}
  result['interpretation']='Counts are heuristic client-bundle proximity signals only; they do not validate a request method or parameter value by themselves.'
 (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'routes':result.get('route_hits',{}),'verbs':result.get('nearby_http_verb_counts',{}),'params':result.get('nearby_parameter_name_counts',{})},ensure_ascii=False))

if __name__=='__main__':main()
