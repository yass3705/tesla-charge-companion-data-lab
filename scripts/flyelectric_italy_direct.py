#!/usr/bin/env python3
"""Build exact FLY party direct tariff candidate from flyElectric's current own-network tariff."""
from __future__ import annotations
import argparse,gzip,json
from datetime import datetime,timezone
from pathlib import Path
PARTY='FLY'; PRICE=0.69; SOURCE='https://flyelectric.it/home'
def now_iso():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--report',required=True);a=ap.parse_args()
 with gzip.open(a.input,'rt',encoding='utf-8') as f:src=json.load(f)
 es=[e for e in src.get('evses',[]) if e.get('partyId')==PARTY];st={e.get('stationId') for e in es}
 rows=[]
 for e in es:
  rows.append({'evseId':e.get('evseId'),'stationId':e.get('stationId'),'partyId':PARTY,'operator':e.get('operator'),'maxPowerKw':e.get('maxPowerKw'),'connectors':e.get('connectors'),'operationalState':e.get('operationalState'),'sourceStatus':e.get('sourceStatus'),'directTariff':{'pricingType':'flat','currency':'EUR','unit':'kWh','energyEurPerKwh':PRICE,'tariffClass':'FLYELECTRIC_OWN_NETWORK','rankable':True},'rankableDirectTariff':True,'source':SOURCE})
 payload={'schemaVersion':1,'dataset':'flyelectric-direct-italy-candidate','generatedAt':now_iso(),'country':'IT','partyId':PARTY,'operator':'flyElectric','source':SOURCE,'policy':{'ownNetworkEurPerKwh':PRICE,'roamingTariffExcluded':True,'exactPartyIdScope':True,'failClosed':True},'counts':{'evse':len(rows),'stations':len(st),'rankableDirectEvse':len(rows),'unresolvedEvse':0},'evses':rows}
 assert len(rows)==50,payload['counts']; assert len(st)==29,payload['counts']
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode(),compresslevel=9,mtime=0))
 report={k:v for k,v in payload.items() if k!='evses'};rp=Path(a.report);rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload['counts'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
