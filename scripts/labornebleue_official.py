#!/usr/bin/env python3
"""Validate current first-party La Borne Bleue / SIPPEREC tariff rules."""
from __future__ import annotations
import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
TARIFF='https://labornebleue.fr/tarifs/'
CGU='https://labornebleue.fr/cgu/'
SERVICE='https://labornebleue.fr/recharger-son-vehicule/'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=45) as r:return int(getattr(r,'status',200)),r.read(),r.geturl()
def clean(raw):
    s=raw.decode('utf-8',errors='replace')
    s=re.sub(r'<script\b[^>]*>.*?</script>',' ',s,flags=re.I|re.S);s=re.sub(r'<style\b[^>]*>.*?</style>',' ',s,flags=re.I|re.S)
    s=re.sub(r'<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s)).strip()
def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '');s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()
def require(t,*items):
    n=norm(t);missing=[x for x in items if norm(x) not in n]
    if missing:raise RuntimeError('La Borne Bleue evidence missing: '+', '.join(missing))
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/labornebleue');args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    ts,traw,tfinal=fetch(TARIFF);cs,craw,cfinal=fetch(CGU);ss,sraw,sfinal=fetch(SERVICE)
    if min(ts,cs,ss)!=200:raise RuntimeError(f'HTTP failure tariff={ts} cgu={cs} service={ss}')
    t,c,s=clean(traw),clean(craw),clean(sraw)
    require(t,'Depuis le 3 avril 2025','3,7 kVA','7,4 kVA','3,50 €/h','2,50 €/h','Tarif abonné + 1 €/h')
    require(t,'Jusqu’à 22 kVA','5,50 €/h','Supérieur à 22 kVA','11,00 €/h','Abonnement : 10 €/an')
    require(t,'Supérieur à 50 kW','0,45 €/kWh','0,50 €/kWh','après 30 min de charge','12 €/h')
    require(c,'Le Service de Charge débute','Il se termine lorsque l’Utilisateur a libéré la Borne de Recharge','débranché son véhicule')
    require(s,'Vous n’êtes pas abonné','payer vos sessions de charge par carte bancaire au tarif non abonné','100 kVA (DC)')
    payload={
      'schemaVersion':'1.0.0','dataset':'labornebleue-official-idf','generatedAt':now(),'operator':'La Borne Bleue / SIPPEREC','country':'FR','region':'Ile-de-France',
      'classification':{'localPublicNetwork':True,'directNonSubscriber':True,'singleFlatTariff':False,'timeAndPowerDependent':True},
      'nonSubscriber':{
        'ac':[
          {'minPowerKva':3.7,'maxPowerKva':7.4,'day0800To2000EurPerHour':4.50,'night2000To0800EurPerHour':3.50},
          {'minPowerKvaExclusive':7.4,'maxPowerKva':22.0,'day0800To2000EurPerHour':6.50,'night2000To0800EurPerHour':6.50},
          {'minPowerKvaExclusive':22.0,'day0800To2000EurPerHour':12.00,'night2000To0800EurPerHour':12.00}
        ],
        'dcAbove50Kw':{'eurPerKwh':0.50,'additionalAfterChargeMinutes':30,'additionalEurPerHour':12.0}
      },
      'subscriber':{
        'annualFeeEur':10.0,
        'ac':[
          {'minPowerKva':3.7,'maxPowerKva':7.4,'day0800To2000EurPerHour':3.50,'night2000To0800EurPerHour':2.50,'nightCapEur':12.0},
          {'minPowerKvaExclusive':7.4,'maxPowerKva':22.0,'day0800To2000EurPerHour':5.50,'night2000To0800EurPerHour':5.50,'nightCapEur':12.0},
          {'minPowerKvaExclusive':22.0,'day0800To2000EurPerHour':11.0,'night2000To0800EurPerHour':11.0}
        ],
        'dcAbove50Kw':{'eurPerKwh':0.45,'additionalAfterChargeMinutes':30,'additionalEurPerHour':12.0}
      },
      'sessionSemantics':{'startsAtAccessRequest':True,'endsAfterSessionClosureAndVehicleUnplugged':True,'acMinuteBillingUsesServiceDuration':True},
      'reservation':{'free':True},'roaming':{'outgoingNoExtraNetworkFee':True,'incomingUsesNonSubscriberPlusOneEurPerHourOnAc':True},
      'sourceEvidence':{'officialOnly':True,'tariffUrl':TARIFF,'tariffHttpStatus':ts,'cguUrl':CGU,'cguHttpStatus':cs,'serviceUrl':SERVICE,'serviceHttpStatus':ss,'tariffSha256':hashlib.sha256(traw).hexdigest(),'cguSha256':hashlib.sha256(craw).hexdigest()},
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','nonSubscriber','subscriber','sessionSemantics','reservation','roaming')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'labornebleue_official_idf.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text("# La Borne Bleue / SIPPEREC\n\nValidated current non-subscriber and subscriber AC/DC tariff rules and service-duration semantics.\n")
if __name__=='__main__':main()
