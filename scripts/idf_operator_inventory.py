#!/usr/bin/env python3
"""Build a small sanitized inventory of operator labels present in TCC IDF data.

Read-only against the public release branch of Tesla Charge Companion. The output
contains aggregate counts and a few public station witnesses only; no secrets,
credentials or user data are read.
"""
from __future__ import annotations
import argparse, json, re, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE='https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/release/2026-08/data/'
FILES=('tesla_stations.json','custom_stations.json')
UA='Mozilla/5.0 TCC-IDF-operator-audit/1.0'

KNOWN=('SIGEIF','Belib','Metropolis','Métropolis','La Borne Bleue','SIPPEREC','Ecocharge77','SEY','Ma Borne','SMOYS','VOLTi','SIE-ELY','SIEELY')
IDF_DEPTS=('75','77','78','91','92','93','94','95')
IDF_TERMS=(
 'paris','seine-et-marne','seine et marne','yvelines','essonne','hauts-de-seine','hauts de seine',
 'seine-saint-denis','seine saint denis','val-de-marne','val de marne','val-d’oise','val-d\'oise','val d’oise','val d\'oise'
)

def fetch_json(name):
    req=urllib.request.Request(BASE+name,headers={'User-Agent':UA,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=90) as r:
        if getattr(r,'status',200)!=200: raise RuntimeError(f'{name}: HTTP {r.status}')
        return json.load(r)

def walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values(): yield from walk(v)
    elif isinstance(obj,list):
        for v in obj: yield from walk(v)

def pick(d,*keys):
    for k in keys:
        v=d.get(k)
        if v not in (None,''): return v
    return None

def as_float(v):
    try: return float(v)
    except Exception: return None

def postcode_from(text):
    m=re.search(r'\b(75|77|78|91|92|93|94|95)\d{3}\b', text or '')
    return m.group(0) if m else None

def is_idf(d):
    text=' '.join(str(pick(d,k) or '') for k in ('address','adresse','city','ville','region','department','departement','name','nom')).lower()
    pc=postcode_from(text)
    if pc and pc[:2] in IDF_DEPTS: return True
    if any(t in text for t in IDF_TERMS): return True
    lat=as_float(pick(d,'latitude','lat')); lon=as_float(pick(d,'longitude','lng','lon'))
    # Conservative geographic envelope; only used when a record has no textual IDF clue.
    return lat is not None and lon is not None and 48.10 <= lat <= 49.25 and 1.35 <= lon <= 3.65

def normalize_operator(d):
    raw=pick(d,'operator','operateur','operatorName','cpo','network','reseau','provider')
    if isinstance(raw,dict): raw=pick(raw,'name','label','title')
    return str(raw).strip() if raw not in (None,'') else ''

def station_like(d):
    return any(k in d for k in ('latitude','lat')) and any(k in d for k in ('longitude','lng','lon')) and any(k in d for k in ('name','nom','address','adresse'))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); args=ap.parse_args()
    counts=Counter(); samples=defaultdict(list); source_counts=Counter(); seen=set()
    for fn in FILES:
        data=fetch_json(fn)
        for d in walk(data):
            if not station_like(d) or not is_idf(d): continue
            op=normalize_operator(d)
            if not op: continue
            name=str(pick(d,'name','nom') or '').strip(); addr=str(pick(d,'address','adresse') or '').strip()
            lat=as_float(pick(d,'latitude','lat')); lon=as_float(pick(d,'longitude','lng','lon'))
            key=(op,name,addr,round(lat,5) if lat is not None else None,round(lon,5) if lon is not None else None)
            if key in seen: continue
            seen.add(key); counts[op]+=1; source_counts[fn]+=1
            if len(samples[op])<3:
                samples[op].append({'name':name[:140],'address':addr[:180],'latitude':lat,'longitude':lon,'source':fn})
    known=[]; unresolved=[]
    for op,n in counts.most_common():
        row={'operator':op,'stationRecords':n,'samples':samples[op]}
        (known if any(k.lower() in op.lower() for k in KNOWN) else unresolved).append(row)
    payload={
      'schemaVersion':'1.0.0','dataset':'idf-operator-inventory','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
      'source':{'repository':'yass3705/tesla-charge-companion-stable','branch':'release/2026-08','files':list(FILES),'readOnly':True},
      'method':{'idfDepartments':list(IDF_DEPTS),'textOrConservativeCoordinateMatch':True,'notATariffValidation':True},
      'summary':{'operatorLabels':len(counts),'stationRecords':sum(counts.values()),'sourceRecords':dict(source_counts),'knownRegionalLabels':len(known),'unresolvedLabels':len(unresolved)},
      'knownRegional':known,'unresolved':unresolved
    }
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__': main()
