#!/usr/bin/env python3
"""Static-only EVGO map-discovery symbol probe.

Extracts only route-like tokens and identifier/key names around public map/location
markers from the Android client. It never calls EVGO/AMPECO backends and never
persists raw bundle context, credentials, values, coordinates, or query strings.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/morocco-evgo-map-symbols'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
MARKERS=('locationids','location_ids','getlocations','fetchlocations','bounds','bounding','northeast','southwest','viewport','region','cluster','clusters','mapmarkers','map markers')
ROUTE_RX=re.compile(r'/(?:api(?:/v\d+)?/)?app/[A-Za-z0-9_./:{}-]{2,120}',re.I)
IDENT_RX=re.compile(r'\b[A-Za-z_$][A-Za-z0-9_$]{2,64}\b')
SAFE_IDENT_PARTS=('location','bound','north','south','east','west','viewport','region','cluster','map','marker','zoom','latitude','longitude','lat','lng','evse','charger','station','radius','distance')
BLOCK_RX=re.compile(r'(token|secret|password|authorization|cookie|email|phone|payment|wallet|account|customer|bearer|apikey|api_key)',re.I)

def download(dest:Path):
    for fmt in ('XAPK','APK'):
        try:
            req=urllib.request.Request(f'https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest',headers={'User-Agent':UA,'Accept':'*/*'})
            with urllib.request.urlopen(req,timeout=120) as r:data=r.read()
            if len(data)>100000: dest.write_bytes(data); return fmt,len(data)
        except Exception: pass
    return None,0

def unzip(src:Path,dst:Path):
    dst.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(src) as z:
            for i in z.infolist():
                if '..' not in Path(i.filename).parts and i.file_size<180*1024*1024:z.extract(i,dst)
    except Exception: pass

def strings(path:Path):
    try:return subprocess.run(['strings','-a','-n','2',str(path)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
    except Exception:return []

def main():
    report={'schema_version':1,'package':PACKAGE,'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'raw_package_persisted':False,'raw_bundle_context_persisted':False,'raw_values_persisted':False,'credentials_persisted':False}}
    with tempfile.TemporaryDirectory(prefix='evgo-map-symbols-') as td:
        root=Path(td); pkg=root/'evgo.pkg'; fmt,size=download(pkg); report.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
        if not fmt:
            (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n'); return
        tree=root/'tree'; unzip(pkg,tree)
        for n,a in enumerate(list(tree.rglob('*.apk'))[:30]): unzip(a,tree/f'apk_{n}')
        bundles=[p for p in tree.rglob('*') if p.is_file() and p.name in ('index.android.bundle','main.jsbundle','libapp.so')]
        route_counts=Counter(); ident_counts=Counter(); marker_counts=Counter(); windows=0
        for p in bundles:
            ls=strings(p)
            for i,line in enumerate(ls):
                low=line.lower(); matched=[m for m in MARKERS if m in low]
                if not matched: continue
                windows+=1
                for m in matched: marker_counts[m]+=1
                for j in range(max(0,i-8),min(len(ls),i+9)):
                    s=ls[j]
                    if BLOCK_RX.search(s): continue
                    for r in ROUTE_RX.findall(s):
                        # Strip any accidental query string and keep only map/location/EVSE-oriented routes.
                        r=r.split('?',1)[0]
                        if any(k in r.lower() for k in ('location','evse','map','cluster','station','charger')): route_counts[r]+=1
                    for ident in IDENT_RX.findall(s):
                        il=ident.lower()
                        if BLOCK_RX.search(il): continue
                        if any(part in il for part in SAFE_IDENT_PARTS): ident_counts[ident]+=1
        report.update({'bundle_count':len(bundles),'marker_counts':dict(marker_counts.most_common()),'route_candidates':[{'route':r,'count':c} for r,c in route_counts.most_common(80)],'identifier_candidates':[{'name':n,'count':c} for n,c in ident_counts.most_common(120)],'windows_examined':windows})
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'download_ok':report.get('download_ok'),'routes':len(report.get('route_candidates',[])),'idents':len(report.get('identifier_candidates',[])),'windows':report.get('windows_examined')}))

if __name__=='__main__': main()
