#!/usr/bin/env python3
"""Validate current official m2A / IZIVIA Impact public charging network coverage."""
from __future__ import annotations
import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
OFFICIAL='https://www.m2a.fr/mobilites/bornes-irve/'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r: return int(getattr(r,'status',200)),r.read(),r.geturl()

def plain(raw):
    s=raw.decode('utf-8',errors='replace'); s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s); s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or ''); s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('’',"'")).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('m2A official evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/m2a_izivia_impact'); args=ap.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    status,raw,final=fetch(OFFICIAL)
    if status!=200: raise RuntimeError(f'HTTP failure official={status}')
    text=plain(raw)
    require(text,'Mulhouse Alsace Agglomération','IZIVIA','Crédit Mutuel Impact','338 points de charge','39 communes','22 kW','24 kW','100 ou 150 kW')
    payload={
      'schemaVersion':'1.0.0','dataset':'m2a-izivia-impact-official-grandest','generatedAt':now(),
      'operator':'Mulhouse Alsace Agglomération - réseau IRVE m2A','serviceOperators':['IZIVIA','Crédit Mutuel Impact'],'country':'FR','region':'Grand Est','department':'Haut-Rhin',
      'classification':{'localPublicNetwork':True,'networkExistenceValidated':True,'territoryCoverageValidated':True,'exactCurrentDirectTariffResolved':False,'directTariffClassable':False,'nationalIziviaOperatorAlreadyValidated':True},
      'network':{'publishedTargetChargePoints':338,'territoryCommunes':39,'publishedPowerKw':[22,24,100,150],'contactlessCardOnUltraFast':True},
      'tariff':{'exactCurrentAmount':None,'status':'unresolved_from_current_official_page','reuseNationalIziviaOperatorRules':True,'note':'The current m2A authority page confirms the live network scope, partners and charger powers but does not expose machine-readable exact current tariff amounts. Do not reuse launch-era prices as current ranking data.'},
      'tccDecision':{'operatorValidated':True,'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','stationTestsDeferred':True,'exactTariffFollowupRequired':True,'roamingSeparate':True},
      'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':status,'officialSha256':hashlib.sha256(raw).hexdigest()},
      'publicationStatus':'validated_candidate_reference_only'
    }
    sig={k:payload[k] for k in ('classification','network','tariff','tccDecision')}; payload['sourceEvidence']['relevantFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'m2a_izivia_impact_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# m2A / IZIVIA Impact\n\nOfficial m2A evidence validates a 338-point public charging programme across 39 communes with IZIVIA and Crédit Mutuel Impact, at 22/24/100/150 kW. Current exact local tariff amounts are not exposed on the authority page, so keep this network reference-only until a current station/tariff flow is confirmed.\n')
if __name__=='__main__': main()
