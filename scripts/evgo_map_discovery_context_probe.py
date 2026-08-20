#!/usr/bin/env python3
"""Sanitized EVGO map-discovery context probe.

Read-only static analysis of the publicly distributed Android package. The goal is to identify
client symbols/routes that discover public map/location IDs before POST /app/locations hydrates
those IDs. No backend requests, login, credentials, raw packages, query strings or account data
are persisted.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from pathlib import Path

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/evgo-map-discovery-context');OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.3)'
SENSITIVE=re.compile(r'(password|secret|token|authorization|cookie|email|phone|wallet|invoice|payment|card|account|customer|bearer)',re.I)
LONG=re.compile(r'\b[A-Za-z0-9_-]{40,}\b')
MARKERS=(
 'last_location_coords','last_location_name','togejsonfeature','geojson','mapsearch','map/searchfield',
 'visible region','visibleregion','mapbounds','bounds','bounding','northeast','southwest','latitudeDelta','longitudeDelta',
 'locationids','location_ids','location ids','locationsids','locations_ids','getlocations','fetchlocations','loadlocations',
 'nearby','around','viewport','region','cluster','clusters','map markers','mapmarkers','chargepointtag','charge point tag',
 'locations:', 'locations/', 'app/locations'
)
ROUTE=re.compile(r'/(?:api/)?(?:v\d+/)?app/[A-Za-z0-9_./:{}-]{2,160}',re.I)

def clean(s:str)->str:
 s=LONG.sub('[REDACTED]',s)
 s=re.sub(r'(?i)(bearer\s+)[^\s,;"\']+',r'\1[REDACTED]',s)
 s=re.sub(r'(https?://[^\s?"\']+)\?[^\s"\']+',r'\1?[REDACTED_QUERY]',s)
 return s[:1400]

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

def lines(p:Path):
 try:
  if p.name in ('libapp.so','index.android.bundle','main.jsbundle'):
   return subprocess.run(['strings','-a','-n','2',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
  return p.read_text(errors='replace').splitlines()
 except Exception:return []

def main():
 out={'schema_version':1,'package':PACKAGE,'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'raw_package_persisted':False,'raw_credentials_persisted':False,'query_strings_persisted':False}}
 with tempfile.TemporaryDirectory(prefix='evgo-map-discovery-') as td:
  root=Path(td);pkg=root/'evgo.pkg';fmt,size=dl(pkg);out.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
  if not fmt:(OUT/'summary.json').write_text(json.dumps(out,indent=2)+'\n');return
  tree=root/'tree';unzip(pkg,tree)
  for n,a in enumerate(list(tree.rglob('*.apk'))[:30]):unzip(a,tree/f'apk_{n}')
  corpus=[]
  for p in tree.rglob('*'):
   if not p.is_file():continue
   try:sz=p.stat().st_size
   except OSError:continue
   if sz>150*1024*1024:continue
   if p.name in ('libapp.so','index.android.bundle','main.jsbundle','app.config') or p.suffix.lower() in ('.json','.js','.txt','.xml'):
    corpus.extend((str(p.relative_to(tree)),x) for x in lines(p))
  hits=[];routes=[];marker_counts={m:0 for m in MARKERS}
  for i,(src,line) in enumerate(corpus):
   low=line.lower();matched=[m for m in MARKERS if m.lower() in low]
   if not matched:continue
   for m in matched:marker_counts[m]+=1
   ctx=[]
   for j in range(max(0,i-14),min(len(corpus),i+15)):
    raw=corpus[j][1].strip()
    if not raw or len(raw)>3000:continue
    if SENSITIVE.search(raw) and not any(k in raw.lower() for k in ('location','map','evse','station','charger','connector','latitude','longitude','bounds','region','cluster')):continue
    c=clean(raw);ctx.append(c)
    for r in ROUTE.findall(raw):
     r=clean(r).split('?')[0]
     if r not in routes:routes.append(r)
   hits.append({'source':src,'matched_markers':matched,'line':clean(line.strip()),'context':ctx[:38]})
   if len(hits)>=140:break
  # Rank route-like strings by public map/discovery relevance.
  rel=[r for r in routes if re.search(r'(location|map|evse|station|charger|cluster|near|search)',r,re.I)]
  out.update({'marker_counts':{k:v for k,v in marker_counts.items() if v},'candidate_routes':rel[:160],'contexts':hits})
 (OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'download_ok':out.get('download_ok'),'contexts':len(out.get('contexts',[])),'candidate_routes':out.get('candidate_routes',[])[:25]}))
if __name__=='__main__':main()
