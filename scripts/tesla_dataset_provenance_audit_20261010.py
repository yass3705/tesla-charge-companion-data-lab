#!/usr/bin/env python3
"""TCC Tesla SOURCE PROVENANCE audit: canonical Mac file vs V9 shell copy.
Read-only, no tariff changes. Prices and source-observation timestamps must not
be conflated with latest Git commit timestamps.
"""
from __future__ import annotations
import collections
import datetime as dt
import hashlib
import json
import pathlib
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/tesla'
REMOTE='https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable'
SOURCES={
 'mac_canonical_main':'main/data/tesla_stations.json',
 'v9_production_snapshot':'main/v9-production-runtime/data/tesla_stations.json',
 'v9_test_snapshot':'main/v9-test/data/tesla_stations.json',
 'before_october_update':'b2eeeeeee90563a34d8314ee779ac22bc21ac5ec/data/tesla_stations.json',
}
COUNTRIES=['FR','IT','CH','DE','ES','NL','GB','MA','BE']
def download(suffix):
    with urllib.request.urlopen(urllib.request.Request(REMOTE+'/'+suffix,headers={
        'User-Agent':'TCC-Tesla-Provenance-20261010/1.0'}),timeout=100) as f:
        raw=f.read(20_000_001)
    if len(raw)>20_000_000:raise ValueError('oversize catalogue')
    data=json.loads(raw)
    if not isinstance(data,list) or len(data)<100:raise ValueError('invalid station array: '+suffix)
    return data,hashlib.sha256(raw).hexdigest(),len(raw)
def iso_day(v):
    try:return str(v)[:10] if dt.date.fromisoformat(str(v)[:10]) else None
    except (TypeError,ValueError):return None
def mode(v):
    if not v:return 'missing'
    d=iso_day(v)
    if d is None:return 'invalid_date'
    age=(dt.date.today()-dt.date.fromisoformat(d)).days
    if age<0:return 'future'
    if age<10:return 'lt10d'
    if age<30:return '10to29d'
    return '30d_plus'
def price_signature(st):
    obj={
      'pricing':st.get('pricing'),
      'chargingConfigurations':[{'id':c.get('id'),'powerKw':c.get('powerKw'),'pricing':c.get('pricing')}
                               for c in (st.get('chargingConfigurations') or [])]
    }
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def breakdown(data):
    stats=collections.defaultdict(lambda:{'stations':0,'lastUpdated':collections.Counter(),
      'sourceObservedAt':collections.Counter(),'sourceObservedAtRawDates':collections.Counter(),
      'lastUpdatedRawDates':collections.Counter(),'presentTimestampFields':collections.Counter(),
      'latestSourceObs':None,'latestLastUpdated':None,'pricingSignatureSha':None})
    for x in data:
        cc=x.get('countryCode') or 'UNKNOWN'
        d=stats[cc]
        d['stations']+=1
        for k in ['lastUpdated','sourceObservedAt']:
            val=x.get(k)
            d[k][mode(val)]+=1
            if (date:=iso_day(val)):
                d[k+'RawDates'][date]+=1
                latest='latestLastUpdated' if k=='lastUpdated' else 'latestSourceObs'
                if not d[latest] or date>d[latest]:d[latest]=date
        for k,v in x.items():
            if any(t in k.lower() for t in ('date','updated','observed','checked','captured','generated','collected','refreshed','sourceat')):
                d['presentTimestampFields'][k]+=1
    return {c:{**d,'lastUpdated':dict(d['lastUpdated']),
        'sourceObservedAt':dict(d['sourceObservedAt']),
        'lastUpdatedTopDates':d['lastUpdatedRawDates'].most_common(8),
        'sourceObservedAtTopDates':d['sourceObservedAtRawDates'].most_common(8),
        'presentTimestampFields':dict(d['presentTimestampFields'])
        } for c,d in sorted(stats.items())}
def by_id(arr):return {x['id']:x for x in arr if isinstance(x,dict) and x.get('id')}
def delta(a,b):
    old,new=by_id(a),by_id(b)
    ids=set(old)&set(new)
    country=collections.defaultdict(lambda:collections.Counter())
    samples=collections.defaultdict(list)
    for i in ids:
        x,y=old[i],new[i];cc=y.get('countryCode','?')
        country[cc]['same_station_ids']+=1
        if price_signature(x)!=price_signature(y):
            country[cc]['pricing_changed']+=1
            if len(samples[cc])<6:samples[cc].append({'id':i,'oldLastUpdated':x.get('lastUpdated'),
              'newLastUpdated':y.get('lastUpdated'),'oldSourceObservedAt':x.get('sourceObservedAt'),
              'newSourceObservedAt':y.get('sourceObservedAt')})
        if x.get('lastUpdated')!=y.get('lastUpdated'):country[cc]['lastUpdated_changed']+=1
        if x.get('sourceObservedAt')!=y.get('sourceObservedAt'):country[cc]['sourceObservedAt_changed']+=1
        if x!=y:country[cc]['any_station_fields_changed']+=1
    for i in set(new)-set(old):country[new[i].get('countryCode','?')]['new_stations']+=1
    for i in set(old)-set(new):country[old[i].get('countryCode','?')]['deleted_stations']+=1
    return {'countries':{c:dict(v) for c,v in sorted(country.items())},'examples':dict(samples)}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data={}
    source={}
    for name,p in SOURCES.items():
        a,sha,size=download(p)
        data[name]=a
        source[name]={'refPath':p,'sha256':sha,'bytes':size,'stations':len(a),
                      'countries':breakdown(a)}
    current=data['mac_canonical_main']
    mirror=data['v9_production_snapshot']
    old=data['before_october_update']
    compare={
        'mac_vs_v9_production':delta(mirror,current),
        'before_october_vs_current_mac':delta(old,current),
        'v9_test_vs_v9_production_identical_bytes':
          source['v9_test_snapshot']['sha256']==source['v9_production_snapshot']['sha256']
    }
    try:
        with urllib.request.urlopen(urllib.request.Request(
            REMOTE+'/main/v9-production-shell/shell-config.json',headers={'User-Agent':'TCC-Provenance'}),
            timeout=20) as f: shell=json.load(f)
        with urllib.request.urlopen(urllib.request.Request(
            REMOTE+'/main/v9-production-runtime/data/v9/source-registry.json',
            headers={'User-Agent':'TCC-Provenance'}),timeout=20) as f:registry=json.load(f)
        tesla_source=[s for s in registry.get('sources',[]) if s.get('id')=='tesla-global']
    except Exception as e:
        raise RuntimeError('Unable to establish real V9 Tesla path') from e
    active=shell.get('runtimeBase') or '?'
    reference=tesla_source[0]['path'] if len(tesla_source)==1 else None
    if reference!='data/tesla_stations.json' or active!='v9-production-runtime':
        raise SystemExit('V9 shell/registry path changed; must review routing manually')
    report={
        'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope':'publication-vs-observation-vs-V9-loaded-copy',
        'sources':source,
        'comparisons':compare,
        'actualV9':{'shellRuntimeBase':active,'teslaSourceRegistryPath':reference,
             'effectiveRepositoryPath':active+'/'+reference,
             'matchesMacCanonicalSource':source['mac_canonical_main']['sha256']==source['v9_production_snapshot']['sha256'],
             'sourceRef':'main'},
        'notes':[
            'GitHub publication date is NOT Tesla charge price observation date.',
            'Mac batch commits after 2026-10-07 are independently documented in Git history.',
            'Canonical Mac country updates can change price while keeping older lastUpdated fields.',
            'Current V9 shell loads v9-production-runtime/data/tesla_stations.json, not root data/tesla_stations.json.',
            'Do not automatically prefer SuC solely because a misleading old station lastUpdated field remains.',
            'Morocco must always use Mac: no substitution by SuC.'],
    }
    path=OUT/'tesla-dataset-provenance-audit-latest.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('TESLA_DATASET_PROVENANCE='+json.dumps({
        'sourceCounts':{k:{'stations':v['stations'],'sha256':v['sha256']} for k,v in source.items()},
        'current_vs_v9':compare['mac_vs_v9_production']['countries'],
        'before_october_vs_current':compare['before_october_vs_current_mac']['countries'],
        'v9MatchesMac':report['actualV9']['matchesMacCanonicalSource'],
        'currentTopDates':{c:{'lastUpdated':v['lastUpdatedTopDates'][:3],
                              'sourceObservedAt':v['sourceObservedAtTopDates'][:3]}
                           for c,v in source['mac_canonical_main']['countries'].items()}
    },ensure_ascii=False))
if __name__=='__main__':main()
