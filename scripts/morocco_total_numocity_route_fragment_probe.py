#!/usr/bin/env python3
"""Static-only route-fragment probe for TotalEnergies Morocco / Numocity client.

Finds route-like path tokens near qr-connector/get-connector-status/connector-status
without calling the backend or persisting raw bundle context, credentials, values,
QR codes, coordinates, or query strings.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path

PACKAGE='com.namp.totalev'; OUT=Path('artifacts/morocco-total-numocity-route-fragments'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
MARKERS=('qr-connector','get-connector-status','connector-status')
PATH_RX=re.compile(r'/(?:[A-Za-z0-9_.:{}-]+/){0,8}(?:qr-connector|get-connector-status|connector-status)(?:/[A-Za-z0-9_.:{}-]+){0,4}',re.I)
PREFIX_RX=re.compile(r'/(?:api|app|mobile|v\d+)(?:/[A-Za-z0-9_.:{}-]+){0,6}',re.I)
IDENT_RX=re.compile(r'\b[A-Za-z_$][A-Za-z0-9_$]{2,64}\b')
SAFE_PARTS=('qr','connector','station','status','location','lat','lng','latitude','longitude','stationid','connectorid','qrcode')
BLOCK=re.compile(r'(token|secret|password|authorization|cookie|email|phone|payment|wallet|account|customer|bearer|apikey|api_key)',re.I)

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
                if '..' not in Path(i.filename).parts and i.file_size<120*1024*1024:z.extract(i,dst)
    except Exception:pass

def slines(p):
    try:return subprocess.run(['strings','-a','-n','2',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
    except Exception:return []

def main():
    rep={'schema_version':1,'package':PACKAGE,'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'raw_package_persisted':False,'raw_bundle_context_persisted':False,'raw_values_persisted':False,'credentials_persisted':False}}
    with tempfile.TemporaryDirectory(prefix='total-numocity-frag-') as td:
        root=Path(td);pkg=root/'app.pkg';fmt,size=dl(pkg);rep.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
        if not fmt:(OUT/'summary.json').write_text(json.dumps(rep,indent=2)+'\n');return
        tree=root/'tree';uz(pkg,tree)
        for n,a in enumerate(list(tree.rglob('*.apk'))[:30]):uz(a,tree/f'apk_{n}')
        paths=Counter(); prefixes=Counter(); idents=Counter(); marker_counts=Counter(); windows=0
        for p in [x for x in tree.rglob('*') if x.is_file() and x.name in ('index.android.bundle','main.jsbundle','libapp.so')]:
            ls=slines(p)
            for i,line in enumerate(ls):
                low=line.lower(); ms=[m for m in MARKERS if m in low]
                if not ms:continue
                windows+=1
                for m in ms:marker_counts[m]+=1
                for j in range(max(0,i-10),min(len(ls),i+11)):
                    s=ls[j]
                    if BLOCK.search(s):continue
                    for x in PATH_RX.findall(s):paths[x.split('?',1)[0]]+=1
                    for x in PREFIX_RX.findall(s):
                        if any(k in x.lower() for k in ('api','app','mobile','connector','station')):prefixes[x.split('?',1)[0]]+=1
                    for ident in IDENT_RX.findall(s):
                        il=ident.lower()
                        if BLOCK.search(il):continue
                        if any(k in il for k in SAFE_PARTS):idents[ident]+=1
        rep.update({'marker_counts':dict(marker_counts),'exact_route_fragments':[{'path':x,'count':c} for x,c in paths.most_common(80)],'prefix_candidates':[{'path':x,'count':c} for x,c in prefixes.most_common(100)],'identifier_candidates':[{'name':x,'count':c} for x,c in idents.most_common(100)],'windows_examined':windows})
    (OUT/'summary.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'download_ok':rep.get('download_ok'),'fragments':len(rep.get('exact_route_fragments',[])),'prefixes':len(rep.get('prefix_candidates',[])),'windows':rep.get('windows_examined')}))

if __name__=='__main__':main()
