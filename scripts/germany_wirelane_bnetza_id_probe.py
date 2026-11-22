#!/usr/bin/env python3
"""Inspect every BNetzA identifier field for Wirelane rows."""
from __future__ import annotations
import json,re,tempfile
from collections import Counter
from pathlib import Path
import germany_bnetza_catalog as bnetza
import germany_bnetza_live as live  # noqa:F401

OP='Wirelane Public 1 GmbH'

def main():
    with tempfile.TemporaryDirectory() as td:
        r=bnetza.build(None,Path(td)/'b.json.gz',None)
    rows=[s for s in r['stations'] if s.get('operator')==OP]
    c=Counter();examples=[]
    for s in rows:
        if s.get('operatorId'):c['operatorIdPresent']+=1
        for conn in s.get('connectors') or []:
            if conn.get('evseId'):c['evseIdPresent']+=1
            if conn.get('publicKey'):c['publicKeyPresent']+=1
            for field in ('evseId','publicKey'):
                v=conn.get(field)
                if v and re.search(r'WLN|DE\*?WLN',str(v),re.I):c[f'{field}WirelaneLike']+=1
        if len(examples)<25:
            examples.append({'stationId':s.get('stationId'),'operatorId':s.get('operatorId'),'address':s.get('address'),'connectors':s.get('connectors')})
    out={'dataset':'germany-wirelane-bnetza-id-probe','operator':OP,'stats':{'rows':len(rows),**dict(c)},'operatorIds':dict(Counter(s.get('operatorId') or '<none>' for s in rows)),'examples':examples}
    p=Path('data/germany/wirelane_bnetza_id_probe.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_WIRELANE_BNETZA_ID_PROBE='+json.dumps({'stats':out['stats'],'operatorIds':out['operatorIds'],'examples':examples[:5]},ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
