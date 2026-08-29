#!/usr/bin/env python3
from __future__ import annotations
import argparse, gzip, json
from collections import Counter, defaultdict
from pathlib import Path

KEYS={'Electra':'ELECTRA','Fastned':'FASTNED','IONITY':'IONITY'}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pun',required=True); ap.add_argument('--out',default='data/reports/atlante_chargeleague_pun_probe.json'); a=ap.parse_args()
    with gzip.open(a.pun,'rt',encoding='utf-8') as f: p=json.load(f)
    result={}
    for label,key in KEYS.items():
        rows=[]; parties=Counter(); states=Counter(); operators=Counter()
        for e in p.get('evses',[]):
            op=str(e.get('operator') or '')
            if key not in op.upper(): continue
            party=str(e.get('partyId') or '').upper(); parties[party]+=1; states[str(e.get('operationalState') or 'unknown')]+=1; operators[op]+=1
            rows.append(str(e.get('evseId') or ''))
        result[label]={'evseCount':len(rows),'partyIdCounts':dict(parties),'operationalStateCounts':dict(states),'operatorCounts':dict(operators.most_common(20)),'sampleEvseIds':rows[:20]}
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
