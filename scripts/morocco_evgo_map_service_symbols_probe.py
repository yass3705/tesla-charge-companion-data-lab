#!/usr/bin/env python3
"""Static-only focused probe for EVGO map/cluster service configuration symbols.

Searches the public Android bundle for map-service identifiers discovered by prior probes
and correlates them with safe host/path/config names. No network call to EVGO/AMPECO,
no credentials, coordinates, query values, or raw bundle context are persisted.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/morocco-evgo-map-service-symbols'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
MARKERS=(
 'fetchCustomPinImagesFromClustersService','loadClusters','ClusterMarker','wrappedPins',
 'getVisibleOperators','RNMapsUrlTile','AnyPointFeature','locationIds','location_ids',
 'fetchLocations','getLocations','clustering','mapMarkers','map markers'
)
BLOCK=re.compile(r'(token|secret|password|authorization|cookie|email|phone|payment|wallet|account|customer|bearer|apikey|api_key)',re.I)
HOST=re.compile(r'(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:com|ma|io|net|app|cloud|dev|tech|org)(?::\d{2,5})?(?![A-Za-z0-9.-])',re.I)
URL=re.compile(r'https?://[^\s\x00\"\'<>\\]{5,500}',re.I)
PATH=re.compile(r'/(?:api(?:/v\d+)?/)?[A-Za-z0-9_.:-]*(?:cluster|location|map|marker|pin|tile|operator|evse|station|charger)[A-Za-z0-9_./:{}-]{0,180}',re.I)
IDENT=re.compile(r'\b[A-Za-z_$][A-Za-z0-9_$]{2,100}\b')
SAFE_PARTS=('cluster','location','map','marker','pin','tile','operator','visible','feature','evse','station','charger','service','endpoint','host','url','base','fetch','load','region','bound','viewport')

def dl(dest):
 for fmt in ('XAPK','APK'):
  try:
   req=urllib.request.Request(f'https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest',headers={'User-Agent':UA,'Accept':'*/*'})
   with urllib.request.urlopen(req,timeout=120) as r:data=r.read()
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

def rows(p):
 try:lines=subprocess.run(['strings','-a','-t','d','-n','3',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
 except Exception:return []
 out=[]
 for line in lines:
  m=re.match(r'^\s*(\d+)\s+(.*)$',line)
  if m:out.append((int(m.group(1)),m.group(2)))
 return out

def safe_url(raw):
 try:
  u=urlsplit(raw)
  if not u.hostname:return None
  return f'{u.scheme}://{u.hostname}{u.path or "/"}'[:500]
 except Exception:return None

def main():
 rep={'schema_version':1,'package':PACKAGE,'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'credentials_persisted':False,'coordinates_persisted':False,'query_values_persisted':False,'raw_package_persisted':False,'raw_bundle_context_persisted':False}}
 with tempfile.TemporaryDirectory(prefix='evgo-map-symbols-') as td:
  root=Path(td);pkg=root/'evgo.pkg';fmt,size=dl(pkg);rep.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
  if not fmt:(OUT/'summary.json').write_text(json.dumps(rep,indent=2)+'\n');return
  tree=root/'tree';uz(pkg,tree)
  for n,a in enumerate(list(tree.rglob('*.apk'))[:30]):uz(a,tree/f'apk_{n}')
  bundles=[p for p in tree.rglob('*') if p.is_file() and p.name in ('index.android.bundle','main.jsbundle','libapp.so')]
  hits=[];hosts=Counter();urls=Counter();paths=Counter();idents=Counter();nearest=[]
  for b in bundles:
   rr=rows(b)
   marker_rows=[]
   for off,text in rr:
    for m in MARKERS:
     if m.lower() in text.lower():marker_rows.append((off,m));hits.append({'marker':m,'source':str(b.relative_to(tree)),'offset':off})
   for off,m in marker_rows:
    for o,text in rr:
     d=abs(o-off)
     if d>160000 or BLOCK.search(text):continue
     for h in HOST.findall(text):
      hl=h.lower()
      if any(x in hl for x in ('evgo','ampeco','map','cluster','charge')):
       hosts[hl]+=1; nearest.append({'marker':m,'kind':'host','distance_bytes':d,'value':hl})
     for raw in URL.findall(text):
      u=safe_url(raw.rstrip('.,;:)]}'))
      if u and any(x in u.lower() for x in ('evgo','ampeco','map','cluster','charge','tile')):
       urls[u]+=1;nearest.append({'marker':m,'kind':'url','distance_bytes':d,'value':u})
     if any(x in text.lower() for x in SAFE_PARTS):
      for p in PATH.findall(text):
       p=p.split('?',1)[0]
       if not BLOCK.search(p):paths[p]+=1;nearest.append({'marker':m,'kind':'path','distance_bytes':d,'value':p})
      for ident in IDENT.findall(text):
       il=ident.lower()
       if not BLOCK.search(il) and any(x in il for x in SAFE_PARTS):
        idents[ident]+=1
        if d<=20000:nearest.append({'marker':m,'kind':'identifier','distance_bytes':d,'value':ident})
  seen=set();items=[]
  for x in sorted(nearest,key=lambda x:(x['distance_bytes'],x['kind'],x['value'])):
   k=(x['marker'],x['kind'],x['value'])
   if k in seen:continue
   seen.add(k);items.append(x)
   if len(items)>=300:break
  rep.update({'bundle_count':len(bundles),'marker_hits':hits[:100],'candidate_hosts':[{'host':k,'count':v} for k,v in hosts.most_common(100)],'candidate_urls':[{'url':k,'count':v} for k,v in urls.most_common(100)],'candidate_paths':[{'path':k,'count':v} for k,v in paths.most_common(140)],'safe_identifiers':[{'name':k,'count':v} for k,v in idents.most_common(180)],'nearest_structural_tokens':items})
 (OUT/'summary.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'markers':len(rep.get('marker_hits',[])),'hosts':rep.get('candidate_hosts',[])[:10],'paths':rep.get('candidate_paths',[])[:10]}))
if __name__=='__main__':main()
