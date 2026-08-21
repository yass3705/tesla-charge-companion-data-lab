#!/usr/bin/env python3
"""Validate current official Colmar municipal Freshmile charging tariff."""
from __future__ import annotations
import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
OFFICIAL='https://www.colmar.fr/stationnement'
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:return int(getattr(r,'status',200)),r.read(),r.geturl()
def plain(raw):
    s=raw.decode('utf-8',errors='replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '');s=''.join(c for c in s if not unicodedata.combining(c));return re.sub(r'\s+',' ',s.lower().replace('’',"'")).strip()
def require(text,*items):
    n=norm(text);missing=[x for x in items if norm(x) not in n]
    if missing:raise RuntimeError('Colmar official evidence missing: '+', '.join(missing))
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/colmar_freshmile');args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    status,raw,final=fetch(OFFICIAL)
    if status!=200:raise RuntimeError(f'HTTP failure official={status}')
    text=plain(raw);require(text,'Les bornes de rechargement électrique','0.30€/kWh','0.03€/minute','continue tant que le véhicule reste branché','Opérateur : Freshmile','Chaque borne a 2 points de charge')
    payload={'schemaVersion':'1.0.0','dataset':'colmar-freshmile-official-grandest','generatedAt':now(),'operator':'Ville de Colmar - bornes publiques','serviceOperator':'Freshmile','country':'FR','region':'Grand Est','department':'Haut-Rhin','classification':{'municipalPublicNetwork':True,'directPublishedTariff':True,'energyBased':True,'connectedTimeBased':True,'directTariffClassable':True,'roamingMayDiffer':True},'operatorDirect':{'energyEurPerKwh':0.30,'connectedTimeEurPerMinute':0.03,'timeFeeContinuesWhilePlugged':True},'network':{'chargePointsPerPublishedCharger':2,'publishedMode':'lent'},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'connectedTimeMustBeModeled':True,'roamingSeparate':True,'stationTestsDeferred':True},'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':status,'officialSha256':hashlib.sha256(raw).hexdigest()},'publicationStatus':'validated_candidate'}
    sig={k:payload[k] for k in ('classification','operatorDirect','network','tccDecision')};payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'colmar_freshmile_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(out/'SUMMARY.md').write_text('# Colmar / Freshmile\n\nCurrent official municipal tariff validated: 0.30 EUR/kWh plus 0.03 EUR/minute. The minute component continues for the whole time the vehicle remains plugged in. Freshmile is the published operator.\n')
if __name__=='__main__':main()
