#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json
from collections import Counter
from pathlib import Path

def bucket(p):
    try:x=float(p)
    except Exception:return 'unknown'
    if x<=22:return '<=22'
    if x<=50:return '22-50'
    if x<=100:return '50-100'
    if x<=150:return '100-150'
    return '>150'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pun',required=True); ap.add_argument('--out',default='data/reports/duferco_italy_pun_profile.json'); a=ap.parse_args()
    with gzip.open(a.pun,'rt',encoding='utf-8') as f:p=json.load(f)
    rows=[e for e in p.get('evses',[]) if str(e.get('partyId') or '').upper()=='DUF']
    ops=Counter(str(e.get('operationalState') or 'unknown') for e in rows); occ=Counter(str(e.get('occupancyState') or 'unknown') for e in rows); powers=Counter(bucket(e.get('maxPowerKw')) for e in rows); exact=Counter(str(e.get('maxPowerKw')) for e in rows)
    operators=Counter(str(e.get('operator') or '') for e in rows); stations={e.get('stationId') for e in rows if e.get('stationId')}
    out={'partyId':'DUF','evseCount':len(rows),'stationCount':len(stations),'operationalStateCounts':dict(ops),'occupancyStateCounts':dict(occ),'powerBucketCounts':dict(powers),'topExactPowers':exact.most_common(30),'operatorCounts':dict(operators),'sample':[{'evseId':e.get('evseId'),'stationId':e.get('stationId'),'operator':e.get('operator'),'maxPowerKw':e.get('maxPowerKw'),'operationalState':e.get('operationalState'),'sourceStatus':e.get('sourceStatus'),'coordinates':e.get('coordinates')} for e in rows[:40]]}
    if len(rows)<500: raise RuntimeError(f'Unexpected DUF PUN inventory {len(rows)}')
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
