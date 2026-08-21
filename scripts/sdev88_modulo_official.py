#!/usr/bin/env python3
"""Validate current SDEV Vosges public charging coverage and Modulo access."""
from __future__ import annotations
import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
VITTEL='https://www.ville-vittel.fr/fr/fluides-et-energie.html'
BANATIC='https://www.banatic.interieur.gouv.fr/intercommunalite/200050748-syndicat-departemental-d-electricite-des-vosges'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()

def plain(raw):
    s=raw.decode('utf-8',errors='replace')
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('’',"'")).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('SDEV Vosges evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/sdev88'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    vs,vraw,vfinal=fetch(VITTEL); bs,braw,bfinal=fetch(BANATIC)
    if vs!=200 or bs!=200: raise RuntimeError(f'HTTP failure vittel={vs} banatic={bs}')
    vt=plain(vraw); bt=plain(braw)
    require(vt,'Bornes de recharge pour véhicules électriques','24 kW','22 kW','Sur abonnement auprès de Modulo','Par CB','Syndicat Départemental d\'Électricité des Vosges','SDEV')
    require(bt,"Syndicat départemental d'électricité des Vosges",'Vosges (88)','MIS À JOUR LE 21/05/2026')
    payload={
      'schemaVersion':'1.0.0','dataset':'sdev88-modulo-official-grandest','generatedAt':now(),
      'operator':'SDEV - Syndicat Départemental d’Électricité des Vosges','country':'FR','region':'Grand Est','department':'Vosges',
      'classification':{
        'localPublicNetwork':True,'networkExistenceValidated':True,'moduloAccessValidated':True,
        'adHocCardPaymentValidated':True,'exactLocalTariffResolvedHere':False,'directTariffClassable':False
      },
      'network':{
        'authority':'SDEV','currentAdministrativeExistenceConfirmed':True,
        'sampleOfficialMunicipality':'Vittel','samplePublishedPowerKw':[22,24],'samplePublishedChargePoints':2
      },
      'access':{'subscriptionProvider':'Modulo Energies','subscriptionCard':True,'adHocBankCardViaQrWeb':True},
      'tariff':{
        'authorityModel':'Modulo Energies','reuseExistingModuloOperatorRules':True,'exactLocalAmount':None,
        'note':'Official Vittel evidence confirms Modulo access and CB ad-hoc access on SDEV infrastructure, but does not expose the exact local amount on-page. Reuse validated Modulo rules and keep exact station pricing unresolved.'
      },
      'tccDecision':{
        'operatorValidated':True,'coverageValidated':True,'defaultDisplay':'reference_only','directTariffClassable':False,
        'stationTestsDeferred':True,'exactTariffFollowupRequired':True
      },
      'sourceEvidence':{
        'officialOnly':True,'vittelUrl':vfinal,'vittelHttpStatus':vs,'vittelSha256':hashlib.sha256(vraw).hexdigest(),
        'banaticUrl':bfinal,'banaticHttpStatus':bs,'banaticSha256':hashlib.sha256(braw).hexdigest()
      },
      'publicationStatus':'validated_candidate_reference_only'
    }
    sig={k:payload[k] for k in ('classification','network','access','tariff','tccDecision')}
    payload['sourceEvidence']['relevantFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'sdev88_modulo_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# SDEV Vosges / Modulo\n\nSDEV is validated as a current Vosges public charging network. Official Vittel evidence confirms Modulo subscription access and ad-hoc bank-card access by QR/web on SDEV infrastructure. Keep exact local tariff reference-only until station-level pricing is resolved.\n')

if __name__=='__main__': main()
