#!/usr/bin/env python3
"""Validate current Territoire d'Énergie Alsace demonstration/public IRVE coverage."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36';URL='https://te.alsace/vos-services/mobilite-electrique/'
def fetch(u):
 q=urllib.request.Request(u,headers={'User-Agent':UA,'Accept-Language':'fr-FR,fr;q=0.9'});r=urllib.request.urlopen(q,timeout=60);return r.status,r.read(),r.geturl()
def text(b):
 s=b.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower().replace('’',"'")).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/tea_alsace');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True);st,raw,final=fetch(URL);t=norm(text(raw))
 for q in ['Territoire d’Énergie Alsace','Schémas Directeurs des Infrastructures de Recharge','installé six bornes de recharge à titre de démonstration']:
  if norm(q) not in t:raise RuntimeError('TEA evidence missing: '+q)
 p={'schemaVersion':'1.0.0','dataset':'tea-alsace-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Territoire d’Énergie Alsace','country':'FR','region':'Grand Est','departments':['Bas-Rhin','Haut-Rhin'],'classification':{'publicEnergyAuthorityNetwork':True,'demonstrationIRVE':True,'networkExistenceValidated':True,'exactCurrentDirectTariffResolved':False,'directTariffClassable':False},'network':{'currentOfficialDemonstrationChargers':6,'sdIRVEAdvisoryRole':True,'scopeNote':'This record covers TEA-operated/demonstration IRVE only; it does not claim that TEA operates all public chargers in Alsace.'},'tariff':{'exactCurrentAmount':None,'status':'unresolved_from_current_official_page','historicalPricesNotUsedForRanking':True},'tccDecision':{'operatorValidated':True,'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':st,'officialSha256':hashlib.sha256(raw).hexdigest()},'publicationStatus':'validated_candidate_reference_only'}
 (o/'tea_alsace_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Territoire d’Énergie Alsace IRVE\n\nCurrent TEA page confirms six demonstration charging stations and its SDIRVE role. No current exact consumer tariff is exposed there, so TEA-operated/demonstration IRVE remains reference-only; historical tariffs are not used for ranking.\n')
if __name__=='__main__':main()
