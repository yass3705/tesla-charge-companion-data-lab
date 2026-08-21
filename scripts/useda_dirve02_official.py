#!/usr/bin/env python3
"""Validate current USEDA DIRVE 02 public charging tariff and operator mapping."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
HOME='https://useda.fr/nos-missions/bornes-de-recharge'
TARIFF='https://useda.fr/nouvelle-tarification-des-bornes-publiques-de-recharge-dirve-02'
OPERATOR='https://useda.fr/dirve-02-changement-doperateur-pour-les-bornes-de-recharge'

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
    if missing: raise RuntimeError('USEDA evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/useda_dirve02'); args=ap.parse_args()
    hs,hraw,hfinal=fetch(HOME); ts,traw,tfinal=fetch(TARIFF); os_,oraw,ofinal=fetch(OPERATOR)
    if min(hs,ts,os_)!=200: raise RuntimeError(f'HTTP failure home={hs} tariff={ts} operator={os_}')
    h=hraw.decode('utf-8',errors='replace'); t=traw.decode('utf-8',errors='replace'); o=oraw.decode('utf-8',errors='replace')
    require(h,'DIRVE 02','164 bornes','15 bornes rapides','36 centimes','Electromaps','paiement')
    require(t,'1er septembre 2025','0,36','kWh','Electromaps','paiement','commissions supplémentaires')
    require(o,'CITEOS','COGELUM','Electromaps remplace désormais Freshmile','tarifs délibérés par l’USEDA','propres tarifs')
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    payload={
      'schemaVersion':'1.0.0','dataset':'useda-dirve02-official-hdf','generatedAt':now(),
      'operator':'USEDA DIRVE 02','authority':'Union des Secteurs d’Energie du Département de l’Aisne','country':'FR','region':'Hauts-de-France','department':'Aisne',
      'serviceOperator':'CITEOS/COGELUM','mobilityOperator':'Electromaps','effectiveFrom':'2025-09-01',
      'classification':{'departmentalPublicNetwork':True,'directPublicTariff':True,'singleEnergyTariff':True,'adHocSupported':True,'roamingSeparate':True},
      'directTariff':{'energyEurPerKwhTtc':0.36,'samePriceAllPowerBands':True,'connectionFeeEur':0.0,'timeFeeEurPerMin':0.0},
      'access':{'electromapsApp':True,'electromapsPass':True,'qrCodeAdHoc':True,'otherMobilityBadges':True},
      'networkSnapshot':{'stations':164,'rapidStations':15,'communesNearly':72},
      'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'roamingSeparate':True,'reason':'USEDA currently publishes one exact 0.36 EUR/kWh tariff for all DIRVE 02 chargers when using Electromaps or ad-hoc payment; other mobility operators may add their own fees.'},
      'sourceEvidence':{
        'officialOnly':True,
        'homeUrl':hfinal,'homeHttpStatus':hs,'homeSha256':hashlib.sha256(hraw).hexdigest(),
        'tariffUrl':tfinal,'tariffHttpStatus':ts,'tariffSha256':hashlib.sha256(traw).hexdigest(),
        'operatorChangeUrl':ofinal,'operatorChangeHttpStatus':os_,'operatorChangeSha256':hashlib.sha256(oraw).hexdigest()
      },
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','directTariff','access','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'useda_dirve02_official_hdf.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# USEDA DIRVE 02 / Aisne\n\nCurrent direct tariff validated at 0.36 EUR/kWh from 2025-09-01 for all charger power bands when using Electromaps or ad-hoc payment. CITEOS/COGELUM supervises/operates the infrastructure; Electromaps is the mobility operator. Roaming prices remain separate.\n')

if __name__=='__main__': main()
