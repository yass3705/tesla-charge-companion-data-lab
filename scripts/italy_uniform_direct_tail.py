#!/usr/bin/env python3
"""Build conservative direct tariffs for smaller Italian CPOs with published network/type tariffs."""
from __future__ import annotations
import argparse,gzip,json
from datetime import datetime,timezone
from pathlib import Path

SOURCES={
 'CVG':'https://convergenze.it/it/servizi/energia/evo',
 'CGS':'https://www.cogeserenergia.it/it/punti-di-ricarica-ad-uso-pubblico',
 'A22':'https://www.autobrennero.it/it/in-viaggio/sosta-e-servizi/aree-di-servizio/?t=colonnine-elettriche',
}

def now_iso():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def load(p):
 with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
def power_types(e):return {str(c.get('powerType') or '').upper() for c in (e.get('connectors') or [])}
def flat(v,cls):return {'pricingType':'flat','currency':'EUR','unit':'kWh','energyEurPerKwh':v,'tariffClass':cls,'rankable':True}
def tariff(e):
 p=e.get('partyId'); t=power_types(e)
 try:w=float(e.get('maxPowerKw'))
 except Exception:w=None
 ac=any(x.startswith('AC') for x in t);dc=any(x.startswith('DC') for x in t)
 if p=='CVG': return flat(0.60,'EVO_NETWORK')
 if p=='CGS':
  if ac:return flat(0.67,'COGESER_QUICK_AC')
  return None
 if p=='A22':
  if ac and w is not None and w<=22.5:return flat(0.33,'A22_STANDARD_AC')
  if ac and w is not None and 22.5<w<=43.5:return flat(0.38,'A22_MULTISTANDARD_AC')
  if dc and w is not None and w<=50.5:return flat(0.38,'A22_MULTISTANDARD_DC')
  if dc and w is not None and 50.5<w<=180:return flat(0.43,'A22_ULTRAFAST')
 return None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--report',required=True);a=ap.parse_args();src=load(a.input)
 rows=[];un=[];counts={}
 for party in ('CVG','CGS','A22'):
  es=[e for e in src.get('evses',[]) if e.get('partyId')==party];st={e.get('stationId') for e in es};rank=0
  for e in es:
   tt=tariff(e);reason=None
   if tt:rank+=1
   else:
    reason='published_network_tariff_does_not_safely_cover_observed_connector_or_power'
    un.append({'partyId':party,'evseId':e.get('evseId'),'stationId':e.get('stationId'),'maxPowerKw':e.get('maxPowerKw'),'powerTypes':sorted(power_types(e)),'reason':reason})
   rows.append({'partyId':party,'evseId':e.get('evseId'),'stationId':e.get('stationId'),'operator':e.get('operator'),'maxPowerKw':e.get('maxPowerKw'),'connectors':e.get('connectors'),'directTariff':tt,'rankableDirectTariff':bool(tt),'blockingReason':reason,'source':SOURCES[party]})
  counts[party]={'evse':len(es),'stations':len(st),'rankableDirectEvse':rank,'unresolvedEvse':len(es)-rank}
 payload={'schemaVersion':1,'dataset':'italy-uniform-direct-tail-candidate','generatedAt':now_iso(),'country':'IT','sources':SOURCES,'policy':{'failClosed':True,'exactPartyIdScope':True},'counts':{'operators':3,'evse':len(rows),'rankableDirectEvse':sum(x['rankableDirectEvse'] for x in counts.values()),'unresolvedEvse':len(un),'byOperator':counts},'unresolved':un,'evses':rows}
 assert counts['CVG']=={'evse':90,'stations':44,'rankableDirectEvse':90,'unresolvedEvse':0},counts
 assert counts['CGS']=={'evse':60,'stations':27,'rankableDirectEvse':59,'unresolvedEvse':1},counts
 assert counts['A22']=={'evse':80,'stations':17,'rankableDirectEvse':74,'unresolvedEvse':6},counts
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode(),compresslevel=9,mtime=0))
 report={k:v for k,v in payload.items() if k!='evses'};rp=Path(a.report);rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload['counts'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
