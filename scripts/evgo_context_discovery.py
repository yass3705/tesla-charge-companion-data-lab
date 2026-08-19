#!/usr/bin/env python3
"""Sanitized route-context discovery for Morocco EVGO (ma.evgo.cp.app).

Goal: recover the public client base URL / read-only station route shape around known station
symbols without persisting credentials, query strings, account data or raw application files.
"""
from __future__ import annotations
import json,re,subprocess,tempfile,urllib.request,zipfile
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE='ma.evgo.cp.app'; OUT=Path('artifacts/evgo-context-discovery'); OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.2)'
URL=re.compile(r'https?://[^\s\x00"\'<>\\]{5,400}',re.I)
HOST=re.compile(r'(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:ma|com|io|net|app|cloud|dev|tech)(?::\d{2,5})?(?![A-Za-z0-9.-])',re.I)
SENSITIVE=re.compile(r'(password|secret|token|authorization|cookie|email|phone|wallet|invoice|payment|card|account|customer|bearer)',re.I)
LONG=re.compile(r'\b[A-Za-z0-9_-]{40,}\b')
MARKERS=('places/app/evses/search','evses/search','session:start:pricing','price-fields-formatter','thresholdPriceForEnergyAtDay','chargePointTag','evse-type-ac','evse-type-dc','availability','occupied')


def clean(s):
 s=LONG.sub('[REDACTED]',s); s=re.sub(r'(?i)(bearer\s+)[^\s,;"\']+',r'\1[REDACTED]',s)
 # strip query strings from URLs in arbitrary context
 s=re.sub(r'(https?://[^\s?"\']+)\?[^\s"\']+',r'\1?[REDACTED_QUERY]',s)
 return s[:1200]

def dl(dest):
 for fmt in ('XAPK','APK'):
  try:
   q=urllib.request.Request(f'https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest',headers={'User-Agent':UA,'Accept':'*/*'})
   with urllib.request.urlopen(q,timeout=120) as r:data=r.read()
   if len(data)>100000:dest.write_bytes(data);return fmt,len(data)
  except Exception:pass
 return None,0

def unzip(src,dst):
 dst.mkdir(parents=True,exist_ok=True)
 try:
  with zipfile.ZipFile(src) as z:
   for i in z.infolist():
    if '..' not in Path(i.filename).parts and i.file_size<180*1024*1024:z.extract(i,dst)
 except Exception:pass

def getlines(p):
 try:
  if p.name in ('libapp.so','index.android.bundle','main.jsbundle'):
   return subprocess.run(['strings','-a','-n','2',str(p)],capture_output=True,text=True,errors='replace',timeout=240).stdout.splitlines()
  return p.read_text(errors='replace').splitlines()
 except Exception:return []

def main():
 result={'schema_version':1,'package':PACKAGE,'policy':{'read_only':True,'no_login':True,'raw_package_persisted':False,'raw_credentials_persisted':False,'query_strings_persisted':False}}
 with tempfile.TemporaryDirectory(prefix='evgo-context-') as td:
  root=Path(td);pkg=root/'evgo.pkg';fmt,size=dl(pkg);result.update({'download_ok':bool(fmt),'download_format':fmt,'download_bytes':size})
  if not fmt:(OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return
  tree=root/'tree';unzip(pkg,tree)
  for n,a in enumerate(list(tree.rglob('*.apk'))[:30]):unzip(a,tree/f'apk_{n}')
  ls=[]
  for p in tree.rglob('*'):
   if not p.is_file():continue
   try:sz=p.stat().st_size
   except OSError:continue
   if sz>150*1024*1024:continue
   if p.name in ('libapp.so','index.android.bundle','main.jsbundle','app.config') or p.suffix.lower() in ('.json','.js','.txt','.xml'):
    for x in getlines(p):ls.append((str(p.relative_to(tree)),x))
  hits=[];hosts=[];urls=[]
  for i,(src,line) in enumerate(ls):
   low=line.lower()
   if not any(m.lower() in low for m in MARKERS):continue
   window=[]
   for j in range(max(0,i-18),min(len(ls),i+19)):
    raw=ls[j][1].strip()
    if not raw or len(raw)>2500:continue
    if SENSITIVE.search(raw) and not any(k in raw.lower() for k in ('station','charger','connector','evse','location','price','tariff')):continue
    c=clean(raw);window.append(c)
    for u in URL.findall(raw):
     try:
      q=urlsplit(u); val=f'{q.scheme}://{q.hostname}{q.path or "/"}' if q.hostname else None
     except Exception:val=None
     if val and val not in urls:urls.append(val[:400])
    for h in HOST.findall(raw):
     h=h.lower()
     if h not in hosts:hosts.append(h)
   hits.append({'source':src,'marker':clean(line.strip()),'context':window[:45]})
   if len(hits)>=80:break
  # Base-URL/config symbols often sit away from route names; save only the symbol lines, sanitized.
  config=[]
  for src,line in ls:
   low=line.lower()
   if any(k in low for k in ('baseurl','base_url','apiurl','api_url','axios.create','environment.api','backendurl','apiendpoint','api endpoint')):
    if not SENSITIVE.search(line):config.append({'source':src,'line':clean(line.strip())})
    if len(config)>=100:break
  result.update({'candidate_hosts':hosts[:80],'candidate_urls':urls[:100],'route_contexts':hits,'config_signals':config})
 (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'download_ok':result.get('download_ok'),'contexts':len(result.get('route_contexts',[])),'hosts':result.get('candidate_hosts',[])[:12],'urls':result.get('candidate_urls',[])[:12]}))
if __name__=='__main__':main()
