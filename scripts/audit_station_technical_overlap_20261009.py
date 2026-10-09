#!/usr/bin/env python3
"""Station-level GPS + EVSE count + power refinement (read-only audit).

Strict identity matches (alphanumeric-normalized EVSE IDs) are never removed
because of technical differences. GPS-only unmatched locations gain a
station-candidate only if station EVSE/PdC counts and charging powers both
agree. Each candidate must be UNIQUE within the radius after filtering.
Results are COUNTS OF UNIQUE IRVE STATIONS (not EVSEs or physical pedestals).
"""
import collections
import datetime
import gzip
import json
import math
import pathlib
import re

ROOT=pathlib.Path(__file__).resolve().parents[1]
RADII=(5,10,15)
CELL=.002

def load(p):
    p=ROOT/p
    if str(p).endswith('.gz'):
        with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
    return json.loads(p.read_text(encoding='utf-8'))
def norm(v):return re.sub('[^A-Z0-9]','',str(v or '').strip().upper())
def num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) and x>0 else None
    except (ValueError,TypeError):return None
def gps(a,b):
    try:
        a=float(a);b=float(b)
        return (a,b) if math.isfinite(a) and math.isfinite(b) and -90<=a<=90 and -180<=b<=180 else None
    except (ValueError,TypeError):return None
def distance(a,b):
    p1,l1=a;p2,l2=b
    dlat=math.radians(p2-p1);dlon=math.radians(l2-l1)
    q=math.sin(dlat/2)**2+math.cos(math.radians(p1))*math.cos(math.radians(p2))*math.sin(dlon/2)**2
    return 12742000*math.asin(min(1,math.sqrt(q)))
def matchkw(a,b):
    return a is not None and b is not None and abs(a-b)<=max(2.0, .10*max(a,b))
def signature_match(aa,bb):
    return (bool(aa) and len(aa)==len(bb) and
            all(matchkw(a,b) for a,b in zip(sorted(aa),sorted(bb))))
def cpo_names(names):
    return {norm(v) for v in names if len(norm(v))>=5}
def sources_count(evses,kind):
    ids=[]
    for i,evse in enumerate(evses):
        if kind=='electra':k=str(evse.get('id') or norm(evse.get('evseId')) or i)
        else:k=str(evse.get('pk') or norm(evse.get('physicalReference')) or i)
        ids.append(k)
    return len(set(ids))

national=load('data/national/france-irve-static-v9/all.json.gz')
pdc_owners=collections.defaultdict(set)
irve={}
grid=collections.defaultdict(list)
for row in national:
    sid=str(row[0]);cfgs=row[8] or []
    evse_pow=collections.defaultdict(list)
    for cfg in cfgs:
        kwh=num(cfg[3] if len(cfg)>3 else None)
        ids=cfg[6] if len(cfg)>6 and isinstance(cfg[6],list) else []
        for x in ids:
            k=norm(x)
            if k:
                pdc_owners[k].add(sid)
                if kwh:evse_pow[k].append(kwh)
                else:evse_pow[k]
    irve_powers=[max(powers) if powers else None for powers in evse_pow.values()]
    ll=gps(row[3],row[4])
    irve[sid]={
        'll':ll,
        'count':len(evse_pow),
        'powerMax':max((x for x in irve_powers if x),default=None),
        'powerList':irve_powers,
        'name':str(row[1]),
        'address':str(row[2]),
        'companies':cpo_names([row[5],row[11] if len(row)>11 else None])
    }
    if ll:grid[(math.floor(ll[0]/CELL),math.floor(ll[1]/CELL))].append(sid)
pdc_unique={k:next(iter(v)) for k,v in pdc_owners.items() if len(v)==1}

def neighborhood(ll,r):
    if ll is None:return []
    la,lo=ll
    ia,ib=math.floor(la/CELL),math.floor(lo/CELL)
    span_lat=max(1,math.ceil(r/(111195*CELL)))
    span_lon=max(1,math.ceil(r/(111195*CELL*max(.15,math.cos(math.radians(la))))))
    hits=set()
    for a in range(ia-span_lat,ia+span_lat+1):
        for b in range(ib-span_lon,ib+span_lon+1):
            hits.update(grid.get((a,b),[]))
    return sorted([(distance(ll,irve[s]['ll']),s) for s in hits if irve[s]['ll'] and distance(ll,irve[s]['ll'])<=r])

def evaluate(name,rows):
    strict=set()
    raw_gps={r:set() for r in RADII}
    count_gps={r:set() for r in RADII}
    power_gps={r:set() for r in RADII}
    both_gps={r:set() for r in RADII}
    detailed_gps={r:set() for r in RADII}
    cpo_both_gps={r:set() for r in RADII}
    counts={r:collections.Counter() for r in RADII}
    power_disagreements=collections.Counter()
    examples=[]
    tech_exact={'withTechnicalCount':0,'countMismatch':0,'withTechnicalPower':0,'powerMismatch':0}
    for row in rows:
        matched={pdc_unique[norm(i)] for i in row['ids'] if norm(i) in pdc_unique}
        src_count=row['count'];src_power=row['power'];src_signature=row['signature']
        if matched:
            strict.update(matched)
            if len(matched)==1:
                target=irve[next(iter(matched))]
                tech_exact['withTechnicalCount']+=src_count>0
                tech_exact['countMismatch']+=src_count>0 and src_count!=target['count']
                tech_exact['withTechnicalPower']+=src_power is not None
                tech_exact['powerMismatch']+=src_power is not None and not matchkw(src_power,target['powerMax'])
            continue
        near=neighborhood(row['ll'],max(RADII))
        for r in RADII:
            c=counts[r]
            c['unmatchedSourceLocations']+=1
            rr=[(dist,sid) for dist,sid in near if dist<=r]
            if not rr:
                c['noCandidateWithinRadius']+=1
                continue
            c['withCandidateWithinRadius']+=1
            if len(rr)==1:
                c['oneRawGpsCandidate']+=1
                raw_gps[r].add(rr[0][1])
            else:c['multipleRawGpsCandidates']+=1
            cnt=[(d,s) for d,s in rr if src_count>0 and src_count==irve[s]['count']]
            pwr=[(d,s) for d,s in rr if matchkw(src_power,irve[s]['powerMax'])]
            both=[(d,s) for d,s in cnt if matchkw(src_power,irve[s]['powerMax'])]
            exact_signature=[(d,s) for d,s in both if src_signature and signature_match(src_signature,irve[s]['powerList'])]
            cpo_both=[(d,s) for d,s in both if row['companies'] & irve[s]['companies']]
            c['sourceHasComparableCount']+=src_count>0
            c['sourceHasComparableMaxPower']+=src_power is not None
            c['sourceHasFullPowerSignature']+=bool(src_signature)
            if len(cnt)==1:count_gps[r].add(cnt[0][1]);c['uniqueCountCompatible']+=1
            if len(pwr)==1:power_gps[r].add(pwr[0][1]);c['uniquePowerCompatible']+=1
            if len(both)==1:
                both_gps[r].add(both[0][1]);c['uniqueCountAndPowerCompatible']+=1
                if len(rr)>1:c['resolvedGpsCollisionUsingCountAndPower']+=1
                if r==10 and len(examples)<24:
                    d,s=both[0]
                    examples.append({'source':name,'sourceLocation':row['id'],'irveStation':s,
                                    'distanceM':round(d,2),'sourceCount':src_count,'IRVECount':irve[s]['count'],
                                    'sourcePowerKw':src_power,'IRVEMaxPowerKw':irve[s]['powerMax'],
                                    'fullSignatureAgreement':bool(exact_signature)})
            elif len(both)>1:c['multipleCountAndPowerCompatible']+=1
            else:
                c['noCountAndPowerCompatible']+=1
                if len(rr)==1:
                    d,s=rr[0]
                    if src_count!=irve[s]['count']:power_disagreements['countMismatch']+=1
                    if not matchkw(src_power,irve[s]['powerMax']):power_disagreements['powerMismatchOrUnknown']+=1
            if len(exact_signature)==1:
                detailed_gps[r].add(exact_signature[0][1]);c['uniqueFullPowerSignatureCompatible']+=1
            if len(cpo_both)==1:cpo_both_gps[r].add(cpo_both[0][1]);c['uniqueCpoCountPowerCompatible']+=1
    return {'exact':strict,'rawGps':raw_gps,'countGps':count_gps,'powerGps':power_gps,
            'bothGps':both_gps,'fullGps':detailed_gps,'cpoGps':cpo_both_gps,
            'stats':counts,'exactTechnicalDiagnostics':tech_exact,
            'sample':examples,'disagreements':power_disagreements}

electra_meta=load('data/platforms/electra/france/manifest.json')
el=[]
for row in load('data/platforms/electra/france/source-locations.json.gz')['locations']:
    power=num(row.get('maxPower'))
    # Electra eMSP maxPower is reported in W (22000 = 22 kW).
    power=power/1000 if power is not None else None
    evs=row.get('evses') or []
    coord=row.get('coordinates') or {}
    el.append({'id':str(row.get('id')),'ll':gps(coord.get('latitude'),coord.get('longitude')),
               'ids':[e.get('evseId') for e in evs],'count':sources_count(evs,'electra'),
               'power':power,'signature':None,
               'companies':cpo_names([(row.get('cpo') or {}).get('name'),(row.get('operator') or {}).get('name')])})
ev_meta=load('data/electroverse/tariff_cache/manifest.json')
maps={str(m.get('electroverseLocationPk')):m for m in load('data/electroverse/irve_location_mapping.json')['mappings']}
evl=[]
for shard in ev_meta['shards']:
    for pk,station in load('data/electroverse/tariff_cache/'+shard['file']).get('stations',{}).items():
        sid=str(station.get('electroverseLocationPk') or pk)
        m=maps.get(sid) or {}
        gps_row=m.get('electroverse') or {}
        es=(station.get('tariff') or {}).get('evses') or []
        evse_powers=[]
        for e in es:
            powers=[x for x in (num(c.get('kilowatts')) for c in e.get('connectors') or []) if x is not None]
            evse_powers.append(max(powers) if powers else None)
        power_list=evse_powers if all(x is not None for x in evse_powers) and evse_powers else None
        evl.append({'id':sid,'ll':gps(gps_row.get('lat'),gps_row.get('lon')),
                    'ids':[e.get('physicalReference') for e in es],
                    'count':sources_count(es,'electroverse'),
                    'power':max((x for x in evse_powers if x),default=None),
                    'signature':power_list,
                    # The cached mapping's IRVE operator would be circular "CPO evidence".
                    'companies':cpo_names([gps_row.get('operatorName')])})
electra=evaluate('Electra eMSP',el)
electroverse=evaluate('Electroverse',evl)
result={
    'schemaVersion':1,'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'criteria':{
        'stationUnit':'unique IRVE station IDs; source count is number of EVSEs, NOT number of physical cabinets',
        'identity':'exact alphanumeric-normalized PDC reference keeps precedence; never remove identity-based match',
        'gpsRadiiMeters':RADII,
        'maxPowerTolerance':'absolute <= max(2 kW, 10% of greater maximum)',
        'count':'exact count equality between source EVSE IDs and IRVE unique normalized PDC IDs',
        'ElectraPower':'location.maxPower in watts / 1000; station maximum only, not per EVSE',
        'ElectroversePower':'maximum connector kilowatts by station; optional strict per-EVSE max-power multiset',
        'status':'GPS + count + power = technically corroborated candidate, NOT official validated identity',
        'cpo':'independent CPO consistency optional; Electroverse source operator name absent from mapping, so no independent CPO validation possible'},
    'datasetSizes':{'IRVE':len(irve),'ElectraEMSPFranceLocations':len(el),'ElectroverseCachedLocations':len(evl)},
    'exactStationMatches':{
        'IRVE_Electra':len(electra['exact']),
        'IRVE_Electroverse':len(electroverse['exact']),
        'threeWay':len(electra['exact']&electroverse['exact'])},
    'radii':{},
    'sourceDiagnostics':{
        'ElectraExact':electra['exactTechnicalDiagnostics'],
        'ElectroverseExact':electroverse['exactTechnicalDiagnostics'],
        'ElectraMismatch':dict(electra['disagreements']),
        'ElectroverseMismatch':dict(electroverse['disagreements'])},
    'sampleTechnicalCandidates':electra['sample'][:12]+electroverse['sample'][:12]
}
for r in RADII:
    line={}
    for method,label in [('rawGps','gpsOnlyUnique'),('countGps','gpsAndCount'),
                         ('powerGps','gpsAndPower'),('bothGps','gpsCountPower'),
                         ('fullGps','gpsCountDetailedPowerSignature'),('cpoGps','gpsCountPowerAndCpo')]:
        ae=electra['exact']|electra[method][r]
        av=electroverse['exact']|electroverse[method][r]
        line[label]={
            'IRVE_Electra':len(ae),'IRVE_Electroverse':len(av),
            'threeWay':len(ae&av),
            'addElectra':len(ae-electra['exact']),
            'addElectroverse':len(av-electroverse['exact']),
            'addThreeWay':len((ae&av)-(electra['exact']&electroverse['exact']))}
    line['diagnostics']={'Electra':dict(electra['stats'][r]),'Electroverse':dict(electroverse['stats'][r])}
    result['radii'][str(r)+'m']=line
print('STATION_TECHNICAL_OVERLAP_RESULT='+json.dumps({k:v for k,v in result.items() if k!='sampleTechnicalCandidates'},ensure_ascii=False,separators=(',',':')))
path=ROOT/'reports'/'station-overlap-power-count-sensitivity-20261009.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
