#!/usr/bin/env python3
"""Validate Chargelec36 network/access and current public tariff evidence conservatively."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
HOME='https://www.chargelec36.com/'
REG='https://www.chargelec36.com/registration/index'
STATIONS='https://www.chargelec36.com/station/index'
GUIDE='https://www.chargelec36.com/media/ModeEmploi.pdf'
DATA='https://www.data.gouv.fr/datasets/infrastructure-de-recharge-de-vehicules-electriques-irve'
VERIFY_STALE=Path('data/station_verifications/chargelec36_chateauroux_jules_chauvin_negative_2026_08_22.json')
VERIFY_COLBERT=Path('data/station_verifications/chargelec36_chateauroux_colbert_2026_08_22.json')
TOURISM=[
 'https://www.destinationvalleedelacreuse.fr/offres/borne-de-charge-electrique-pour-voiture-et-velo-8/',
 'https://www.destinationvalleedelacreuse.fr/offres/borne-de-charge-electrique-pour-voiture-et-velo-7/',
 'https://www.destinationvalleedelacreuse.fr/offres/borne-de-charge-electrique-pour-voiture-et-velo-2/'
]

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
    if missing: raise RuntimeError('Chargelec36 evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/chargelec36'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    hs,hraw,hfinal=fetch(HOME); rs,rraw,rfinal=fetch(REG); ss,sraw,sfinal=fetch(STATIONS); gs,graw,gfinal=fetch(GUIDE); ds,draw,dfinal=fetch(DATA)
    if min(hs,rs,ss,gs,ds)!=200: raise RuntimeError(f'HTTP failure home={hs} registration={rs} stations={ss} guide={gs} data={ds}')
    h=hraw.decode('utf-8',errors='replace'); r=rraw.decode('utf-8',errors='replace'); s=sraw.decode('utf-8',errors='replace'); d=draw.decode('utf-8',errors='replace')
    require(h,'Chargelec36')
    require(r,'Formule Grand Public','Prices','calameo')
    require(s,'Réseau SDEI36','ARGENTON','CHATEAUROUX','ISSOUDUN','VALENCAY','CHATEAUROUX - Colbert')
    require(d,'Chargelec','CHARGELEC / SDEI 36','28 janvier 2026')

    if not VERIFY_STALE.exists(): raise RuntimeError(f'missing manual station verification {VERIFY_STALE}')
    stale=json.loads(VERIFY_STALE.read_text())
    if stale.get('operator')!='Chargelec36 / SDEI36': raise RuntimeError('manual Chargelec36 stale verification operator mismatch')
    decision=stale.get('decision',{})
    if decision.get('excludeAsLiveStationWitness') is not True or decision.get('doNotUseForTariffValidation') is not True:
        raise RuntimeError('Jules Chauvin manual verification is not marked excluded')
    current_candidate_present='jules chauvin' in norm(s)
    if current_candidate_present:
        raise RuntimeError('Rue Jules Chauvin has reappeared in the current first-party station directory; manual stale exclusion must be reviewed')

    if not VERIFY_COLBERT.exists(): raise RuntimeError(f'missing manual station verification {VERIFY_COLBERT}')
    colbert=json.loads(VERIFY_COLBERT.read_text())
    if colbert.get('operator')!='Chargelec36 / SDEI36': raise RuntimeError('manual Chargelec36 Colbert verification operator mismatch')
    if colbert.get('station',{}).get('name')!='CHATEAUROUX - Colbert': raise RuntimeError('Colbert witness name mismatch')
    if colbert.get('station',{}).get('evseCount')!=2 or colbert.get('station',{}).get('stationMaxPowerKVA')!=22:
        raise RuntimeError('Colbert live hardware witness mismatch')
    card=colbert.get('manualEvidence',{}).get('directTariff',{})
    if card.get('billingModel')!='flat_session_fee' or card.get('fixedSessionFeeEur')!=10.0 or card.get('semanticsResolved') is not True:
        raise RuntimeError('Chargelec36 direct bank-card flat tariff verification mismatch')
    if colbert.get('decision',{}).get('directBankCardPriceValidated') is not True:
        raise RuntimeError('Chargelec36 direct bank-card tariff not marked validated')

    trows=[]
    for url in TOURISM:
        st,raw,final=fetch(url)
        if st!=200: raise RuntimeError(f'tourism HTTP {st} {url}')
        tx=raw.decode('utf-8',errors='replace')
        require(tx,'chargelec 36','2026','10','Cartes bancaires')
        trows.append({'url':url,'httpStatus':st,'sha256':hashlib.sha256(raw).hexdigest()})

    payload={
      'schemaVersion':'1.1.0','dataset':'chargelec36-official-centre','generatedAt':now(),
      'operator':'Chargelec36 / SDEI36','authority':'Syndicat Départemental d’Énergies de l’Indre (SDEI)','country':'FR','region':'Centre-Val de Loire','department':'Indre',
      'classification':{
        'regionalPublicNetwork':True,'directPublicAccess':True,'firstPartyPriceBookLinked':True,
        'firstPartyPriceBookMachineReadableValidated':False,'firstPartyBankCardFlatTariffManuallyValidated':True,
        'currentThirdPartyLocalPriceCorroboration':True,'singleUniversalExactTariffValidated':False,
        'rankableDirectBankCardTariff':True,'rankableWithoutFirstPartyPriceConfirmation':False
      },
      'access':{'rfidBadge':True,'contactlessBankCard':True,'billingAtEndOfChargeForBankCard':True,'interoperability':True},
      'currentPriceEvidence':{
        'tourismOfficeObservedEur':10.0,'observationYear':2026,'observationCount':len(trows),
        'semanticsResolved':True,
        'directBankCard':{'currency':'EUR','billingModel':'flat_session_fee','fixedSessionFeeEur':10.0,'source':'first-party Chargelec36 user guide manually verified'},
        'badgeAndRoamingSamePriceProven':False,
        'note':'The 10 EUR amount is now resolved for direct bank-card payment as a fixed session price. Do not propagate this price to RFID/subscriber or roaming access without separate evidence.'
      },
      'networkEvidence':{
        'liveFirstPartyStationDirectory':True,'currentPublicDatasetUpdated':'2026-01-28',
        'manualStaleCandidateCheck':{
          'candidate':'4 rue Jules Chauvin, Châteauroux','visibleOnOfficialMapDuringManualCheck':False,
          'presentInCurrentFirstPartyDirectory':current_candidate_present,'excludeAsLiveWitness':True,
          'replacementCurrentFirstPartyWitness':'CHATEAUROUX - Colbert','verificationFile':str(VERIFY_STALE)
        },
        'manualCurrentStationCheck':{
          'station':'CHATEAUROUX - Colbert','latitude':46.811115,'longitude':1.7041603,
          'evseCount':2,'powerKVA':22,'visibleOnOfficialMapDuringManualCheck':True,
          'verificationFile':str(VERIFY_COLBERT)
        }
      },
      'tccDecision':{
        'operatorValidated':True,'defaultDisplay':'direct_bank_card_flat_session','numericPriceRankable':True,
        'rankablePaymentMethod':'contactless_bank_card','billingModel':'flat_session_fee','fixedSessionFeeEur':10.0,
        'excludeJulesChauvinAsLiveTariffWitness':True,'badgeAndRoamingTariffNeedsSeparateResolution':True,
        'reason':'Direct bank-card charging is validated at a fixed 10 EUR per session from the official Chargelec36 guide, with current Colbert station hardware verified manually. Badge/subscriber and roaming pricing remain separate.'
      },
      'sourceEvidence':{
        'firstPartyOnlyForNetworkAndAccess':False,'homeUrl':HOME,'homeHttpStatus':hs,'registrationUrl':REG,'registrationHttpStatus':rs,
        'stationsUrl':STATIONS,'stationsHttpStatus':ss,'guideUrl':GUIDE,'guideHttpStatus':gs,
        'publicDatasetUrl':DATA,'publicDatasetHttpStatus':ds,'tourismCorroboration':trows,
        'manualStaleStationVerificationFile':str(VERIFY_STALE),'manualCurrentStationVerificationFile':str(VERIFY_COLBERT),
        'homeSha256':hashlib.sha256(hraw).hexdigest(),'registrationSha256':hashlib.sha256(rraw).hexdigest(),'stationsSha256':hashlib.sha256(sraw).hexdigest(),'guideSha256':hashlib.sha256(graw).hexdigest()
      },
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','access','currentPriceEvidence','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'chargelec36_official_centre.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Chargelec36 / SDEI36\n\nNetwork and direct access are validated. Rue Jules Chauvin in Châteauroux remains excluded as a stale live witness. CHATEAUROUX - Colbert is verified on the current official map with two NORMAL 22 kVA charge points and 22 kVA maximum power. The official Chargelec36 guide has now been manually resolved for direct bank-card payment: **10 EUR fixed per charging session**. This direct card scenario can be ranked in Tesla Charge Companion. Do not apply the same 10 EUR to RFID/subscriber or roaming sessions unless separately validated; site parking charges also remain separate.\n')

if __name__=='__main__': main()
