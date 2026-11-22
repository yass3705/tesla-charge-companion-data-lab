#!/usr/bin/env python3
"""Rank German CPO/operator integration priorities from the staged national catalog."""
from __future__ import annotations
import argparse,gzip,json
from collections import Counter
from pathlib import Path


def load_gz(path:Path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--catalog',type=Path,default=Path('data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz'))
    ap.add_argument('--output',type=Path,default=Path('data/germany/operator_priority.json'))
    args=ap.parse_args()
    d=load_gz(args.catalog)
    if d.get('dataset')!='germany-national-non-tesla-catalog-staging-tariff-classified':
        raise RuntimeError('unexpected catalog dataset')
    total=Counter(); matched=Counter(); raw=Counter(); cand=Counter(); operational=Counter()
    for s in d.get('sites') or []:
        op=s.get('operator') or '<unknown>'
        total[op]+=1
        if (s.get('afir') or {}).get('matchStatus')=='matched_safe': matched[op]+=1
        p=s.get('pricing') or {}
        if p.get('rawAfirTariffs'): raw[op]+=1
        if p.get('stagingRankableCandidate'): cand[op]+=1
        if (s.get('service') or {}).get('state')=='operational': operational[op]+=1
    rows=[]
    for op,n in total.most_common():
        rows.append({
            'operator':op,'sites':n,'safeAfirMatchedSites':matched[op],
            'sitesWithRawAfirTariff':raw[op],'stagingRankableAfirCandidateSites':cand[op],
            'sitesWithKnownOperationalState':operational[op],
            'afirCandidateCoveragePct':round(cand[op]*100/n,2) if n else 0.0,
            'priorityScore':round(n + cand[op]*1.5 + raw[op]*0.15,2),
        })
    rows.sort(key=lambda x:(-x['priorityScore'],-x['sites'],x['operator']))
    out={
        'schemaVersion':'0.1.0','dataset':'germany-cpo-integration-priority','countryCode':'DE',
        'scope':{'stagedOnly':True,'publishesToTcc':False,'purpose':'Prioritize direct CPO tariff/source research by national footprint and existing AFIR evidence.'},
        'operatorCount':len(rows),'topOperators':rows[:100]
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_GERMANY_OPERATOR_PRIORITY='+json.dumps(rows[:30],ensure_ascii=False))

if __name__=='__main__':main()
