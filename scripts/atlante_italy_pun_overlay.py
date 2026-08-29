#!/usr/bin/env python3
"""Build Atlante Go Italy subscription overlay on authoritative PUN ATE EVSE inventory."""
from __future__ import annotations
import argparse, gzip, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PARTY="ATE"
PRICE=0.49

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pun',required=True); ap.add_argument('--offers',default='data/reference/atlante_italy_offers.json'); ap.add_argument('--out',default='data/national/atlante_go_italy_overlay.json.gz'); ap.add_argument('--report',default='data/reports/atlante_italy_pun_overlay_report.json'); a=ap.parse_args()
    with gzip.open(a.pun,'rt',encoding='utf-8') as f: pun=json.load(f)
    offers=json.loads(Path(a.offers).read_text(encoding='utf-8'))
    go=next(x for x in offers['subscriptions'] if x['id']=='atlante_go')
    assert abs(float(go['countryTariffs']['IT']['ATLANTE'])-PRICE)<1e-9
    evses=[]
    for e in pun.get('evses',[]):
        if str(e.get('partyId') or '').upper()!=PARTY: continue
        evses.append({
          'evseId':e.get('evseId'),'stationId':e.get('stationId'),'partyId':PARTY,
          'operationalState':e.get('operationalState'),'occupancyState':e.get('occupancyState'),
          'sourceStatus':e.get('sourceStatus'),'coordinates':e.get('coordinates'),'maxPowerKw':e.get('maxPowerKw'),
          'subscriptionTariffs':[{'subscriptionId':'atlante_go','country':'IT','network':'Atlante','energyEurPerKwh':PRICE,'rankableWhenSubscriptionSelected':True}]
        })
    if len(evses)<500: raise RuntimeError(f'Unexpectedly small PUN ATE inventory: {len(evses)}')
    states=Counter(str(x.get('operationalState') or 'unknown') for x in evses)
    stations={x.get('stationId') for x in evses if x.get('stationId')}
    payload={'schemaVersion':1,'generatedAt':now(),'country':'IT','operator':'Atlante','punPartyId':PARTY,'layerType':'subscription_overlay','subscription':{'id':'atlante_go','monthlyFeeEur':go['monthlyFeeEur'],'energyEurPerKwh':PRICE,'appliesTo':'all PUN ATE EVSE in Italy when user selects Atlante Go'},'counts':{'evse':len(evses),'stations':len(stations),'operationalStateCounts':dict(sorted(states.items()))},'evses':evses}
    report={'generatedAt':now(),'counts':payload['counts'],'qualityGates':{'punAteInventoryNonzero':len(evses)>0,'allRowsAte':all(x['partyId']==PARTY for x in evses),'allRowsHaveRankableSelectedSubscriptionTariff':all(x['subscriptionTariffs'][0]['rankableWhenSubscriptionSelected'] and x['subscriptionTariffs'][0]['energyEurPerKwh']==PRICE for x in evses)},'directPayAsYouGoRankable':False}
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); rendered=json.dumps(payload,ensure_ascii=False,indent=2)+'\n'; Path(a.out).write_bytes(gzip.compress(rendered.encode(),compresslevel=9,mtime=0))
    Path(a.report).parent.mkdir(parents=True,exist_ok=True); Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
