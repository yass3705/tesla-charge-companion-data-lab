#!/usr/bin/env python3
"""Validate current first-party SEY Ma Borne tariff rules from official SEY sources."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
PAGE='https://www.sey78.fr/activites-du-sey/les-bornes-de-recharge'
PV='https://www.sey78.fr/images/4_BIBLIOTHEQUE_OU_DOCUMENTATION/2_Statuts-et-assembl%C3%A9es-Generales/2026-Recueil/COMITE/COMITE_DU_20.01.2026/PV_COMITE_2026_01_20_-_Pour_le_site.pdf'

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
    if missing: raise RuntimeError('SEY evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/sey_maborne'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    hs,hraw,hfinal=fetch(PAGE); ps,praw,pfinal=fetch(PV)
    if hs!=200 or ps!=200: raise RuntimeError(f'HTTP failure page={hs} pv={ps}')
    html=hraw.decode('utf-8',errors='replace')
    require(html,'SEY ma borne','1er mars 2026','9.60','Aucun abonnement','22 kW','36')
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError('pypdf required to validate official SEY committee PDF') from e
    reader=PdfReader(io.BytesIO(praw))
    text='\n'.join((p.extract_text() or '') for p in reader.pages)
    require(text,'Nouvelle tarification 2026','0,36','0,46','Gratuit les deux premières heures','4,00','0,30','1,00','20h','8h','1er mars 2026')
    payload={
      'schemaVersion':'1.0.0','dataset':'sey-maborne-official-idf','generatedAt':now(),
      'operator':'SEY Ma Borne','authority':'Syndicat d’Energie des Yvelines (SEY)','country':'FR','region':'Ile-de-France','department':'Yvelines',
      'effectiveFrom':'2026-03-01',
      'classification':{'localPublicNetwork':True,'directTariff':True,'singleFlatTariff':False,'energyAndTimeDependent':True,'roamingMayDiffer':True},
      'access':{'subscriptionRequired':False,'badgePurchaseEur':9.60,'badgeRecurringFeeEur':0.0,'operatorPortal':'Alize / SEY Ma Borne'},
      'directTariff':{
        'ac22Kw':{'energyEurPerKwh':0.36,'firstHoursTimeFeeFree':2.0,'after2hDayEurPerHour':4.0,'after2hNight2000To0800EurPerHour':0.30,'bankCardNightExceptionEurPerHour':4.0},
        'dc36Kw':{'energyEurPerKwh':0.46,'dayEurPerHour':4.0,'night2000To0800EurPerHour':1.0,'bankCardNightExceptionEurPerHour':4.0}
      },
      'connectorContext':{'typicalAcPointsKw':22.0,'sharedSiteLimitKva':36.0,'type2AndDomesticSockets':True},
      'roaming':{'otherMobilityProviderMayAddSurcharge':True,'officialWarningToCheckProviderCompatibilityAndSurcharges':True},
      'sourceEvidence':{'officialOnly':True,'pageUrl':PAGE,'pageHttpStatus':hs,'committeeMinutesUrl':PV,'committeeMinutesHttpStatus':ps,'pageSha256':hashlib.sha256(hraw).hexdigest(),'committeeMinutesSha256':hashlib.sha256(praw).hexdigest()},
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('effectiveFrom','classification','access','directTariff','connectorContext','roaming')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'sey_maborne_official_idf.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# SEY Ma Borne / Yvelines\n\nValidated the official tariff rules effective 1 March 2026 from SEY public sources. Direct tariff combines energy and time components; roaming-provider surcharges remain outside this direct tariff.\n')
if __name__=='__main__': main()
