#!/usr/bin/env python3
import argparse, collections, gzip, hashlib, json
from pathlib import Path


def gz_read(path):
    with gzip.open(path,'rt',encoding='utf-8') as f: return json.load(f)

def gz_write(path,obj):
    raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    with path.open('wb') as fh:
        with gzip.GzipFile(fileobj=fh,mode='wb',compresslevel=9,mtime=0) as g: g.write(raw)
    return len(raw),path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest()

def first(obj,*keys):
    if not isinstance(obj,dict): return None
    for k in keys:
        if k in obj: return obj.get(k)
    return None

def hhmm(v):
    s=str(v or '')
    return s[:5] if len(s)>=5 and s[2]==':' else ''

def regular_rows(opening,stats):
    rows=[]
    hours=first(opening,'regular_hours','regularHours') or []
    per_day=collections.Counter()
    for h in hours:
        if not isinstance(h,dict): continue
        try: wd=int(first(h,'weekday','week_day'))
        except (TypeError,ValueError): continue
        if wd<1 or wd>7: continue
        day=wd%7
        start=hhmm(first(h,'period_begin','periodBegin'))
        end=hhmm(first(h,'period_end','periodEnd'))
        if not start or not end: continue
        if end>start:
            rows.append([day,start,end]); per_day[day]+=1
        elif end<start:
            rows.append([day,start,'24:00']); rows.append([(day+1)%7,'00:00',end]); per_day[day]+=1; per_day[(day+1)%7]+=1
        else:
            stats['equalBeginEndIgnored']+=1
    if any(n>1 for n in per_day.values()): stats['stationsWithMultiIntervalRegular']+=1
    return sorted(rows,key=lambda r:(r[0],r[1],r[2]))

def exception_rows(opening,stats):
    out=[]
    for mode,keys in ((1,('exceptional_openings','exceptionalOpenings')),(0,('exceptional_closings','exceptionalClosings'))):
        for p in first(opening,*keys) or []:
            if not isinstance(p,dict): continue
            begin=str(first(p,'period_begin','periodBegin') or '')
            end=str(first(p,'period_end','periodEnd') or '')
            if begin and end:
                out.append([mode,begin,end]); stats['exceptionPeriods']+=1
    return sorted(out,key=lambda r:(r[1],r[0],r[2]))

def compact_access(st,stats):
    opening=st.get('openingTimes') if isinstance(st,dict) else None
    parking=str(st.get('parkingType') or '') if isinstance(st,dict) else ''
    restrictions=sorted({str(x).upper() for ev in (st.get('evses') or []) for x in (ev.get('parkingRestrictions') or []) if x}) if isinstance(st,dict) else []
    if restrictions: stats['stationsWithParkingRestrictions']+=1
    if parking: stats['stationsWithParkingType']+=1
    exceptions=exception_rows(opening,stats) if isinstance(opening,dict) else []
    if isinstance(opening,dict) and bool(first(opening,'twentyfourseven','twentyFourSeven')):
        stats['access24x7']+=1; return [2,[],exceptions,parking,restrictions]
    regular=regular_rows(opening,stats) if isinstance(opening,dict) else []
    if regular:
        stats['accessScheduled']+=1; return [1,regular,exceptions,parking,restrictions]
    stats['accessUnknown']+=1; return [0,[],exceptions,parking,restrictions]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('normalized_gz',type=Path); ap.add_argument('runtime_dir',type=Path); ap.add_argument('report_json',type=Path); args=ap.parse_args()
    data=gz_read(args.normalized_gz)
    stats=collections.Counter()
    access_by_id={}
    for st in data.get('stations') or []:
        sid=str(st.get('stationId') or '')
        if sid: access_by_id[sid]=compact_access(st,stats)
    manifest_path=args.runtime_dir/'manifest.json'; manifest=json.load(open(manifest_path,encoding='utf-8'))
    def patch_rows(rows):
        patched=0
        for row in rows:
            if not isinstance(row,list) or not row: continue
            acc=access_by_id.get(str(row[0]))
            if acc is None: continue
            while len(row)<=7: row.append(None)
            row[7]=acc; patched+=1
        return patched
    all_path=args.runtime_dir/manifest['allFile']; rows=gz_read(all_path); stats['runtimeRowsPatched']+=patch_rows(rows)
    _,all_bytes,_=gz_write(all_path,rows); manifest['allBytes']=all_bytes
    for tile in manifest.get('tiles') or []:
        path=args.runtime_dir/tile['file']; arr=gz_read(path); patch_rows(arr)
        _,gz_n,sha=gz_write(path,arr); tile['bytes']=gz_n; tile['count']=len(arr); tile['sha256']=sha
    manifest['schemaVersion']=3
    scope=manifest.setdefault('scope',{}); scope['ocpiOpeningTimes']=True; scope['ocpiParkingRestrictions']=True
    manifest['accessCoverage']={
        'twentyFourSevenStations':stats['access24x7'],
        'scheduledStations':stats['accessScheduled'],
        'unknownStations':stats['accessUnknown'],
        'stationsWithExceptionalPeriods':sum(1 for v in access_by_id.values() if v[2]),
        'stationsWithMultiIntervalRegular':stats['stationsWithMultiIntervalRegular'],
        'stationsWithParkingRestrictions':stats['stationsWithParkingRestrictions'],
        'stationsWithParkingType':stats['stationsWithParkingType'],
    }
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    report={
        'dataset':'dotnl-netherlands-access-patch-report',
        'stationCount':manifest.get('stationCount'),
        'schemaVersion':manifest.get('schemaVersion'),
        'metrics':dict(stats),
        'coveragePct':{
            'knownOpeningHours':round(100*(stats['access24x7']+stats['accessScheduled'])/max(1,len(access_by_id)),3),
            'multiIntervalRegular':round(100*stats['stationsWithMultiIntervalRegular']/max(1,len(access_by_id)),3),
        }
    }
    args.report_json.parent.mkdir(parents=True,exist_ok=True); args.report_json.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
