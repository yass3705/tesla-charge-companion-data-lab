#!/usr/bin/env python3
"""Build Atlante Go Italy ChargeLeague overlay without overwriting CPO direct tariffs."""
from __future__ import annotations
import argparse,gzip,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

PRICE=0.59
PARTNERS={'Electra':'ELECTRA','Fastned':'FASTNED','IONITY':'IONITY'}
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pun',required=True); ap.add_argument('--offers',default='data/reference/atlante_italy_offers.json'); ap.add_argument('--out',default='data/national/atlante_go_chargeleague_italy_overlay.json.gz'); ap.add_argument('--report',default='data/reports/atlante_go_chargeleague_italy_report.json'); a=ap.parse_args()
    with gzip.open(a.pun,'rt',encoding='utf-8') as f:p=json.load(f)
    offers=json.loads(Path(a.offers).read_text()); go=next(x for x in offers['subscriptions'] if x['id']=='atlante_go'); assert float(go['countryTariffs']['IT']['CHARGELEAGUE'])==PRICE
    evses=[]; party_by_partner=defaultdict(Counter); states=defaultdict(Counter)
    for e in p.get('evses',[]):
        op=str(e.get('operator') or '')
        label=next((n for n,k in PARTNERS.items() if k in op.upper()),None)
        if not label: continue
        party=str(e.get('partyId') or '').upper(); party_by_partner[label][party]+=1; states[label][str(e.get('operationalState') or 'unknown')]+=1
        evses.append({'evseId':e.get('evseId'),'stationId':e.get('stationId'),'operator':op,'partyId':party,'operationalState':e.get('operationalState'),'occupancyState':e.get('occupancyState'),'sourceStatus':e.get('sourceStatus'),'coordinates':e.get('coordinates'),'maxPowerKw':e.get('maxPowerKw'),'subscriptionTariffs':[{'subscriptionId':'atlante_go','provider':'Atlante','serviceNetwork':'ChargeLeague','energyEurPerKwh':PRICE,'rankableWhenSubscriptionSelected':True,'mustNotOverwriteCpoDirectTariff':True}]})
    ambiguous={k:dict(v) for k,v in party_by_partner.items() if len(v)>1}
    if ambiguous: raise RuntimeError(f'Ambiguous ChargeLeague PUN party mapping: {ambiguous}')
    counts={k:{'evse':sum(party_by_partner[k].values()),'partyIdCounts':dict(party_by_partner[k]),'operationalStateCounts':dict(states[k])} for k in PARTNERS}
    payload={'schemaVersion':1,'generatedAt':now(),'country':'IT','serviceProvider':'Atlante','subscriptionId':'atlante_go','layerType':'cross_cpo_subscription_overlay','energyEurPerKwh':PRICE,'partners':list(PARTNERS),'counts':{'totalEvse':len(evses),'byPartner':counts},'precedence':{'overwritesCpoDirectTariff':False,'appliesOnlyWhenSubscriptionSelected':True},'evses':evses}
    report={'generatedAt':now(),'counts':payload['counts'],'qualityGates':{'noAmbiguousPartnerPartyMapping':not ambiguous,'allTariffsSelectedSubscriptionOnly':all(x['subscriptionTariffs'][0]['rankableWhenSubscriptionSelected'] for x in evses),'directTariffsNotOverwritten':all(x['subscriptionTariffs'][0]['mustNotOverwriteCpoDirectTariff'] for x in evses)},'partyIds':{k:list(v.keys()) for k,v in party_by_partner.items()}}
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); s=json.dumps(payload,ensure_ascii=False,indent=2)+'\n'; Path(a.out).write_bytes(gzip.compress(s.encode(),compresslevel=9,mtime=0)); Path(a.report).parent.mkdir(parents=True,exist_ok=True); Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
