#!/usr/bin/env python3
"""Cross-check Bump tariff detail on a second independently identified Bump EVSE."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from bump_tariff_detail_probe import post, build_selection

OUT=Path('reports/bump/tariff_crosscheck_latest.json')
EVSE_ID='b03c7079-fe14-d201-8e1d-2759540f804d'
EVSE_IDENTIFIER='FRBMPE6443'
TARIFF_GROUP_ID='1f7a109f-3a39-4c1e-9a5a-9195a43dcd9d'


def main():
    cache={}; selection=build_selection('Tariff',cache)
    q=f'''query TccTariff($tariffGroupId: TariffGroupId!, $evseId: EvseId, $hasAnonymous: Boolean) {{ tariffs {{ detail(tariffGroupId:$tariffGroupId, evseId:$evseId, hasAnonymous:$hasAnonymous) {{ {selection} }} }} }}'''
    attempts=[]
    for label,anon in (('anonymous_true',True),('anonymous_false',False)):
        status,obj=post(q,{'tariffGroupId':TARIFF_GROUP_ID,'evseId':EVSE_ID,'hasAnonymous':anon})
        data=(((obj.get('data') or {}).get('tariffs') or {}).get('detail')) if isinstance(obj,dict) else None
        errors=[str(e.get('message'))[:1000] for e in (obj.get('errors') or []) if isinstance(e,dict)]
        attempts.append({'label':label,'status':status,'errors':errors,'data':data})
    p={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'method':{'unauthenticated':True,'publicReadOnlyTariffQueryOnly':True,'mutationsSent':False,'credentialsUsed':False,'personalDataQueried':False},'verifiedBinding':{'officialEvseIdentifier':EVSE_IDENTIFIER,'evseId':EVSE_ID,'tariffGroupId':TARIFF_GROUP_ID},'attempts':attempts,'tariffResolved':any(a.get('data') is not None and not a.get('errors') for a in attempts)}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'tariffResolved':p['tariffResolved'],'attempts':attempts},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
