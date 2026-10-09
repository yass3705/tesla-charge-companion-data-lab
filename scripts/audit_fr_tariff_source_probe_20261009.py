#!/usr/bin/env python3
import pathlib,json,gzip,collections,re
R=pathlib.Path(__file__).resolve().parents[1]
dirs=['data/operator_direct','data/national','data/publish','v9-production-runtime/data/v9']
focus=('tariff','direct','price','offer','electra','electroverse','chargepoint','ionity','izivia','driveco','powerdot','atlante','lidl','fastned','station','belib','freshmile','bump','e55c','etotem')
def walk(o,p='',depth=0):
 if depth>7:return
 if isinstance(o,list):
  if o and isinstance(o[0],dict):
   d=o[0];names=list(d.keys())
   if any('evse' in x.lower() or 'pdc' in x.lower() or 'price' in x.lower() or 'tariff' in x.lower() for x in names):yield (p+'[]',len(o),names[:20],str(d)[:350])
  for t in o[:1]:yield from walk(t,p+'[]',depth+1)
 if isinstance(o,dict):
  for k,v in o.items():
   if isinstance(v,(list,dict)) and (len(v) if hasattr(v,'__len__') else 0):
    yield from walk(v,p+'/'+k,depth+1)
def samplefiles(files):
 for f in files:
  try:
   if f.stat().st_size>25_000_000:continue
   with (gzip.open(f,'rt',encoding='utf-8') if str(f).endswith('.gz') else f.open('rt',encoding='utf-8')) as fd:data=json.load(fd)
   if not isinstance(data,dict):continue
   samples=list(walk(data))
   keys=list(data.keys())
   priced=any('price' in str(x).lower() or 'tariff' in str(x).lower() for x in keys)
   if samples or priced:
    value={'file':str(f.relative_to(R)),'bytes':f.stat().st_size,'topKeys':keys[:16],'report':samples[:4]}
    print('CPO_SOURCE_PROBE='+json.dumps(value,ensure_ascii=False,separators=(',',':')))
  except Exception as e:
   print('CPO_PROBE_ERROR='+json.dumps({'path':str(f.relative_to(R)),'error':str(e)[:100]}))
for root in dirs:
 p=R/root
 files=sorted(f for f in p.glob('*') if f.is_file() and f.suffix in ('.json','.gz') and (root=='data/operator_direct' or root=='data/publish' or any(x in f.name.lower() for x in focus)))
 samplefiles(files)
