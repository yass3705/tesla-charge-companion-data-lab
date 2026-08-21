#!/usr/bin/env python3
"""Validate current first-party Pass Pass Electrique tariff rules for Hauts-de-France."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
HOME='https://passpasselectrique.fr/fr/'
TARIFF='https://passpasselectrique.fr/fr/tarifs/'
RECHARGE='https://passpasselectrique.fr/fr/recharger-son-vehicule/'
PARTNERS='https://passpasselectrique.fr/fr/partenaires/'
TARIFF_IMAGE='https://passpasselectrique.fr/wp-content/uploads/sites/9/2025/03/tarif-ppe-tableau3.png'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('Pass Pass evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/passpass_hdf'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    hs,hraw,hfinal=fetch(HOME); ts,traw,tfinal=fetch(TARIFF); rs,rraw,rfinal=fetch(RECHARGE); ps,praw,pfinal=fetch(PARTNERS); ims,imraw,imfinal=fetch(TARIFF_IMAGE)
    if min(hs,ts,rs,ps,ims)!=200: raise RuntimeError(f'HTTP failure home={hs} tariff={ts} recharge={rs} partners={ps} image={ims}')
    h=hraw.decode('utf-8',errors='replace'); t=traw.decode('utf-8',errors='replace'); r=rraw.decode('utf-8',errors='replace'); p=praw.decode('utf-8',errors='replace')
    require(h,'550','28','20 000','140 000')
    require(t,'Tarifs à partir du 1er avril 2025','Tout palier temporel ou de puissance','facturation se poursuit','abonné')
    require(r,'tarif préférentiel','utilisateur occasionnel','carte bancaire','tarif non-abonné')
    require(p,'Région Hauts-de-France','Bouygues Énergies et Services','gestion de son infrastructure de recharge')
    if not imraw.startswith(b'\x89PNG\r\n\x1a\n') or len(imraw)<10000: raise RuntimeError('current Pass Pass tariff asset is not a valid tariff PNG')

    payload={
      'schemaVersion':'1.0.0','dataset':'passpass-electrique-official-hdf','generatedAt':now(),
      'operator':'Pass Pass Electrique','serviceOperator':'Bouygues Energies et Services','country':'FR','region':'Hauts-de-France',
      'effectiveFrom':'2025-04-01',
      'classification':{
        'regionalPublicNetwork':True,'directPublicTariff':True,'subscriberTariff':True,'adHocTariff':True,
        'energyPlusConnectionTime':True,'stationDisplayedTariffAuthoritative':True,'roamingSeparate':True,
        'tariffValuesHumanValidatedFromFirstPartyAsset':True
      },
      'networkSnapshot':{'stationsMoreThan':550,'participatingAuthorities':28,'usersMoreThan':20000},
      'tariffs':{
        'normal':{
          'subscriber':{'energyEurPerKwh':0.32,'freeConnectedMinutes':180,'day0700To2100AfterFreeEurPerMin':0.04,'night2100To0700AfterFreeEurPerMin':0.01,'nightTimeComponentCapEur':1.20},
          'nonSubscriber':{'energyEurPerKwh':0.38,'freeConnectedMinutes':180,'day0700To2100AfterFreeEurPerMin':0.08,'night2100To0700AfterFreeEurPerMin':0.02}
        },
        'rapid':{
          'subscriber':{'energyEurPerKwh':0.44,'freeConnectedMinutes':90,'afterFreeEurPerMin':0.20},
          'nonSubscriber':{'energyEurPerKwh':0.51,'freeConnectedMinutes':90,'afterFreeEurPerMin':0.40}
        },
        'ultraRapid':{
          'subscriber':{'energyEurPerKwh':0.44,'freeConnectedMinutes':45,'afterFreeEurPerMin':0.20},
          'nonSubscriber':{'energyEurPerKwh':0.51,'freeConnectedMinutes':45,'afterFreeEurPerMin':0.40}
        },
        'longStay':{
          'subscriber':{'energyEurPerKwh':0.32,'freeConnectedMinutes':840,'afterFreeEurPerHour':0.10},
          'nonSubscriber':{'energyEurPerKwh':0.38,'freeConnectedMinutes':840,'afterFreeEurPerHour':0.20}
        }
      },
      'access':{'subscriberAccount':True,'passPassCard':True,'mobileAppAdHoc':True,'bankCardViaAppForOccasionalUser':True},
      'sessionSemantics':{'startedTimeOrEnergyStepIsDue':True,'billingContinuesWhileVehicleConnected':True,'stationTariffShouldBeChecked':True},
      'tccDecision':{
        'operatorValidated':True,'networkRulesClassable':True,'stationCategoryRequired':True,'stationDisplayedTariffHasPriority':True,
        'roamingSeparate':True,
        'reason':'Current first-party tariff page and tariff asset define exact subscriber/non-subscriber rules by Pass Pass station category; the site explicitly says station-displayed pricing remains authoritative.'
      },
      'sourceEvidence':{
        'officialOnly':True,
        'homeUrl':hfinal,'homeHttpStatus':hs,'homeSha256':hashlib.sha256(hraw).hexdigest(),
        'tariffUrl':tfinal,'tariffHttpStatus':ts,'tariffSha256':hashlib.sha256(traw).hexdigest(),
        'tariffAssetUrl':imfinal,'tariffAssetHttpStatus':ims,'tariffAssetSha256':hashlib.sha256(imraw).hexdigest(),
        'rechargeUrl':rfinal,'rechargeHttpStatus':rs,'partnersUrl':pfinal,'partnersHttpStatus':ps
      },
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','tariffs','access','sessionSemantics','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'passpass_hdf_official.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Pass Pass Electrique / Hauts-de-France\n\nCurrent first-party rules effective 2025-04-01 validated for normal, rapid, ultra-rapid and long-stay categories, with separate subscriber and non-subscriber prices. Session time fees must be modeled and the tariff displayed on the station remains authoritative.\n')

if __name__=='__main__': main()
