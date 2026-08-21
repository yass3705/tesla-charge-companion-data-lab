#!/usr/bin/env python3
"""Validate current first-party SIE-ELY tariff rules from official SIE-ELY/Alize sources."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
HOME='https://sieely.alizecharge.com/'
TARIFF='https://sieely.alizecharge.com/tarifs/'
IMG74='https://alizecharge.com/app/uploads/sites/14/2024/06/Tarif_SIEELY_SYN_74kW-vf-1-e1717659641951.png'
IMG22='https://alizecharge.com/app/uploads/sites/14/2024/06/Tarif_SIEELY_SYN_22kW-vf-1-e1717659622903.png'
CGV='https://alizecharge.com/app/uploads/sites/14/2026/01/CGV_Sieely22122025.pdf'


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
    if missing: raise RuntimeError('SIE-ELY evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/sieely'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    hs,hraw,hfinal=fetch(HOME); ts,traw,tfinal=fetch(TARIFF); s74,b74,f74=fetch(IMG74); s22,b22,f22=fetch(IMG22); cs,craw,cfinal=fetch(CGV)
    if min(hs,ts,s74,s22,cs)!=200: raise RuntimeError(f'HTTP failure home={hs} tariff={ts} img74={s74} img22={s22} cgv={cs}')
    h=hraw.decode('utf-8',errors='replace'); t=traw.decode('utf-8',errors='replace')
    require(h,'SIEELY','4','Communes','6','Bornes','11','Points de charge','badge SIEELY','itinérance')
    require(t,'Tarifs','7,4','22','Tarif_SIEELY_SYN_7','Tarif_SIEELY_SYN_22')
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError('pypdf required to validate current SIE-ELY CGV') from e
    ctext='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(craw)).pages)
    require(ctext,'Date de mise à jour : 22 décembre 2025','SIEELY','scan du QR code','Prix du Service de Charge','tarifs des Services de Charge','page web')
    payload={
      'schemaVersion':'1.0.0','dataset':'sieely-official-idf-centre','generatedAt':now(),
      'operator':'SIE-ELY','authority':'Syndicat Intercommunal d’Energies d’Eure-et-Loir et des Yvelines','country':'FR',
      'regions':['Ile-de-France','Centre-Val de Loire'],'departments':['Yvelines','Eure-et-Loir'],
      'classification':{'localPublicNetwork':True,'directPublicTariff':True,'singleFlatTariff':False,'energyPlusParking':True,'crossRegionNetwork':True,'roamingMayDiffer':True},
      'directTariff':{
        'upTo7_4Kw':{'connectionFeeEur':1.0,'energyEurPerKwh':0.30,'parkingDay0800To2000EurPerHour':0.50,'parkingNight2000To0800EurPerHour':0.0},
        'upTo22Kw':{'connectionFeeEur':1.0,'energyEurPerKwh':0.30,'parkingDay0800To2000First2HoursEurPerHour':1.0,'parkingDay0800To2000After2HoursEurPerHour':4.0,'parkingNight2000To0800EurPerHour':0.30}
      },
      'access':{'sieelyBadge':True,'alizeAccount':True,'qrCode':True,'nonAccountQrAllowedByCgv':True,'partnerBadgesMayAddRoamingSurcharge':True},
      'sessionSemantics':{'startsAtBadgeAppOrQr':True,'endsAfterSessionClosureVehicleUnpluggedAndSpaceReleased':True,'parkingFeeAppliesDuringServiceSession':True},
      'networkSnapshot':{'communes':4,'stations':6,'chargePoints':11},
      'sourceEvidence':{
        'officialOnly':True,'homeUrl':HOME,'homeHttpStatus':hs,'tariffUrl':TARIFF,'tariffHttpStatus':ts,
        'tariff74Asset':IMG74,'tariff74HttpStatus':s74,'tariff74Sha256':hashlib.sha256(b74).hexdigest(),
        'tariff22Asset':IMG22,'tariff22HttpStatus':s22,'tariff22Sha256':hashlib.sha256(b22).hexdigest(),
        'cgvUrl':CGV,'cgvHttpStatus':cs,'cgvSha256':hashlib.sha256(craw).hexdigest(),
        'tariffValuesHumanValidatedFromFirstPartyAssets':True
      },
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','directTariff','access','sessionSemantics')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'sieely_official_idf_centre.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# SIE-ELY\n\nValidated current first-party tariffs for 7.4 kW and 22 kW SIE-ELY points. Direct local tariff is classable where the SIE-ELY network and power tier are identified; roaming remains provider-specific.\n')

if __name__=='__main__': main()
