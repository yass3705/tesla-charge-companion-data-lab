#!/usr/bin/env python3
"""Static-only EVGO loadClusters symbol/co-occurrence probe.

Extracts only safe identifier names and route-like tokens near loadClusters/getLocations/
locationIds map symbols. No backend calls, credentials, raw bundle context, values,
coordinates, or query strings are persisted.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/morocco-evgo-loadclusters-symbols'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
MARKERS=('loadclusters','getlocations','fetchlocations','locationids','location_ids','clusters')
IDENT_RX=re.compile(r'\b[A-Za-z_$][A-Za-z0-9_$]{2,80}\b')
ROUTE_RX=re.compile(r'/(?:api(?:/v\d+)?/)?(?:app|map|maps|location|locations|cluster|clusters)[A-Za-z0-9_./:{}-]{1,140}',re.I)
SAFE_PARTS=('cluster','location','bound','viewport','region','north','south','east','west','zoom','radius','distance','map','marker','evse','station','charger','fetch','load','get','lat','lng')
METHODS=('get','post','put','patch','delete')
BLOCK=re.compile(r'(token|secret|password|authorization|cookie|email|phone|payment|wallet|account|customer|bearer|apikey|api_key)',re.I)

def dl(dest):
    for fmt in ('XAPK','APK'):
        try:
            q=urllib.request.Request(f'https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest',headers={'User-Agent':UA,'Accept':'*/*'})
            with urllib.request.urlopen(q,timeout=120) as r:data=r.read()
            if len(data)>100000: dest.write_bytes(data); return fmt,len(data)
        except Exception: pass
    return None,0

def uz(src,dst):
    dst.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(src) as z:
            for i in z.infolist():
                if '..' not in Path(i.filename).parts and i.file_size<180*1024*1024:z.extract(i,dst)
    except Exception: pass

def strings(p):
    try:return subprocess.run(['strings','-a','-n','2',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
    except Exception:return []

def main():
    rep={'schema_version':1,'package':PACKAGE,'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'raw_package_persisted':False,'raw_bundle_context_persisted':False,'raw_values_persisted':False,'coordinates_persisted':False,'credentials_persisted':False}}
    with tempfile.TemporaryDirectory(prefix='evgo-loadclusters-') as td:
        root=Path(td); pkg=root/'evgo.pkg'; fmt,size=dl(pkg); rep.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
        if not fmt:
            (OUT/'summary.json').write_text(json.dumps(rep,indent=2)+'\n'); return
        tree=root/'tree'; uz(pkg,tree)
        for n,a in enumerate(list(tree.rglob('*.apk'))[:30]): uz(a,tree/f'apk_{n}')
        bundles=[p for p in tree.rglob('*') if p.is_file() and p.name in ('index.android.bundle','main.jsbundle','libapp.so')]
        ids=Counter(); routes=Counter(); methods=Counter(); marker_counts=Counter(); windows=0
        for p in bundles:
            ls=strings(p)
            for i,line in enumerate(ls):
                low=line.lower(); hit=[m for m in MARKERS if m in low]
                if not hit: continue
                windows+=1
                for m in hit: marker_counts[m]+=1
                for j in range(max(0,i-12),min(len(ls),i+13)):
                    s=ls[j]
                    if BLOCK.search(s): continue
                    sl=s.lower()
                    for meth in METHODS:
                        if re.search(rf'\b{meth}\b',sl): methods[meth]+=1
                    for r in ROUTE_RX.findall(s):
                        r=r.split('?',1)[0]
                        if any(k in r.lower() for k in ('cluster','location','map','evse','station','charger')): routes[r]+=1
                    for x in IDENT_RX.findall(s):
                        xl=x.lower()
                        if BLOCK.search(xl): continue
                        if any(part in xl for part in SAFE_PARTS): ids[x]+=1
        rep.update({'bundle_count':len(bundles),'marker_counts':dict(marker_counts.most_common()),'nearby_method_counts':dict(methods.most_common()),'route_candidates':[{'route':r,'count':c} for r,c in routes.most_common(100)],'identifier_candidates':[{'name':n,'count':c} for n,c in ids.most_common(160)],'windows_examined':windows})
    (OUT/'summary.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'download_ok':rep.get('download_ok'),'markers':rep.get('marker_counts'),'methods':rep.get('nearby_method_counts'),'windows':rep.get('windows_examined')}))

if __name__=='__main__': main()
