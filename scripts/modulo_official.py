#!/usr/bin/env python3
"""Validate current public Modulo pricing envelope and Centre-Val de Loire network evidence."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
HOME='https://modulo-energies.fr/'
RULES='https://modulo-energies.fr/wp-content/uploads/2024/09/Reglement-de-service-site-web-2024.pdf'
TE28='https://www.te28.fr/pages/le-service-des-bornes-de-charge'
SIEIL37='https://sieil37.fr/activites-du-sieil/bornes-de-recharge.html'
SDE18='https://www.sde18.com/mobilite-electrique/'

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
    if missing: raise RuntimeError('Modulo evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/modulo'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    hs,hraw,hfinal=fetch(HOME); rs,rraw,rfinal=fetch(RULES); ts,traw,tfinal=fetch(TE28); ss,sraw,sfinal=fetch(SIEIL37); cs,craw,cfinal=fetch(SDE18)
    if min(hs,rs,ts,ss,cs)!=200: raise RuntimeError(f'HTTP failure home={hs} rules={rs} te28={ts} sieil37={ss} sde18={cs}')
    h=hraw.decode('utf-8',errors='replace'); t=traw.decode('utf-8',errors='replace'); s=sraw.decode('utf-8',errors='replace'); c=craw.decode('utf-8',errors='replace')
    require(h,'804','Sans Abonnement','0,52','Abonnement','0,40','Abonnement Gratuit','Pas d’€/min la nuit','carte bancaire','Charge Global')
    require(t,'Modulo','SPL','abonnement','sans aucun abonnement')
    require(s,'Modulo','société publique locale','bornes de recharge')
    require(c,'MODULO','réseau public','1er janvier 2022')
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError('pypdf required to validate current linked Modulo service regulation') from e
    rtext='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(rraw)).pages)
    require(rtext,'RÈGLEMENT DU SERVICE DE RECHARGE','tarification','temps de connexion','statut','abonné ou non','grille tarifaire')
    payload={
      'schemaVersion':'1.0.0','dataset':'modulo-official-centre','generatedAt':now(),
      'operator':'Modulo Energies','country':'FR','primaryRegion':'Centre-Val de Loire',
      'classification':{
        'regionalPublicNetwork':True,'crossRegionNetwork':True,'directAdHoc':True,'freeSubscription':True,
        'publishedPricesAreFromValues':True,'singleUniversalExactTariff':False,'localTariffMayDiffer':True,
        'rankableWithoutLocalConfirmation':False
      },
      'publishedCurrentEnvelope':{
        'nonSubscriberFromEurPerKwh':0.52,'subscriberFromEurPerKwh':0.40,'subscriptionMonthlyFeeEur':0.0,
        'subscriberNoPerMinuteFeeAtNight':True
      },
      'access':{'adHocBankCard':True,'subscription':True,'badge':True,'chargeGlobalApp':True,'roamingPartners':True},
      'centreValDeLoireEvidence':{
        'eureEtLoir':{'authority':'Territoire d’Energie Eure-et-Loir','operatorConfirmed':True},
        'indreEtLoire':{'authority':'SIEIL 37','operatorConfirmed':True},
        'cher':{'authority':'SDE18','operatorConfirmed':True}
      },
      'tccDecision':{
        'operatorValidated':True,'defaultDisplay':'reference_only','reason':'Current first-party public prices are published as from-values and the service regulation allows tariff dependence on charger/status; exact local/station confirmation is required before ranking.'
      },
      'sourceEvidence':{
        'officialOnly':True,'homeUrl':HOME,'homeHttpStatus':hs,'homeSha256':hashlib.sha256(hraw).hexdigest(),
        'serviceRegulationUrl':RULES,'serviceRegulationHttpStatus':rs,'serviceRegulationSha256':hashlib.sha256(rraw).hexdigest(),
        'te28Url':TE28,'te28HttpStatus':ts,'sieil37Url':SIEIL37,'sieil37HttpStatus':ss,'sde18Url':SDE18,'sde18HttpStatus':cs
      },
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','publishedCurrentEnvelope','access','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'modulo_official_centre.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Modulo Energies / Centre-Val de Loire\n\nOperator validated. Current public homepage confirms free subscription from 0.40 EUR/kWh and ad-hoc from 0.52 EUR/kWh, but these are explicitly from-prices; keep Modulo reference-only until the exact local/station tariff is resolved.\n')

if __name__=='__main__': main()
