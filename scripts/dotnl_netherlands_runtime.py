#!/usr/bin/env python3
import argparse, collections, datetime as dt, gzip, hashlib, json, math
from pathlib import Path

DAYS=['MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY']
JS_DAY={'SUNDAY':0,'MONDAY':1,'TUESDAY':2,'WEDNESDAY':3,'THURSDAY':4,'FRIDAY':5,'SATURDAY':6}
DIMS=('ENERGY','TIME','PARKING_TIME','FLAT')
UNSUPPORTED_RESTRICTIONS={'min_kwh','max_kwh','min_power','max_power','min_current','max_current','reservation'}
NL_BOUNDS=(50.5,53.8,3.0,7.6)  # generous European-Netherlands guardrail


def fnum(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def date_of(v):
    if not v: return None
    try: return dt.date.fromisoformat(str(v)[:10])
    except ValueError: return None

def minute(v,default):
    if not v: return default
    try:
        hh,mm=str(v)[:5].split(':'); return max(0,min(1440,int(hh)*60+int(mm)))
    except Exception: return default

def hhmm(m):
    m=int(m)%1440; return f'{m//60:02d}:{m%60:02d}'

def in_window(m,start,end):
    s=minute(start,0); e=minute(end,1440)
    if s==e: return True
    return (s<e and s<=m<e) or (s>e and (m>=s or m<e))

def in_nl_bounds(lat,lon):
    a,b,c,d=NL_BOUNDS; return a<=lat<=b and c<=lon<=d

def current_element(el,today):
    rr=el.get('restrictions') or {}; s=date_of(rr.get('start_date')); e=date_of(rr.get('end_date'))
    return not (s and today<s) and not (e and today>e)

def tariff_current(t,today):
    s=date_of(t.get('startDateTime')); e=date_of(t.get('endDateTime'))
    return not (s and today<s) and not (e and today>e)

def component_gross(pc):
    value=fnum(pc.get('priceInclVat'))
    if value is not None: return value
    ex=fnum(pc.get('priceExVat'))
    if ex is None: return None
    return ex*(1+(fnum(pc.get('vatPct')) or 0)/100)

def static_element_matches(el,day_name,m):
    rr=el.get('restrictions') or {}; days=rr.get('day_of_week')
    if days and day_name not in {str(x).upper() for x in days}: return False
    if rr.get('start_time') or rr.get('end_time'):
        if not in_window(m,rr.get('start_time') or '00:00',rr.get('end_time') or '24:00'): return False
    return True

def element_component(el,dim):
    for pc in el.get('priceComponents') or []:
        if str(pc.get('type') or '').upper()==dim: return pc
    return None

def duration_interval(el):
    rr=el.get('restrictions') or {}
    mn=fnum(rr.get('min_duration')); mx=fnum(rr.get('max_duration'))
    mn=max(0.0,mn or 0.0)
    if mx is not None: mx=max(0.0,mx)
    if mx is not None and mx<=mn: return None
    return mn,mx

def dimension_schedule(elements,dim,day_name,m):
    candidates=[]
    boundaries={0.0}
    for el in elements:
        if not static_element_matches(el,day_name,m): continue
        pc=element_component(el,dim)
        if not pc: continue
        interval=duration_interval(el)
        if interval is None: return None,None,'invalid_duration_range'
        mn,mx=interval
        rate=component_gross(pc)
        if rate is None: return None,None,'missing_price'
        if dim in ('TIME','PARKING_TIME'):
            # Existing DOT-NL TIME/PARKING_TIME components with step 1 or
            # 60 are represented as per-minute amounts.  Preserve that
            # established convention, while honoring larger OCPI increments
            # (notably StellaPower's 900-second parking increment).
            step=fnum(pc.get('stepSize'))
            rate/=(step if step and step>60 else 60.0)
        candidates.append((mn,mx,rate))
        boundaries.add(mn)
        if mx is not None: boundaries.add(mx)

    if not candidates: return 0.0,[],None

    def rate_at(seconds):
        for mn,mx,rate in candidates:
            if seconds+1e-9<mn: continue
            if mx is not None and seconds>=mx-1e-9: continue
            return rate
        return 0.0

    points=sorted(boundaries)
    spans=[]
    for i,a in enumerate(points):
        b=points[i+1] if i+1<len(points) else None
        probe=a if b is None else a+(b-a)/2
        if b is None: probe=a+1e-6
        spans.append((a,b,rate_at(probe)))

    base=rate_at(0.0)
    bands=[]
    for a,b,rate in spans:
        if abs(rate-base)<=1e-12: continue
        if bands and bands[-1][0]==dim and bands[-1][2]==a and abs(bands[-1][3]-rate)<=1e-12:
            bands[-1][2]=b
        else:
            bands.append([dim,round(a,6),None if b is None else round(b,6),round(rate,8)])
    return base,bands,None

def compile_tariff(t,today):
    if not tariff_current(t,today): return None,'not_current'
    current=[el for el in (t.get('elements') or []) if isinstance(el,dict) and current_element(el,today)]
    if not current: return None,'no_current_element'
    for el in current:
        rr=el.get('restrictions') or {}
        active={k for k,v in rr.items() if k not in {'start_date','end_date'} and v not in (None,[],{},'')}
        bad=active & UNSUPPORTED_RESTRICTIONS
        if bad: return None,'unsupported_restriction:'+','.join(sorted(bad))
        if (rr.get('min_duration') not in (None,'') or rr.get('max_duration') not in (None,'')):
            if duration_interval(el) is None: return None,'invalid_duration_range'
            if element_component(el,'FLAT') is not None: return None,'duration_restricted_flat'
        for pc in el.get('priceComponents') or []:
            typ=str(pc.get('type') or '').upper()
            if typ not in DIMS: return None,'unsupported_dimension:'+typ
            step=fnum(pc.get('stepSize'))
            # OCPI expresses TIME and PARKING_TIME step_size in seconds.
            # A 60-second step is therefore a normal per-minute component;
            # the compiler converts its rate to the runtime's per-second
            # representation in dimension_schedule().  Keep the stricter
            # one-unit rule for ENERGY and FLAT so we never reinterpret a
            # monetary amount with the wrong billing unit.
            if step not in (None,1.0) and not (typ in {'TIME','PARKING_TIME'} and step in {60.0,900.0}):
                return None,'step_size'
            if component_gross(pc) is None: return None,'missing_price'

    flat_components=[]
    for el in current:
        rr=el.get('restrictions') or {}
        for pc in el.get('priceComponents') or []:
            if str(pc.get('type') or '').upper()=='FLAT':
                if any(rr.get(k) not in (None,[],{},'') for k in ('start_time','end_time','day_of_week')): return None,'restricted_flat'
                flat_components.append(pc)
    flat=0.0
    if flat_components:
        first=component_gross(flat_components[0])
        if any(abs(component_gross(pc)-first)>1e-9 for pc in flat_components[1:]): return None,'multiple_flat'
        flat=first

    boundaries={0,1440}
    for el in current:
        rr=el.get('restrictions') or {}
        if rr.get('start_time'): boundaries.add(minute(rr.get('start_time'),0))
        if rr.get('end_time'): boundaries.add(minute(rr.get('end_time'),1440))

    bounds=sorted(boundaries); rows=[]
    for day_name in DAYS:
        for a,b in zip(bounds,bounds[1:]):
            if b<=a: continue
            probe=a+(b-a)/2
            values={}; duration_bands=[]
            for dim in ('ENERGY','TIME','PARKING_TIME'):
                base,bands,err=dimension_schedule(current,dim,day_name,probe)
                if err: return None,err
                values[dim]=base
                duration_bands.extend(bands)
            billing='kwh' if values['ENERGY']>0 else ('minute' if values['TIME']>0 else 'kwh')
            rows.append([
                'timeWindow',hhmm(a),'24:00' if b==1440 else hhmm(b),billing,
                (t.get('currency') or 'EUR').upper(),
                round(values['ENERGY'],6),round(values['TIME'],8),round(flat,6),
                round(values['PARKING_TIME'],8),0,0,[JS_DAY[day_name]],duration_bands
            ])

    merged={}
    for r in rows:
        key=json.dumps(r[:11]+[r[12]],separators=(',',':'))
        if key not in merged: merged[key]=r
        else: merged[key][11]=sorted(set(merged[key][11]+r[11]))
    out=list(merged.values()); out.sort(key=lambda r:(r[1],r[2],r[11]))
    return out,None

def tariff_rank(t):
    typ=str(t.get('type') or '').upper()
    if typ=='AD_HOC_PAYMENT': return 0
    # DOT-NL carries the CPO owner's tariff objects (party_id is the CPO,
    # not an eMSP).  OCPI REGULAR therefore cannot be rejected as roaming
    # solely because of its type: the national CPO tariff remains usable for
    # direct/app/QR presentation unless another explicit field says that it is
    # a third-party or roaming tariff.  AD_HOC_PAYMENT remains preferred when
    # both forms are present.
    if typ in {'REGULAR', ''}: return 1
    return None

def choose_tariff(keys,tariffs,today,stats,compile_cache,selection_cache):
    selector=tuple(keys)
    if selector in selection_cache:
        tkey,rules,err,reasons=selection_cache[selector]
        for reason,count in reasons.items(): stats['unsupportedReasons'][reason]+=count
        if err=='ambiguous': stats['ambiguousTariffConnectors']+=1
        return tkey,rules,err
    candidates=[]; reasons=collections.Counter()
    for key in keys:
        t=tariffs.get(key)
        if not t: continue
        if key not in compile_cache: compile_cache[key]=compile_tariff(t,today)
        rules,reason=compile_cache[key]
        if reason: reasons[reason]+=1; continue
        rank=tariff_rank(t)
        if rank is None:
            reasons['non_direct_tariff_type:'+str(t.get('type') or '').upper()]+=1
            continue
        candidates.append((rank,key,t,rules))
    if not candidates: result=(None,None,'none_exact',dict(reasons))
    else:
        best=min(x[0] for x in candidates); candidates=[x for x in candidates if x[0]==best]
        sigs={json.dumps(x[3],separators=(',',':')) for x in candidates}
        if len(sigs)>1: result=(None,None,'ambiguous',dict(reasons))
        else:
            x=candidates[0]; result=(x[1],x[3],None,dict(reasons))
    selection_cache[selector]=result; tkey,rules,err,reasons=result
    for reason,count in reasons.items(): stats['unsupportedReasons'][reason]+=count
    if err=='ambiguous': stats['ambiguousTariffConnectors']+=1
    return tkey,rules,err

def kind(conn):
    pt=str(conn.get('powerType') or '').upper(); st=str(conn.get('standard') or '').upper()
    return 'DC' if pt=='DC' or 'CHADEMO' in st or 'COMBO' in st or 'CCS' in st else 'AC'

def gz_write(path,obj):
    raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode(); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb') as fh:
        with gzip.GzipFile(fileobj=fh,mode='wb',compresslevel=9,mtime=0) as g: g.write(raw)
    return len(raw),path.stat().st_size

def tile_id(lat,lon,size=.5):
    a=math.floor(lat/size)*size; b=math.floor(lon/size)*size; fmt=lambda x:str(round(x*2)).replace('-','m')
    return f't_{fmt(a)}_{fmt(b)}',a,b

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('normalized_gz',type=Path); ap.add_argument('out_dir',type=Path); ap.add_argument('report_json',type=Path); args=ap.parse_args()
    with gzip.open(args.normalized_gz,'rt',encoding='utf-8') as f: data=json.load(f)
    tariffs=data.get('tariffs') or {}; stations=data.get('stations') or []; generated=str(data.get('generatedAt') or dt.datetime.now(dt.timezone.utc).isoformat()); today=date_of(generated) or dt.datetime.now(dt.timezone.utc).date()
    stats={'connectors':0,'exactPricedConnectors':0,'unpricedConnectors':0,'ambiguousTariffConnectors':0,'unsupportedReasons':collections.Counter(),'configs':0,'pricedConfigs':0,'outOfBoundsStations':0,'outOfBoundsByParty':collections.Counter(),'durationBandConfigs':0}
    compile_cache={}; selection_cache={}; rows=[]
    for st in stations:
        co=st.get('coordinates') or {}; lat=fnum(co.get('latitude')); lon=fnum(co.get('longitude'))
        if lat is None or lon is None or not in_nl_bounds(lat,lon):
            stats['outOfBoundsStations']+=1
            stats['outOfBoundsByParty'][str(st.get('partyId') or 'UNKNOWN')]+=1
            continue
        station_id=str(st.get('stationId') or '')
        if not station_id: continue
        groups={}
        last_updated=str(st.get('lastUpdated') or '')
        for evse in st.get('evses') or []:
            last_updated=max(last_updated,str(evse.get('lastUpdated') or ''))
            for conn in evse.get('connectors') or []:
                stats['connectors']+=1
                last_updated=max(last_updated,str(conn.get('lastUpdated') or ''))
                tariff_key,rules,reason=choose_tariff(conn.get('tariffKeys') or [],tariffs,today,stats,compile_cache,selection_cache)
                if tariff_key:
                    stats['exactPricedConnectors']+=1
                else:
                    stats['unpricedConnectors']+=1
                power=fnum(conn.get('powerKw')) or 11.0
                power=round(max(0.1,power),1)
                connector_kind=kind(conn)
                signature=(connector_kind,power,tariff_key or '')
                if signature not in groups:
                    groups[signature]={'evses':set(),'rules':rules or []}
                groups[signature]['evses'].add(str(evse.get('evseId') or evse.get('uid') or ''))
        if not groups: continue
        configs=[]
        for index,((connector_kind,power,tariff_key),group) in enumerate(sorted(groups.items(),key=lambda x:(x[0][0],x[0][1],x[0][2]))):
            stall_count=len(group['evses']) or 1
            config_id=f'dotnl-{index}-{connector_kind.lower()}-{str(power).replace(".","_")}'
            label=f'DOT-NL public · {connector_kind} {power:g} kW'
            rules=group['rules']
            configs.append([config_id,label,connector_kind,power,stall_count,rules])
            stats['configs']+=1
            if rules:
                stats['pricedConfigs']+=1
                if any(rule[12] for rule in rules): stats['durationBandConfigs']+=1
        address=', '.join(str(st.get(key) or '').strip() for key in ('address','postalCode','city') if st.get(key))
        stalls=sum(config[4] for config in configs)
        rows.append([station_id,st.get('name') or address,address,round(lat,6),round(lon,6),
                     st.get('operatorName') or st.get('partyId') or 'DOT-NL',stalls,None,configs,
                     last_updated or generated,st.get('serviceStatus') or 'UNKNOWN'])

    args.out_dir.mkdir(parents=True,exist_ok=True)
    _,all_bytes=gz_write(args.out_dir/'all.json.gz',rows)
    all_sha=hashlib.sha256((args.out_dir/'all.json.gz').read_bytes()).hexdigest()
    tiled=collections.defaultdict(list)
    for row in rows:
        tile,lo_lat,lo_lon=tile_id(row[3],row[4])
        tiled[(tile,lo_lat,lo_lon)].append(row)
    tiles=[]
    for (tile,lo_lat,lo_lon),fragment in sorted(tiled.items()):
        file=f'{tile}.json.gz'
        _,gz_bytes=gz_write(args.out_dir/file,fragment)
        tiles.append({'id':tile,'file':file,'count':len(fragment),'bytes':gz_bytes,
                      'sha256':hashlib.sha256((args.out_dir/file).read_bytes()).hexdigest(),
                      'minLat':lo_lat,'maxLat':lo_lat+.5,'minLon':lo_lon,'maxLon':lo_lon+.5})
    manifest={
        'schemaVersion':2,'dataset':'netherlands-non-tesla-runtime',
        'generatedAt':generated,'effectiveTariffDate':today.isoformat(),
        'stationCount':len(rows),'configurationCount':stats['configs'],
        'pricedConfigurationCount':stats['pricedConfigs'],
        'durationBandConfigurationCount':stats['durationBandConfigs'],
        'tileSizeDegrees':.5,'tileCount':len(tiles),'allFile':'all.json.gz',
        'allBytes':all_bytes,'allSha256':all_sha,'tiles':tiles,
        'scope':{'countryCode':'NL','teslaExcluded':True,'strictTariffCompiler':True,
                 'ocpiDurationBands':True,'ocpiOpeningTimes':False,
                 'ocpiParkingRestrictions':False,'publishedToTcc':False,
                 'europeanNetherlandsBounds':list(NL_BOUNDS)}
    }
    (args.out_dir/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={
        'dataset':'dotnl-netherlands-runtime-report','generatedAt':generated,
        'stationCount':len(rows),'metrics':{**stats,'unsupportedReasons':dict(stats['unsupportedReasons']),
                                          'outOfBoundsByParty':dict(stats['outOfBoundsByParty'])},
        'coveragePct':{'exactTariffConnectors':round(100*stats['exactPricedConnectors']/max(1,stats['connectors']),3),
                       'pricedConfigurations':round(100*stats['pricedConfigs']/max(1,stats['configs']),3)}
    }
    args.report_json.parent.mkdir(parents=True,exist_ok=True)
    args.report_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'stationCount':len(rows),'metrics':report['metrics'],
                      'coveragePct':report['coveragePct']},ensure_ascii=False))

if __name__=='__main__': main()
