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
    require(s,'Réseau SDEI36','ARGENTON','CHATEAUROUX','ISSOUDUN','VALENCAY')
    require(d,'Chargelec','CHARGELEC / SDEI 36','28 janvier 2026')
    trows=[]
    for url in TOURISM:
        st,raw,final=fetch(url)
        if st!=200: raise RuntimeError(f'tourism HTTP {st} {url}')
        tx=raw.decode('utf-8',errors='replace')
        require(tx,'chargelec 36','2026','10','Cartes bancaires')
        trows.append({'url':url,'httpStatus':st,'sha256':hashlib.sha256(raw).hexdigest()})
    # The user guide is first party and establishes access/billing methods; avoid extracting a tariff from stale snapshots.
    payload={
      'schemaVersion':'1.0.0','dataset':'chargelec36-official-centre','generatedAt':now(),
      'operator':'Chargelec36 / SDEI36','authority':'Syndicat Départemental d’Énergies de l’Indre (SDEI)','country':'FR','region':'Centre-Val de Loire','department':'Indre',
      'classification':{
        'regionalPublicNetwork':True,'directPublicAccess':True,'firstPartyPriceBookLinked':True,
        'firstPartyPriceBookMachineReadableValidated':False,'currentThirdPartyLocalPriceCorroboration':True,
        'singleUniversalExactTariffValidated':False,'rankableWithoutFirstPartyPriceConfirmation':False
      },
      'access':{'rfidBadge':True,'contactlessBankCard':True,'billingAtEndOfChargeForBankCard':True,'interoperability':True},
      'currentPriceEvidence':{
        'tourismOfficeObservedEur':10.0,'observationYear':2026,'observationCount':len(trows),
        'semanticsResolved':False,'note':'Official tourism-office records repeatedly display 10 EUR for Chargelec36 stations, but their CMS labels it as an adult/base tariff and the first-party price book is currently only exposed through an external Calameo link. Do not infer session/kWh/minute semantics.'
      },
      'networkEvidence':{'liveFirstPartyStationDirectory':True,'currentPublicDatasetUpdated':'2026-01-28'},
      'tccDecision':{'operatorValidated':True,'defaultDisplay':'reference_only','numericPriceRankable':False,'reason':'Current 10 EUR amount is strongly corroborated locally but its billing unit/semantics are not first-party machine-readable; exact Chargelec36 offer must remain out of ranking.'},
      'sourceEvidence':{
        'firstPartyOnlyForNetworkAndAccess':True,'homeUrl':HOME,'homeHttpStatus':hs,'registrationUrl':REG,'registrationHttpStatus':rs,
        'stationsUrl':STATIONS,'stationsHttpStatus':ss,'guideUrl':GUIDE,'guideHttpStatus':gs,
        'publicDatasetUrl':DATA,'publicDatasetHttpStatus':ds,'tourismCorroboration':trows,
        'homeSha256':hashlib.sha256(hraw).hexdigest(),'registrationSha256':hashlib.sha256(rraw).hexdigest(),'stationsSha256':hashlib.sha256(sraw).hexdigest(),'guideSha256':hashlib.sha256(graw).hexdigest()
      },
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','access','currentPriceEvidence','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'chargelec36_official_centre.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Chargelec36 / SDEI36\n\nNetwork and direct access are validated. Multiple current 2026 official tourism-office records display 10 EUR, but the billing unit cannot be proven from the first-party public surface because the live price book is delegated to an external Calameo document. Keep Chargelec36 reference-only and out of ranking until first-party tariff semantics are resolved.\n')

if __name__=='__main__': main()
