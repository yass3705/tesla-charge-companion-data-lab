#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json
from pathlib import Path

def load(p):
    with gzip.open(p,'rt',encoding='utf-8') as fh:return json.load(fh)
def write_gz(p,d):
    p.parent.mkdir(parents=True,exist_ok=True); raw=(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n').encode(); p.write_bytes(gzip.compress(raw,9,mtime=0))
def write_json(p,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def complement_window(w):
    s=str(w.get('start') or ''); e=str(w.get('end') or '')
    if not s or not e or s==e: raise SystemExit(f'invalid active window {w}')
    return [{'start':e,'end':s}]
def base_rule(rule):
    return {k:v for k,v in rule.items() if k not in {'connectedTimeFreeMinutes','connectedTimePerMinuteAfterFreeEur','start','end','scope'}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True)
    ap.add_argument('--out',default='data/consolidation/italy_v9_candidate_go_electric_engine_compatible_qa.json.gz')
    ap.add_argument('--report',default='data/reports/go_electric_italy_v9_engine_primitive_mapping_qa.json'); a=ap.parse_args()
    d=load(Path(a.candidate)); ge=0; post=0; post_window=0; after=0; after_window=0; after_plain=0
    for e in d.get('evses') or []:
        t=e.get('tccV9DirectTariff') or {}
        if t.get('operator')!='Go Electric Stations SRLS': continue
        ge+=1; p=t.get('runtimePricing') or {}; rules=p.get('rules')
        if p.get('type')!='rules' or not isinstance(rules,list) or len(rules)!=1: raise SystemExit(f"{e.get('evseId')}: unexpected runtime pricing")
        fee=p.get('postChargeFee')
        if isinstance(fee,dict):
            post+=1; wins=fee.pop('activeLocalWindows',None)
            if wins:
                if len(wins)!=1: raise SystemExit('multiple post-charge windows unsupported')
                fee['exemptLocalWindows']=complement_window(wins[0]); post_window+=1
        surcharge=p.pop('connectedTimeSurcharge',None)
        if isinstance(surcharge,dict):
            after+=1; threshold=surcharge.get('thresholdMinutes'); rate=surcharge.get('eurPerMinute'); wins=surcharge.get('activeLocalWindows') or []
            r0=rules[0]; b=base_rule(r0)
            if wins:
                if len(wins)!=1: raise SystemExit('multiple surcharge windows unsupported')
                s=wins[0].get('start'); en=wins[0].get('end')
                if not s or not en: raise SystemExit('invalid surcharge window')
                active={**b,'start':s,'end':en,'connectedTimeFreeMinutes':threshold,'connectedTimePerMinuteAfterFreeEur':rate}
                outside1={**b,'start':'00:00','end':s}; outside2={**b,'start':en,'end':'24:00'}
                p['rules']=[outside1,active,outside2]; after_window+=1
            else:
                p['rules']=[{**b,'scope':'allDay','connectedTimeFreeMinutes':threshold,'connectedTimePerMinuteAfterFreeEur':rate}]; after_plain+=1
        t['runtimePricing']=p
        tr=t.setdefault('runtimeTranslation',{}); tr['enginePrimitiveMappingQa']='existing_v9_primitives_only'; tr['windowCrossingBehavior']='fail_closed_when_nonsegmentable_surcharge_crosses_rule_boundary'
    if ge!=2214 or post!=626 or post_window!=493 or after!=74 or after_window!=63 or after_plain!=11: raise SystemExit(f'count drift ge={ge} post={post}/{post_window} after={after}/{after_window}/{after_plain}')
    leftovers=[]
    for e in d.get('evses') or []:
        t=e.get('tccV9DirectTariff') or {}
        if t.get('operator')!='Go Electric Stations SRLS': continue
        s=json.dumps(t.get('runtimePricing') or {})
        if 'connectedTimeSurcharge' in s or 'activeLocalWindows' in s: leftovers.append(e.get('evseId'))
    if leftovers: raise SystemExit(f'unsupported runtime fields remain {leftovers[:5]}')
    d['dataset']='italy-v9-consolidated-candidate-go-electric-engine-compatible-qa'; d['publicationAllowed']=False
    d['publicationReason']='Go Electric mapped to existing V9 engine primitives; stable builder/engine execution QA required before publication'
    r={'schemaVersion':1,'publicationAllowed':False,'stableActivationAllowed':False,'goElectricEvse':ge,'postChargeOffers':post,'postChargeWindowed':post_window,'onAfterTimeOffers':after,'onAfterTimeWindowed':after_window,'onAfterTimeUnwindowed':after_plain,'unsupportedRuntimeFields':0,'gates':{'goElectric2214':ge==2214,'postCharge626':post==626,'postChargeWindow493':post_window==493,'onAfterTime74':after==74,'onAfterTimeWindow63':after_window==63,'onAfterTimePlain11':after_plain==11,'existingEnginePrimitivesOnly':not leftovers,'publicationDisabled':d['publicationAllowed'] is False}}
    if not all(r['gates'].values()): raise SystemExit(r['gates'])
    write_gz(Path(a.out),d); write_json(Path(a.report),r); print(json.dumps(r,indent=2))
if __name__=='__main__':main()
