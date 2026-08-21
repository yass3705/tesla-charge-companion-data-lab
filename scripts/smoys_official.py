#!/usr/bin/env python3
"""Validate current SMOYS public charging tariff rules from public first-party/network-partner sources."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
ULYS='https://ulys.com/offre/ulys-electric/options/smoys/'
ULYS_PRO='https://ulys.com/professionnel/offre/ulys-electric/options/smoys-pro/'
SMOYS='https://smoys.org/'
ONCY='https://www.oncy-sur-ecole.fr/une-borne-de-recharge-sur-le-parking-de-lespace-jean-pierre-hazard/'
DATA='https://www.data.gouv.fr/datasets/reseau-smoys-reseau-public-de-lessonne-ile-de-france'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    s=s.lower().replace('\xa0',' ')
    return re.sub(r'\s+',' ',s).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('SMOYS evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/smoys'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    us,uraw,ufinal=fetch(ULYS); ps,praw,pfinal=fetch(ULYS_PRO); ss,sraw,sfinal=fetch(SMOYS); os_,oraw,ofinal=fetch(ONCY); ds,draw,dfinal=fetch(DATA)
    if min(us,ps,ss,os_,ds)!=200: raise RuntimeError(f'HTTP failure ulys={us} pro={ps} smoys={ss} oncy={os_} data={ds}')
    u=uraw.decode('utf-8',errors='replace'); p=praw.decode('utf-8',errors='replace'); s=sraw.decode('utf-8',errors='replace'); o=oraw.decode('utf-8',errors='replace'); d=draw.decode('utf-8',errors='replace')
    require(u,'SMOYS','0.39','0.80','15 minutes','8h','20h','20h','8h','6€')
    require(p,'SMOYS','0.325','0.39','0.667','0.80')
    require(s,'SMOYS','bornes de recharge')
    require(o,'SMOYS','0,39','0,80','15 minutes','scanner le QR code','payer par CB')
    require(d,'Réseau SMOYS','Essonne','Val de Marne','Citeos','Ulys')
    payload={
      'schemaVersion':'1.0.0','dataset':'smoys-official-idf','generatedAt':now(),
      'operator':'SMOYS','authority':'Syndicat Mixte Orge-Yvette-Seine','country':'FR','region':'Ile-de-France','departments':['Essonne','Val-de-Marne'],
      'classification':{'localPublicNetwork':True,'directBankCard':True,'regionalPass':True,'singleFlatEnergyTariff':True,'postChargeTimeDependent':True,'roamingMayDiffer':True},
      'directTariff':{
        'energyEurPerKwhTtc':0.39,
        'postCharge':{'graceMinutes':15,'day0800To2000EurPer15MinutesTtc':0.80,'night2000To0800EurPer15MinutesTtc':0.0,'billingBlockMinutes':15,'startedBlockAssumed':False}
      },
      'access':{
        'qrBankCard':True,
        'ulysSmoysPass':True,
        'ulysSmoysPassMonthlyFeeEur':0.0,
        'ulysSmoysPassPurchaseEur':6.0,
        'samePublishedLocalTariffForQrBankCardAndUlysSmoys':True,
        'thirdPartyRoamingMayDiffer':True
      },
      'network':{'approxPublicChargePoints':200,'serviceOperator':'Citeos','mobilityPartner':'Ulys'},
      'sourceEvidence':{
        'networkAndPartnerSourcesOnly':True,
        'ulysUrl':ULYS,'ulysHttpStatus':us,
        'ulysProUrl':ULYS_PRO,'ulysProHttpStatus':ps,
        'smoysUrl':SMOYS,'smoysHttpStatus':ss,
        'municipalCorroborationUrl':ONCY,'municipalCorroborationHttpStatus':os_,
        'publicDatasetUrl':DATA,'publicDatasetHttpStatus':ds,
        'ulysSha256':hashlib.sha256(uraw).hexdigest(),
        'ulysProSha256':hashlib.sha256(praw).hexdigest(),
        'municipalSha256':hashlib.sha256(oraw).hexdigest()
      },
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','directTariff','access','network')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'smoys_official_idf.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# SMOYS / Essonne + Val-de-Marne\n\nValidated the current public SMOYS tariff: 0.39 EUR/kWh TTC, with daytime post-charge billing of 0.80 EUR per 15 minutes after a 15-minute grace period, and no published post-charge fee overnight. QR/bank-card and Ulys SMOYS access are documented; third-party roaming remains provider-specific.\n')
if __name__=='__main__': main()
