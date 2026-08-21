#!/usr/bin/env python3
"""Validate SDEA Aube ELINVEST public-domain IRVE rollout coverage."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36';URL='https://www.sde-aube.fr/au-service-des-collectivites-et-des-aubois/la-transition-energetique'
def fetch(u):
 q=urllib.request.Request(u,headers={'User-Agent':UA,'Accept-Language':'fr-FR,fr;q=0.9'});r=urllib.request.urlopen(q,timeout=60);return r.status,r.read(),r.geturl()
def text(b):
 s=b.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower().replace('’',"'")).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/sdea_elinvest');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True);st,raw,final=fetch(URL);t=norm(text(raw))
 for q in ['Appel à Initiative Privée','attribué','ELINVEST','228 points de charge','57 stations de recharge','45 stations','22kVA','12 stations','180kW','17 ans']:
  if norm(q) not in t:raise RuntimeError('SDEA ELINVEST evidence missing: '+q)
 p={'schemaVersion':'1.0.0','dataset':'sdea-elinvest-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'ELINVEST - AIP SDEA Aube','authority':'SDEA - Syndicat départemental d’énergie de l’Aube','partners':['Banque des Territoires','Equans','TIIC'],'country':'FR','region':'Grand Est','department':'Aube','classification':{'publicDomainPrivateInitiativeNetwork':True,'rolloutValidated':True,'separateFromLegacyChargelec':True,'exactCurrentConsumerTariffResolved':False,'directTariffClassable':False},'network':{'plannedChargePoints':228,'plannedStations':57,'acStations':45,'acPowerKw':22,'highPowerStations':12,'dcPowerKw':180,'publicDomain':True,'occupationAgreementYears':17},'tariff':{'exactCurrentAmount':None,'status':'not_published_in_current_sdea_rollout_evidence','doNotReuseLegacyChargelecTariff':True},'tccDecision':{'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':st,'officialSha256':hashlib.sha256(raw).hexdigest()},'publicationStatus':'validated_candidate_reference_only'}
 (o/'sdea_elinvest_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# SDEA Aube / ELINVEST AIP\n\nCurrent SDEA evidence validates ELINVEST as the public-domain AIP rollout: 228 points / 57 stations, with 45 AC 22 kW stations and 12 DC 180 kW stations. This is separate from the legacy Chargelec network. No exact ELINVEST consumer tariff is published in this authority evidence, so ranking is deferred.\n')
if __name__=='__main__':main()
