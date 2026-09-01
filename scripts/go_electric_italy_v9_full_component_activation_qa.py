#!/usr/bin/env python3
from __future__ import annotations

import argparse, gzip, json, math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPERATOR="Go Electric Stations SRLS"
EXPECTED_TOTAL_EVSE=75025
EXPECTED_VALIDATED=2214
EXPECTED_GO_ELECTRIC_RANKABLE=2214
EXPECTED_TOTAL_DIRECT=27840
EXPECTED_TIME=1052
EXPECTED_PARKING=700
EXPECTED_ON_NO_ENERGY=626
EXPECTED_ON_AFTER_TIME=74
SEMANTICS_QA_RUN=33551150109

def now_iso(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def load(path:Path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8') as fh:return json.load(fh)
    return json.loads(path.read_text(encoding='utf-8'))
def write_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write_gz(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True); raw=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode(); path.write_bytes(gzip.compress(raw,9,mtime=0))
def finite(v):
    try:
        n=float(v); return n if math.isfinite(n) else None
    except (TypeError,ValueError): return None

def component_map(t):
    out={}
    for c in t.get('priceComponents') or []:
        if not isinstance(c,dict): raise SystemExit('invalid component')
        typ=str(c.get('type') or '')
        if not typ or typ in out: raise SystemExit('duplicate/missing component type')
        out[typ]=c
    if 'energy' not in out: raise SystemExit('energy component missing')
    return out

def local_windows(p):
    s=p.get('startTime'); e=p.get('endTime')
    if bool(s)!=bool(e): raise SystemExit('partial parking local window')
    return [{'start':str(s),'end':str(e)}] if s and e else []

def runtime_pricing(t):
    comps=component_map(t); allowed={'energy','session','time','parking'}
    if not set(comps)<=allowed: raise SystemExit(f'unsupported components {set(comps)-allowed}')
    energy=comps['energy']; er=finite(energy.get('amount'))
    if energy.get('unit')!='per_kWh' or er is None or er<0: raise SystemExit('bad energy component')
    rule={'scope':'allDay','pricePerKwh':er}; pricing={'type':'rules','rules':[rule]}
    if 'session' in comps:
        c=comps['session']; v=finite(c.get('amount'))
        if c.get('unit')!='per_session' or v is None or v<0: raise SystemExit('bad session component')
        rule['sessionFeeEur']=v
    if 'time' in comps:
        c=comps['time']; v=finite(c.get('amount'))
        if c.get('unit')!='source_time_rate' or v is None or v<0: raise SystemExit('bad time component')
        rule['connectedTimePerMinuteEur']=v
    if 'parking' in comps:
        c=comps['parking']; v=finite(c.get('amount'))
        if c.get('unit')!='source_parking_rate' or v is None or v<0: raise SystemExit('bad parking component')
        r=t.get('restrictions') or {}; p=r.get('parking') if isinstance(r,dict) else None
        if not isinstance(p,dict): raise SystemExit('parking restriction missing')
        trigger=p.get('trigger'); windows=local_windows(p)
        if trigger=='onNoEnergyDelivery':
            fee={'eurPerMinute':v,'graceMinutes':0}
            if windows: fee['activeLocalWindows']=windows
            pricing['postChargeFee']=fee
        elif trigger=='onAfterTime':
            sec=finite(p.get('afterTime'))
            if sec is None or sec<=0: raise SystemExit('onAfterTime threshold missing')
            surcharge={'thresholdMinutes':sec/60.0,'eurPerMinute':v}
            if windows: surcharge['activeLocalWindows']=windows
            pricing['connectedTimeSurcharge']=surcharge
        else: raise SystemExit(f'unsupported parking trigger {trigger}')
    return pricing

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True); ap.add_argument('--semantics-proof',required=True)
    ap.add_argument('--out',default='data/consolidation/italy_v9_candidate_go_electric_full_components_qa.json.gz')
    ap.add_argument('--report',default='data/reports/go_electric_italy_v9_full_component_activation_qa.json'); args=ap.parse_args()
    payload=load(Path(args.candidate)); proof=load(Path(args.semantics_proof))
    if payload.get('publicationAllowed') is not False: raise SystemExit('input candidate must remain unpublished')
    gates=proof.get('gates') or {}
    if not all(gates.values()): raise SystemExit('semantics proof gates not green')
    if (proof.get('derived') or {}).get('timeAndParkingUnit')!='EUR_per_minute': raise SystemExit('minute semantics not proven')
    if (proof.get('derived') or {}).get('onAfterTimeMinutes')!=241.0: raise SystemExit('onAfterTime sample semantics drift')
    evses=payload.get('evses')
    if not isinstance(evses,list) or len(evses)!=EXPECTED_TOTAL_EVSE: raise SystemExit('Italy EVSE inventory drift')
    promoted=0; comp_counts=Counter(); triggers=Counter(); translated_sets=Counter()
    for evse in evses:
        t=evse.get('tccV9DirectTariff')
        if not isinstance(t,dict) or t.get('operator')!=OPERATOR: continue
        comps=component_map(t); types=tuple(sorted(comps)); translated_sets['+'.join(types)]+=1
        for typ in comps: comp_counts[typ]+=1
        if 'parking' in comps:
            p=((t.get('restrictions') or {}).get('parking') or {}); triggers[str(p.get('trigger'))]+=1
        rp=runtime_pricing(t)
        t['runtimePricing']=rp
        t['runtimeTranslation']={'energy':'pricePerKwh','session':'sessionFeeEur','time':'connectedTimePerMinuteEur','parkingOnNoEnergyDelivery':'postChargeFee','parkingOnAfterTime':'connectedTimeSurcharge','semanticsQaRun':SEMANTICS_QA_RUN,'exactPublicUiProofPassed':True}
        t['fullCostRankable']=True; t['runtimeRankable']=True; t['rankable']=True; t['requiresRuntimeComponentSupport']=False
        t['rankabilityReason']='all_go_electric_components_exact_runtime_mapping_staged'
        evse['tccV9RankableDirect']=True; promoted+=1
    if promoted!=EXPECTED_VALIDATED: raise SystemExit(f'Go Electric validated drift {promoted}')
    if comp_counts['time']!=EXPECTED_TIME or comp_counts['parking']!=EXPECTED_PARKING: raise SystemExit(f'component drift {comp_counts}')
    if triggers['onNoEnergyDelivery']!=EXPECTED_ON_NO_ENERGY or triggers['onAfterTime']!=EXPECTED_ON_AFTER_TIME: raise SystemExit(f'trigger drift {triggers}')
    by_station={}
    for e in evses: by_station.setdefault(str(e.get('stationId') or ''),[]).append(e)
    for s in payload.get('stations') or []:
        rows=by_station.get(str(s.get('stationId') or ''),[]); s['evses']=rows; s['rankableDirectEvseCount']=sum(e.get('tccV9RankableDirect') is True for e in rows); s['rankableDirect']=s['rankableDirectEvseCount']>0
    direct_total=sum(e.get('tccV9RankableDirect') is True for e in evses)
    direct_by=Counter((e.get('tccV9DirectTariff') or {}).get('operator') or 'UNKNOWN' for e in evses if e.get('tccV9RankableDirect') is True)
    if direct_total!=EXPECTED_TOTAL_DIRECT or direct_by[OPERATOR]!=EXPECTED_GO_ELECTRIC_RANKABLE: raise SystemExit(f'direct accounting drift total={direct_total} ge={direct_by[OPERATOR]}')
    counts=payload.setdefault('counts',{}); counts['rankableDirectEvseCount']=direct_total; counts['rankableDirectCoveragePct']=round(100*direct_total/len(evses),2); counts['rankableDirectByOperator']=dict(sorted(direct_by.items()))
    rules=payload.setdefault('rules',{}); rules['goElectricFullComponentRuntimeMappingStaged']=True; rules['goElectricTimeAndParkingMinuteSemanticsQaRun']=SEMANTICS_QA_RUN
    integ=payload.setdefault('goElectricIntegration',{}); current=int(integ.get('currentPhysicalEvse') or 2453)
    integ.update({'status':'full_component_runtime_mapping_candidate','acceptedExactEvseOffers':promoted,'runtimeRankableTotalEvse':promoted,'stagedMultiComponentEvse':0,'currentPhysicalEvseWithoutRuntimeRankableDirect':current-promoted,'builderAndEngineQaRequiredBeforePublication':True,'publicationAllowed':False})
    payload['generatedAt']=now_iso(); payload['dataset']='italy-v9-consolidated-candidate-go-electric-full-components-qa'; payload['publicationAllowed']=False; payload['publicationReason']='all Go Electric component mappings staged; stable V9 engine/builder QA required before publication'
    report={'schemaVersion':1,'generatedAt':payload['generatedAt'],'publicationAllowed':False,'stableActivationAllowed':False,'validatedGoElectricDirectEvse':promoted,'goElectricRuntimeCandidateEvse':direct_by[OPERATOR],'goElectricStagedEvse':0,'componentCounts':dict(comp_counts),'parkingTriggers':dict(triggers),'componentSets':dict(translated_sets),'directAccounting':{'rankableDirectEvse':direct_total,'rankableDirectCoveragePct':counts['rankableDirectCoveragePct'],'rankableDirectByOperator':counts['rankableDirectByOperator']},'goElectricPhysicalWithoutRuntimeCandidate':current-promoted,'semanticsEvidence':{'qaRun':SEMANTICS_QA_RUN,'timeAndParkingUnit':'EUR_per_minute','onAfterTimeMeaning':'after connector connection threshold'},'gates':{'validated2214Preserved':promoted==EXPECTED_VALIDATED,'all2214RuntimeCandidates':direct_by[OPERATOR]==EXPECTED_GO_ELECTRIC_RANKABLE,'time1052Translated':comp_counts['time']==EXPECTED_TIME,'parking700Translated':comp_counts['parking']==EXPECTED_PARKING,'onNoEnergy626Translated':triggers['onNoEnergyDelivery']==EXPECTED_ON_NO_ENERGY,'onAfterTime74Translated':triggers['onAfterTime']==EXPECTED_ON_AFTER_TIME,'totalDirect27840':direct_total==EXPECTED_TOTAL_DIRECT,'publicationDisabled':payload['publicationAllowed'] is False,'stableActivationDisabled':True}}
    if not all(report['gates'].values()): raise SystemExit(report['gates'])
    write_gz(Path(args.out),payload); write_json(Path(args.report),report); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
