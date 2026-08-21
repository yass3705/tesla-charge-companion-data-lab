#!/usr/bin/env python3
"""Validate current first-party Ecocharge77 tariff rules from official SDESM/Ecocharge77 sources."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
TARIFF_PAGE='https://ecocharge77.fr/tarifs/'
SERVICE_PAGE='https://ecocharge77.fr/recharger-son-vehicule/'
TARIFF_IMAGE='https://alizecharge.com/app/uploads/sites/10/2024/07/Tarif_Globaux_2024.jpg'
SDESM_PV='https://www.sdesm.fr/wp-content/uploads/2024/02/CS-07-02-2024.pdf'

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
    if missing: raise RuntimeError('Ecocharge77 evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/ecocharge77'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    ts,traw,tfinal=fetch(TARIFF_PAGE); ss,sraw,sfinal=fetch(SERVICE_PAGE); ims,imraw,imfinal=fetch(TARIFF_IMAGE); ps,praw,pfinal=fetch(SDESM_PV)
    if min(ts,ss,ims,ps)!=200: raise RuntimeError(f'HTTP failure tariff={ts} service={ss} image={ims} pv={ps}')
    thtml=traw.decode('utf-8',errors='replace'); shtml=sraw.decode('utf-8',errors='replace')
    require(thtml,'Ecocharge77','badge Ecocharge77','application mobile Ecocharge77','QR Code','carte bancaire','tarifs différents')
    require(thtml,'Tarif_Globaux_2024.jpg')
    require(shtml,'18kW','24kW','100kW','DBT Milestone 120','tarif local en vigueur')
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError('pypdf required to validate official SDESM committee PDF') from e
    text='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(praw)).pages)
    require(text,'0,46 € TTC par kWh','0,20 € TTC / minute','Au-delà d’1h de session de charge')
    require(text,'0,36 € TTC par kWh','0,036 € TTC par minute','Au-delà de 3h de session de charge','8h à 21h')
    require(text,'applicable à compter du 1er avril 2024')
    payload={
      'schemaVersion':'1.0.0','dataset':'ecocharge77-official-idf','generatedAt':now(),
      'operator':'Ecocharge77','authority':'Syndicat Départemental des Énergies de Seine-et-Marne (SDESM)','country':'FR','region':'Ile-de-France','department':'Seine-et-Marne',
      'effectiveFrom':'2024-04-01',
      'classification':{'localPublicNetwork':True,'directTariff':True,'singleFlatTariff':False,'energyAndTimeDependent':True,'roamingMayDiffer':True},
      'directAccess':{'badgeEcocharge77':True,'mobileApp':True,'qrCode':True,'bankCardWhereReaderAvailable':True,'sameLocalTariffForRegisteredAndOccasional':True},
      'directTariff':{
        'normalUpTo24Kw':{'energyEurPerKwh':0.36,'day0800To2100AdditionalAfterMinutes':180,'dayAdditionalEurPerMinute':0.036,'night2100To0800AdditionalEurPerMinute':0.0},
        'rapidAtLeast50Kw':{'energyEurPerKwh':0.46,'additionalAfterMinutes':60,'additionalEurPerMinute':0.20}
      },
      'powerContext':{'legacyAcKw':[18.0],'dcNormalKw':[24.0],'rapidKw':[100.0],'sharedPowerPossibleWhenTwoVehiclesConnected':True},
      'roaming':{'thirdPartyEmpTariffMayDiffer':True,'examples':['Chargemap','Izivia','Ulys','Freshmile'],'ecocharge77BadgePartnerNetworkTariffShownInApp':True},
      'parking':{'dedicatedChargingSpace':True,'separateParkingFeeValidated':False},
      'sourceEvidence':{'officialOnly':True,'tariffPageUrl':TARIFF_PAGE,'tariffPageHttpStatus':ts,'servicePageUrl':SERVICE_PAGE,'servicePageHttpStatus':ss,'tariffImageUrl':TARIFF_IMAGE,'tariffImageHttpStatus':ims,'sdesmCommitteePdfUrl':SDESM_PV,'sdesmCommitteePdfHttpStatus':ps,'tariffPageSha256':hashlib.sha256(traw).hexdigest(),'tariffImageSha256':hashlib.sha256(imraw).hexdigest(),'sdesmCommitteePdfSha256':hashlib.sha256(praw).hexdigest()},
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('effectiveFrom','classification','directAccess','directTariff','powerContext','roaming','parking')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'ecocharge77_official_idf.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Ecocharge77 / Seine-et-Marne\n\nValidated current first-party tariff rules from the official Ecocharge77 tariff page/image and SDESM committee decision. Direct registered/occasional access is classable; third-party roaming prices remain provider-specific.\n')
if __name__=='__main__': main()
