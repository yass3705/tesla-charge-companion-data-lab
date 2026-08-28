#!/usr/bin/env python3
import argparse, collections, datetime as dt, gzip, hashlib, json, math
from pathlib import Path

DAYS=['MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY']
JS_DAY={'SUNDAY':0,'MONDAY':1,'TUESDAY':2,'WEDNESDAY':3,'THURSDAY':4,'FRIDAY':5,'SATURDAY':6}
DIMS=('ENERGY','TIME','PARKING_TIME','FLAT')
UNSUPPORTED_RESTRICTIONS={'min_duration','max_duration','min_kwh','max_kwh','min_power','max_power','min_current','max_current','reservation'}
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

def component_for_dimension(elements,dim,day_name,m):
    for el in elements:
        rr=el.get('restrictions') or {}; days=rr.get('day_of_week')
        if days and day_name not in {str(x).upper() for x in days}: continue
        if rr.get('start_time') or rr.get('end_time'):
            if not in_window(m,rr.get('start_time') or '00:00',rr.get('end_time') or '24:00'): continue
        for pc in el.get('priceComponents') or []:
            if str(pc.get('type') or '').upper()==dim: return pc
    return None

def compile_tariff(t,today):
    if not tariff_current(t,today): return None,'not_current'
    current=[el for el in (t.get('elements') or []) if isinstance(el,dict) and current_element(el,today)]
    if not current: return None,'no_current_element'
    for el in current:
        rr=el.get('restrictions') or {}
        active={k for k,v in rr.items() if k not in {'start_date','end_date'} and v not in (None,[],{},'')}
        bad=active & UNSUPPORTED_RESTRICTIONS
        if bad: return None,'unsupported_restriction:'+','.join(sorted(bad))
        for pc in el.get('priceComponents') or []:
            typ=str(pc.get('type') or '').upper()
            if typ not in DIMS: return None,'unsupported_dimension:'+typ
            step=fnum(pc.get('stepSize'))
            if step not in (None,1.0): return None,'step_size'
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
            probe=a+(b-a)/2; vals={}
            for dim in ('ENERGY','TIME','PARKING_TIME'):
                pc=component_for_dimension(current,dim,day_name,probe); vals[dim]=component_gross(pc) if pc else 0.0
            billing='kwh' if vals['ENERGY']>0 else ('minute' if vals['TIME']>0 else 'kwh')
            rows.append(['timeWindow',hhmm(a),'24:00' if b==1440 else hhmm(b),billing,(t.get('currency') or 'EUR').upper(),round(vals['ENERGY'],6),round(vals['TIME']/60,8),round(flat,6),round(vals['PARKING_TIME']/60,8),0,0,[JS_DAY[day_name]]])
    merged={}
    for r in rows:
        key=json.dumps(r[:11],separators=(',',':'))
        if key not in merged: merged[key]=r
        else: merged[key][11]=sorted(set(merged[key][11]+r[11]))
    out=list(merged.values()); out.sort(key=lambda r:(r[1],r[2],r[11]))
    return out,None

def tariff_rank(t):
    typ=str(t.get('type') or '').upper(); return 0 if typ=='AD_HOC_PAYMENT' else (1 if typ=='REGULAR' else 2)

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
        candidates.append((tariff_rank(t),key,t,rules))
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
    stats={'connectors':0,'exactPricedConnectors':0,'unpricedConnectors':0,'ambiguousTariffConnectors':0,'unsupportedReasons':collections.Counter(),'configs':0,'pricedConfigs':0,'outOfBoundsStations':0,'outOfBoundsByParty':collections.Counter()}
    compile_cache={}; selection_cache={}; rows=[]
    for st in stations:
        co=st.get('coordinates') or {}; lat=fnum(co.get('latitude')); lon=fnum(co.get('longitude'))
        if lat is None or lon is None: continue
        if not in_nl_bounds(lat,lon):
            stats['outOfBoundsStations']+=1; stats['outOfBoundsByParty'][str(st.get('partyId') or '')]+=1; continue
        groups={}
        for evse in st.get('evses') or []:
            uid=str(evse.get('uid') or evse.get('evseId') or '')
            for c in evse.get('connectors') or []:
                stats['connectors']+=1; p=fnum(c.get('powerKw'))
                if not p or p<=0: continue
                tkey,rules,err=choose_tariff(c.get('tariffKeys') or [],tariffs,today,stats,compile_cache,selection_cache); priced=rules is not None
                stats['exactPricedConnectors' if priced else 'unpricedConnectors']+=1
                sig=json.dumps(rules,separators=(',',':')) if priced else 'UNPRICED'; gkey=(kind(c),round(p,1),sig)
                g=groups.setdefault(gkey,{'kind':gkey[0],'power':gkey[1],'rules':rules,'tariffKey':tkey,'evses':set(),'count':0}); g['count']+=1
                if uid: g['evses'].add(uid)
        configs=[]
        for i,g in enumerate(sorted(groups.values(),key=lambda x:(x['kind'],x['power'],x['tariffKey'] or ''))):
            stalls=len(g['evses']) or g['count']; priced=g['rules'] is not None; label=('DOT-NL public' if priced else 'Tarif DOT-NL non calculable')+f" · {g['kind']} {g['power']:g} kW"
            cid=f"dotnl-{i}-{g['kind'].lower()}-{str(g['power']).replace('.','_')}"; configs.append([cid,label,g['kind'],g['power'],stalls,g['rules'] or []]); stats['configs']+=1
            if priced: stats['pricedConfigs']+=1
        if not configs: continue
        name=str(st.get('name') or '').strip() or f"Borne {st.get('stationId')}"; address=', '.join(x for x in [str(st.get('address') or '').strip(),str(st.get('postalCode') or '').strip(),str(st.get('city') or '').strip()] if x); operator=str(st.get('operatorName') or '').strip() or str(st.get('partyId') or 'DOT-NL')
        physical=len({str(e.get('uid') or e.get('evseId') or '') for e in st.get('evses') or [] if (e.get('uid') or e.get('evseId'))})
        rows.append([st.get('stationId'),name,address,round(lat,6),round(lon,6),operator,physical,0,configs,generated[:10],st.get('serviceStatus') or 'UNKNOWN'])
    args.out_dir.mkdir(parents=True,exist_ok=True); tiles=collections.defaultdict(list)
    for row in rows:
        tid,a,b=tile_id(row[3],row[4]); tiles[(tid,a,b)].append(row)
    manifest_tiles=[]
    for (tid,a,b),arr in sorted(tiles.items()):
        arr.sort(key=lambda r:str(r[0])); path=args.out_dir/f'{tid}.json.gz'; _,gz_n=gz_write(path,arr); manifest_tiles.append({'id':tid,'file':path.name,'minLat':a,'maxLat':a+.5,'minLon':b,'maxLon':b+.5,'count':len(arr),'bytes':gz_n,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    rows.sort(key=lambda r:str(r[0])); raw_all,gz_all=gz_write(args.out_dir/'all.json.gz',rows)
    manifest={'schemaVersion':1,'dataset':'netherlands-non-tesla-runtime-test','generatedAt':generated,'effectiveTariffDate':today.isoformat(),'stationCount':len(rows),'configurationCount':stats['configs'],'pricedConfigurationCount':stats['pricedConfigs'],'tileSizeDegrees':.5,'tileCount':len(manifest_tiles),'allFile':'all.json.gz','allBytes':gz_all,'tiles':manifest_tiles,'scope':{'countryCode':'NL','europeanNetherlandsBounds':list(NL_BOUNDS),'teslaExcluded':True,'strictTariffCompiler':True,'publishedToTcc':False}}
    (args.out_dir/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    report={'dataset':'dotnl-netherlands-runtime-report','generatedAt':generated,'effectiveTariffDate':today.isoformat(),'stationCount':len(rows),'tileCount':len(manifest_tiles),'allCompressedBytes':gz_all,'allUncompressedBytes':raw_all,'cache':{'compiledTariffs':len(compile_cache),'tariffSelections':len(selection_cache)},'metrics':{**{k:v for k,v in stats.items() if not isinstance(v,collections.Counter)},'unsupportedReasons':dict(stats['unsupportedReasons'].most_common()),'outOfBoundsByParty':dict(stats['outOfBoundsByParty'].most_common())},'coveragePct':{'exactTariffConnectors':round(100*stats['exactPricedConnectors']/stats['connectors'],3) if stats['connectors'] else 0,'pricedConfigs':round(100*stats['pricedConfigs']/stats['configs'],3) if stats['configs'] else 0},'publishedToTcc':False}
    args.report_json.parent.mkdir(parents=True,exist_ok=True); args.report_json.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
