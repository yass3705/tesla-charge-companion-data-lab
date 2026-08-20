#!/usr/bin/env python3
"""Static-only byte-offset probe around EVGO map/cluster symbols.

Uses GNU strings offsets to correlate loadClusters/fetchLocations/locationIds with nearby
safe route-like tokens and map parameter identifiers. No backend calls, credentials,
raw bundle contents, coordinates, query values, or sensitive values are persisted.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/morocco-evgo-loadclusters-offset'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
MARKERS=('loadClusters','fetchLocations','getLocations','locationIds','location_ids','fetchCustomPinImagesFromClustersService')
SAFE_PARTS=('cluster','location','bound','viewport','region','north','south','east','west','zoom','radius','distance','map','marker','evse','station','charger','fetch','load','lat','lng')
BLOCK=re.compile(r'(token|secret|password|authorization|cookie|email|phone|payment|wallet|account|customer|bearer|apikey|api_key)',re.I)
ROUTE=re.compile(r'/(?:api(?:/v\d+)?/)?(?:app|map|maps|location|locations|cluster|clusters|evse|evses)[A-Za-z0-9_./:{}-]{1,160}',re.I)
IDENT=re.compile(r'\b[A-Za-z_$][A-Za-z0-9_$]{2,80}\b')


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

def offset_strings(p):
    try:
        out=subprocess.run(['strings','-a','-t','d','-n','3',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
    except Exception:return []
    rows=[]
    for line in out:
        m=re.match(r'^\s*(\d+)\s+(.*)$',line)
        if m: rows.append((int(m.group(1)),m.group(2)))
    return rows

def main():
    rep={'schema_version':1,'package':PACKAGE,'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'raw_package_persisted':False,'raw_bundle_context_persisted':False,'raw_values_persisted':False,'coordinates_persisted':False,'credentials_persisted':False}}
    with tempfile.TemporaryDirectory(prefix='evgo-offset-') as td:
        root=Path(td); pkg=root/'evgo.pkg'; fmt,size=dl(pkg); rep.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
        if not fmt:
            (OUT/'summary.json').write_text(json.dumps(rep,indent=2)+'\n'); return
        tree=root/'tree'; uz(pkg,tree)
        for n,a in enumerate(list(tree.rglob('*.apk'))[:30]): uz(a,tree/f'apk_{n}')
        bundles=[p for p in tree.rglob('*') if p.is_file() and p.name in ('index.android.bundle','main.jsbundle','libapp.so')]
        marker_hits=[]; routes=Counter(); ids=Counter(); distances=[]
        for p in bundles:
            rows=offset_strings(p)
            hits=[(off,s,m) for off,s in rows for m in MARKERS if m.lower() in s.lower()]
            for off,s,m in hits:
                marker_hits.append({'marker':m,'source':str(p.relative_to(tree)),'offset':off})
                nearby=[(o,t) for o,t in rows if abs(o-off)<=12000]
                for o,t in nearby:
                    if BLOCK.search(t): continue
                    for r in ROUTE.findall(t):
                        rr=r.split('?',1)[0]
                        if any(k in rr.lower() for k in ('cluster','location','map','evse','station','charger')):
                            routes[rr]+=1; distances.append({'marker':m,'kind':'route','distance_bytes':abs(o-off),'value':rr})
                    for x in IDENT.findall(t):
                        xl=x.lower()
                        if BLOCK.search(xl): continue
                        if any(part in xl for part in SAFE_PARTS):
                            ids[x]+=1
                            if abs(o-off)<=2500: distances.append({'marker':m,'kind':'identifier','distance_bytes':abs(o-off),'value':x})
        # Keep only structural offsets/distances and safe names, never raw neighboring text.
        distances=sorted(distances,key=lambda x:(x['distance_bytes'],x['kind'],x['value']))[:200]
        rep.update({'bundle_count':len(bundles),'marker_hits':marker_hits[:50],'route_candidates':[{'route':r,'count':c} for r,c in routes.most_common(80)],'identifier_candidates':[{'name':n,'count':c} for n,c in ids.most_common(160)],'nearest_safe_tokens':distances})
    (OUT/'summary.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'download_ok':rep.get('download_ok'),'markers':len(rep.get('marker_hits',[])),'routes':len(rep.get('route_candidates',[])),'nearest':rep.get('nearest_safe_tokens',[])[:12]}))

if __name__=='__main__': main()
