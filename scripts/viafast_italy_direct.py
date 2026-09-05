#!/usr/bin/env python3
"""Build a conservative VIAFAST Italy direct-tariff candidate from exact VFS party scope."""
from __future__ import annotations
import argparse,gzip,json
from datetime import datetime,timezone
from pathlib import Path

PARTY='VFS'
SOURCE='https://www.viafast.net/viafast-tariffe/'

def now_iso(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def load(p):
    with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--report',required=True);a=ap.parse_args()
    src=load(a.input); rows=[]; unresolved=[]; stations=set()
    for e in src.get('evses',[]):
        if e.get('partyId')!=PARTY: continue
        stations.add(e.get('stationId'))
        try:p=float(e.get('maxPowerKw'))
        except Exception:p=None
        types={str(c.get('powerType') or '').upper() for c in (e.get('connectors') or [])}
        tariff=None;reason=None
        if any(t.startswith('AC') for t in types) and p is not None and p<=22.5:
            tariff={'pricingType':'flat','currency':'EUR','unit':'kWh','energyEurPerKwh':0.60,'tariffClass':'AC_22','rankable':True}
        elif any(t.startswith('DC') for t in types) and p is not None and 60<=p<=180:
            tariff={'pricingType':'flat','currency':'EUR','unit':'kWh','energyEurPerKwh':0.85,'tariffClass':'DC_60_180','rankable':True}
        else:
            reason='official_viafast_tariff_page_does_not_cover_observed_connector_power_combination'
            unresolved.append({'evseId':e.get('evseId'),'stationId':e.get('stationId'),'maxPowerKw':p,'powerTypes':sorted(types),'reason':reason})
        rows.append({'evseId':e.get('evseId'),'stationId':e.get('stationId'),'partyId':PARTY,'operator':e.get('operator'),'maxPowerKw':p,'connectors':e.get('connectors'),'directTariff':tariff,'rankableDirectTariff':bool(tariff),'blockingReason':reason,'source':SOURCE})
    rankable=sum(x['rankableDirectTariff'] for x in rows)
    payload={'schemaVersion':1,'dataset':'viafast-direct-italy-candidate','generatedAt':now_iso(),'country':'IT','partyId':PARTY,'operator':'VIAFAST','source':SOURCE,'policy':{'ac22EurPerKwh':0.60,'dc60To180EurPerKwh':0.85,'parkingAfterGraceEurPerMinute':0.25,'parkingGraceMinutes':5,'failClosedOutsideOfficialPowerRanges':True},'counts':{'evse':len(rows),'stations':len(stations),'rankableDirectEvse':rankable,'unresolvedEvse':len(unresolved)},'unresolved':unresolved,'evses':rows}
    assert len(rows)==167,(len(rows),); assert rankable==165,(rankable,); assert len(unresolved)==2,unresolved
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode(),compresslevel=9,mtime=0))
    report={k:v for k,v in payload.items() if k!='evses'};rp=Path(a.report);rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload['counts'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
