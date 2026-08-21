#!/usr/bin/env python3
"""Deep static EVGO/AMPECO cluster-service literal probe.

Downloads the public Android package and inspects only static client material. No backend
requests, login, credentials, station IDs or coordinates are used. Persisted output is
limited to safe hostnames, path-like literals, HTTP method words and symbol names near
map/cluster markers; raw bundle text and query values are never stored.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE='ma.evgo.cp.app'
OUT=Path('artifacts/morocco-evgo-cluster-literal-deep'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)'
MARKERS=('loadClusters','fetchCustomPinImagesFromClustersService','getVisibleOperators','fetchLocations','getLocations','locationIds','location_ids','mapMarkers','wrappedPins')
URL_RE=re.compile(r'https?://[^\s\x00"\'<>\\]{5,500}',re.I)
HOST_RE=re.compile(r'(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:ma|com|net|io|app|cloud|dev|tech)(?::\d{2,5})?(?![A-Za-z0-9.-])',re.I)
PATH_RE=re.compile(r'(?<![A-Za-z0-9])/(?:api|app|mobile|map|maps|cluster|clusters|location|locations|operator|operators|pin|pins|evse|evses)[A-Za-z0-9_./{}:-]{0,180}',re.I)
IDENT_RE=re.compile(r'\b[A-Za-z_][A-Za-z0-9_]{2,80}\b')
SENSITIVE=re.compile(r'(password|secret|token|authorization|cookie|email|phone|wallet|invoice|payment|card|account|customer|bearer)',re.I)


def dl(dest:Path):
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


def strings(p:Path):
    try:
        return subprocess.run(['strings','-a','-n','3',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
    except Exception:return []


def clean_url(u:str):
    try:
        q=urlsplit(u)
        if not q.hostname:return None
        return f'{q.scheme}://{q.hostname}{q.path or "/"}'[:400]
    except Exception:return None


def main():
    report={'schema_version':1,'package':PACKAGE,'policy':{'static_analysis_only':True,'backend_requests_made':False,'no_login':True,'no_credentials':True,'no_station_ids':True,'no_coordinates':True,'raw_package_persisted':False,'raw_bundle_persisted':False,'raw_context_persisted':False,'query_values_persisted':False}}
    with tempfile.TemporaryDirectory(prefix='evgo-cluster-deep-') as td:
        root=Path(td); pkg=root/'app.pkg'; fmt,size=dl(pkg); report.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
        if not fmt:
            (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n'); return
        tree=root/'tree'; unzip(pkg,tree)
        for n,a in enumerate(list(tree.rglob('*.apk'))[:30]): unzip(a,tree/f'apk_{n}')
        bundles=[]
        for p in tree.rglob('*'):
            if p.is_file() and p.name in ('index.android.bundle','main.jsbundle'):
                bundles.append(p)
        marker_hits=Counter(); hosts=Counter(); urls=Counter(); paths=Counter(); methods=Counter(); identifiers=Counter()
        for p in bundles:
            lines=strings(p)
            for i,line in enumerate(lines):
                low=line.lower()
                matched=[m for m in MARKERS if m.lower() in low]
                if not matched: continue
                for m in matched: marker_hits[m]+=1
                for j in range(max(0,i-80),min(len(lines),i+81)):
                    s=lines[j].strip()
                    if not s or len(s)>5000 or SENSITIVE.search(s): continue
                    for h in HOST_RE.findall(s): hosts[h.lower()]+=1
                    for u in URL_RE.findall(s):
                        cu=clean_url(u)
                        if cu: urls[cu]+=1
                    for path in PATH_RE.findall(s):
                        if '?' in path:path=path.split('?',1)[0]
                        paths[path[:220]]+=1
                    for meth in ('GET','POST','PUT','PATCH','DELETE'):
                        if re.search(rf'\b{meth}\b',s): methods[meth]+=1
                    for ident in IDENT_RE.findall(s):
                        il=ident.lower()
                        if any(k in il for k in ('cluster','location','operator','visible','marker','pin','map','bounds','viewport','region')):
                            identifiers[ident]+=1
        report.update({'bundle_count':len(bundles),'marker_hits':dict(marker_hits),'candidate_hosts':[{'value':k,'count':v} for k,v in hosts.most_common(60)],'candidate_urls':[{'value':k,'count':v} for k,v in urls.most_common(80)],'candidate_paths':[{'value':k,'count':v} for k,v in paths.most_common(120)],'nearby_http_methods':dict(methods),'nearby_symbol_names':[{'value':k,'count':v} for k,v in identifiers.most_common(120)]})
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'download_ok':report.get('download_ok'),'markers':report.get('marker_hits',{}),'hosts':report.get('candidate_hosts',[])[:10],'paths':report.get('candidate_paths',[])[:15]}))

if __name__=='__main__':main()
