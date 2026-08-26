#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

SRC = Path('data/national/bump_direct_tariffs_graphql_france.json.gz')
OUT = Path('reports/bump/unresolved_tariff_audit_latest.json')


def main() -> None:
    p = json.loads(gzip.decompress(SRC.read_bytes()))
    no_numeric=[]
    unmapped=[]
    unmatched=[]
    no_numeric_text=Counter()
    for s in p.get('stations',[]):
        sid=s.get('idStationItinerance') or s.get('stationKey')
        m=s.get('match') or {}
        if m.get('status')!='matched':
            unmatched.append({'stationId':sid,'name':s.get('name'),'address':s.get('address'),'reason':m.get('reason')})
            continue
        for pt in m.get('points') or []:
            t=pt.get('tariff')
            if not pt.get('mapped'):
                unmapped.append({'stationId':sid,'name':s.get('name'),'idPdc':pt.get('idPdcItinerance'),'powerKw':pt.get('powerKw')})
                continue
            if not isinstance(t,dict):
                continue
            has_numeric=any(isinstance(t.get(k),(int,float)) for k in ('energyEurPerKwh','timeEurPerHour','flatFeeEur'))
            if not has_numeric and not t.get('isTariffChangingInTime'):
                row={
                    'stationId':sid,'name':s.get('name'),'idPdc':pt.get('idPdcItinerance'),'powerKw':pt.get('powerKw'),
                    'tariffGroupId':pt.get('tariffGroupId'),'tariffId':t.get('tariffId'),'tariffName':t.get('name'),
                    'quickPriceType':t.get('quickPriceType'),'quickPriceEur':t.get('quickPriceEur'),
                    'minPriceEur':t.get('minPriceEur'),'quick':t.get('quick'),'short':t.get('short'),'long':t.get('long'),
                    'parkingText':t.get('parkingText'),'alternativeText':t.get('alternativeText')
                }
                no_numeric.append(row)
                no_numeric_text[(str(t.get('quick')),str(t.get('short')),str(t.get('long')),str(t.get('alternativeText')))]+=1
    out={
        'schemaVersion':'1.0.0',
        'sourceGeneratedAt':p.get('generatedAt'),
        'counts':{
            'unmatchedStations':len(unmatched),
            'unmappedPoints':len(unmapped),
            'pricedObjectsWithoutNumericComponent':len(no_numeric),
            'distinctNoNumericTexts':len(no_numeric_text),
        },
        'noNumericPatterns':[{'count':n,'quick':k[0],'short':k[1],'long':k[2],'alternativeText':k[3]} for k,n in no_numeric_text.most_common()],
        'noNumericExamples':no_numeric[:100],
        'unmappedPointExamples':unmapped[:100],
        'unmatchedStationExamples':unmatched[:100],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out['counts'],indent=2))

if __name__=='__main__': main()
