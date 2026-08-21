#!/usr/bin/env python3
"""Validate current Territoire d'Energie Somme public charging tariff."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
MOBILITY='https://www.te80.fr/nos-actions/amenagement-du-territoire/mobilite-propre'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('TE80 evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/te80_somme'); args=ap.parse_args()
    status,raw,final=fetch(MOBILITY)
    if status!=200: raise RuntimeError(f'HTTP failure mobility={status}')
    text=raw.decode('utf-8',errors='replace')
    require(text,'Tarifs publics','28 janvier 2026','0,45','0,012','19h','9h','0,003','50kW','0,55','0,05','207 bornes','412 points','FRESHMILE')
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    payload={
      'schemaVersion':'1.0.0','dataset':'te80-somme-official-hdf','generatedAt':now(),
      'operator':'Territoire d’Energie Somme (TE80)','legacyName':'FDE80','serviceOperator':'Freshmile','country':'FR','region':'Hauts-de-France','department':'Somme','effectiveFrom':'2026-01-28',
      'classification':{'departmentalPublicNetwork':True,'directPublicTariff':True,'energyPlusConnectionTime':True,'powerDependentTariff':True,'roamingSeparate':True},
      'tariffs':{
        'power3To22Kw':{'energyEurPerKwh':0.45},
        'station7Kw':{'connectionTimeFeeEurPerMin':0.0},
        'stationWith22KwPoint':{'freeConnectedMinutes':120,'day0900To1900AfterFreeEurPerMin':0.012,'night1900To0900AfterFreeEurPerMin':0.003,'billingStep':'started_minute'},
        'rapid50Kw':{'energyEurPerKwh':0.55,'freeConnectedMinutes':60,'afterFreeEurPerMin':0.05,'billingStep':'started_minute'}
      },
      'access':{'compatibleMobilityCard':True,'freshmileApp':True,'roamingOperatorMayAddOwnFees':True},
      'networkSnapshot':{'stationsMoreThan':207,'chargePoints':412},
      'sessionSemantics':{'timeFeeDependsOnStationPowerClass':True,'22KwRuleAlsoAppliesWhenUsing3KwSocketOn22KwStation':True},
      'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'stationPowerClassRequired':True,'roamingSeparate':True,'reason':'TE80 currently publishes exact energy and connection-time rules effective 2026-01-28; Freshmile operates the network and roaming mobility providers may apply separate fees.'},
      'sourceEvidence':{'officialOnly':True,'mobilityUrl':final,'mobilityHttpStatus':status,'mobilitySha256':hashlib.sha256(raw).hexdigest()},
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','tariffs','access','sessionSemantics','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'te80_somme_official_hdf.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Territoire d’Energie Somme / TE80\n\nCurrent tariff effective 2026-01-28 validated: 0.45 EUR/kWh for 3-22 kW, with connection-time rules by station class, and 0.55 EUR/kWh for 50 kW plus 0.05 EUR/min after 60 minutes. Freshmile operates the network; roaming prices remain separate.\n')

if __name__=='__main__': main()
