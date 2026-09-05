#!/usr/bin/env python3
"""Build current Magis (former AGSM AIM Smart Solutions) own-network subscription applicability.

The current Magis public site publishes subscription fees and discounted energy rates.
The base pay-per-use rate is intentionally not inferred because the current site directs
users to the app for that value.
"""
from __future__ import annotations
import argparse,gzip,json
from datetime import datetime,timezone
from pathlib import Path
PARTY='ASS'; SOURCE='https://www.magissmart.it/agsmaim_e-mobility/abbonamenti'
OFFERS=[
 {'id':'magis-small-ac','name':'Small','monthlyFeeEur':5.0,'rates':{'AC':0.60}},
 {'id':'magis-medium-ac','name':'Medium','monthlyFeeEur':10.0,'rates':{'AC':0.58}},
 {'id':'magis-large-ac','name':'Large','monthlyFeeEur':20.0,'rates':{'AC':0.50}},
 {'id':'magis-flat-dc','name':'Flat DC','monthlyFeeEur':10.0,'rates':{'DC':0.74}},
 {'id':'magis-small-plus-dc','name':'Small + Flat DC','monthlyFeeEur':15.0,'rates':{'AC':0.60,'DC':0.74}},
 {'id':'magis-medium-plus-dc','name':'Medium + Flat DC','monthlyFeeEur':20.0,'rates':{'AC':0.58,'DC':0.74}},
 {'id':'magis-large-plus-dc','name':'Large + Flat DC','monthlyFeeEur':30.0,'rates':{'AC':0.50,'DC':0.74}},
]
def now_iso():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def kind(e):
 types={str(c.get('powerType') or '').upper() for c in (e.get('connectors') or [])}
 if any(x.startswith('DC') for x in types):return 'DC'
 if any(x.startswith('AC') for x in types):return 'AC'
 return None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--report',required=True);a=ap.parse_args()
 with gzip.open(a.input,'rt',encoding='utf-8') as f:src=json.load(f)
 es=[e for e in src.get('evses',[]) if e.get('partyId')==PARTY];st={e.get('stationId') for e in es};rows=[];unknown=[]
 for e in es:
  k=kind(e); ids=[o['id'] for o in OFFERS if k in o['rates']] if k else []
  if not ids:unknown.append({'evseId':e.get('evseId'),'stationId':e.get('stationId'),'reason':'connector_power_type_unresolved'})
  rows.append({'evseId':e.get('evseId'),'stationId':e.get('stationId'),'partyId':PARTY,'operator':e.get('operator'),'currentOperatorAlias':'Magis Smart','connectorClass':k,'applicableSubscriptionOfferIds':ids,'basePayPerUseTariff':None,'basePayPerUseBlockingReason':'current_base_pay_per_use_value_is_app_only_and_not_inferred','source':SOURCE})
 payload={'schemaVersion':1,'dataset':'magis-italy-uniform-subscriptions','generatedAt':now_iso(),'country':'IT','partyId':PARTY,'identity':{'snapshotOperator':'AGSM AIM Smart Solutions','currentOperator':'Magis Smart','renameEffective':'2026-03-01'},'source':SOURCE,'policy':{'subscriptionsPublished':True,'basePayPerUsePublished':False,'basePayPerUseFailClosed':True,'exactPartyIdScope':True},'subscriptionOffers':OFFERS,'counts':{'evse':len(rows),'stations':len(st),'evseWithApplicableSubscription':sum(bool(r['applicableSubscriptionOfferIds']) for r in rows),'unresolvedConnectorClass':len(unknown)},'unresolved':unknown,'evses':rows}
 assert len(rows)==258,payload['counts'];assert len(st)==135,payload['counts']
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode(),compresslevel=9,mtime=0))
 report={k:v for k,v in payload.items() if k!='evses'};rp=Path(a.report);rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload['counts'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
