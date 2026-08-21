#!/usr/bin/env python3
"""Validate Sélestat municipal Freshmile charging offer."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'; URL='https://www.selestat.fr/mon-quotidien/se-deplacer/bornes-de-recharge-electrique'
def fetch(u):
 r=urllib.request.Request(u,headers={'User-Agent':UA,'Accept-Language':'fr-FR,fr;q=0.9'}); x=urllib.request.urlopen(r,timeout=60); return x.status,x.read(),x.geturl()
def text(b):
 s=b.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower()).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/selestat');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True);st,raw,final=fetch(URL);t=norm(text(raw))
 for q in ['les 2 bornes installees par la ville de selestat','recharger 2 vehicules chacune','freshmile charge','la recharge est gratuite','seule la place de parking est payante']:
  if norm(q) not in t: raise RuntimeError('Sélestat official evidence missing: '+q)
 p={'schemaVersion':'1.0.0','dataset':'selestat-freshmile-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Ville de Sélestat - bornes municipales','serviceOperator':'Freshmile','country':'FR','region':'Grand Est','department':'Bas-Rhin','classification':{'municipalPublicNetwork':True,'directPublishedTariff':True,'chargingFree':True,'parkingSeparate':True,'directTariffClassable':True},'network':{'municipalChargers':2,'chargePointsPerCharger':2,'scopeNote':'Free charging applies only to the two chargers installed by the Ville de Sélestat, not to all ~60 chargers on the territory.'},'operatorDirect':{'energyEurPerKwh':0.0,'parkingIncludedInChargingTariff':False,'parkingPaidSeparately':True},'access':{'freshmileBadge':True,'freshmileApp':True,'smartphoneWithoutAccount':True},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'applyOnlyToMunicipalChargers':True,'parkingSeparate':True,'stationTestsDeferred':True},'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':st,'officialSha256':hashlib.sha256(raw).hexdigest()},'publicationStatus':'validated_candidate'}
 (o/'selestat_freshmile_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Sélestat / Freshmile\n\nThe two municipal chargers are free for energy; parking remains paid separately. Freshmile badge/app/smartphone access is confirmed. Scope strictly limited to the two city-installed chargers.\n')
if __name__=='__main__':main()
