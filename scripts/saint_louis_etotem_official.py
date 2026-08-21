#!/usr/bin/env python3
"""Validate current official Saint-Louis Agglomération / E-TOTEM charging tariffs."""
from __future__ import annotations
import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
OFFICIAL='https://www.agglo-saint-louis.fr/fr/au-quotidien/mobilite/bornes-electriques/'
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
    if missing:raise RuntimeError('Saint-Louis official evidence missing: '+', '.join(missing))
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/saint_louis_etotem');args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    status,raw,final=fetch(OFFICIAL)
    if status!=200:raise RuntimeError(f'HTTP failure official={status}')
    text=plain(raw);require(text,'depuis le 1er janvier 2026','E-TOTEM','40 points de charge','Mode Eco 3,7 kW','Normal ou Boost 7,4-22 kW','0,30 €','0,39 €','50 kW-99 kW','100-180 kW','0,45 €','0,49 €','10 minutes de franchise','1 € / 15 min','3 € / 15 min','limitée à 2 € maximum','22 h et 8 h')
    payload={'schemaVersion':'1.0.0','dataset':'saint-louis-etotem-official-grandest','generatedAt':now(),'operator':'Saint-Louis Agglomération - réseau public','serviceOperator':'E-TOTEM','country':'FR','region':'Grand Est','department':'Haut-Rhin','classification':{'localPublicNetwork':True,'directPublishedTariff':True,'energyBased':True,'postChargeBlockFee':True,'nightPostChargeCap':True,'directTariffClassable':True,'nationalEtotemOperatorAlreadyValidated':True},'network':{'legacyChargePointsTakenOver':40,'serviceOperatorSince':'2026-01-01','publishedPowerRangeKw':[3,180]},'operatorDirect':{'eCity':{'eco37KwEurPerKwh':0.30,'normalBoost74To22KwEurPerKwh':0.39,'postChargeFreeMinutes':10,'postChargeEurPer15Minutes':1.0},'ePremiumFast':{'power50To99KwEurPerKwh':0.45,'power100To180KwEurPerKwh':0.49,'postChargeFreeMinutes':10,'postChargeEurPer15Minutes':3.0},'postChargeNight':{'localTimeStart':'22:00','localTimeEnd':'08:00','maximumEur':2.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'postChargeBlocksMustBeModeled':True,'nightCapMustBeModeled':True,'roamingSeparate':True,'stationTestsDeferred':True},'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':status,'officialSha256':hashlib.sha256(raw).hexdigest()},'publicationStatus':'validated_candidate'}
    sig={k:payload[k] for k in ('classification','network','operatorDirect','tccDecision')};payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'saint_louis_etotem_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(out/'SUMMARY.md').write_text('# Saint-Louis Agglomération / E-TOTEM\n\nE-TOTEM operates the network from 1 January 2026. Exact official tariffs validated: e-City 3.7 kW 0.30 EUR/kWh, 7.4-22 kW 0.39 EUR/kWh; e-Premium/e-Fast 50-99 kW 0.45 EUR/kWh, 100-180 kW 0.49 EUR/kWh. Post-charge starts after 10 free minutes at 1 EUR/15 min on e-City or 3 EUR/15 min on e-Premium/e-Fast, with a 2 EUR cap for charges between 22:00 and 08:00.\n')
if __name__=='__main__':main()
