#!/usr/bin/env python3
"""Validate current Grand Reims SDIRVE/public charging coverage model."""
from __future__ import annotations
import argparse,hashlib,io,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36';URL='https://www.reims.fr/fileadmin/reims/MEDIA/Presse/Communiques_en_PDF/2023-09-14_CP_CC_.pdf'
def fetch(u):
 q=urllib.request.Request(u,headers={'User-Agent':UA});r=urllib.request.urlopen(q,timeout=60);return r.status,r.read(),r.geturl()
def txt(b):return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower().replace('’',"'")).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/grand_reims');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True);st,raw,final=fetch(URL);t=norm(txt(raw))
 for q in ['Adoption du projet de Schéma Directeur des Infrastructures de Recharge','comité de pilotage conjoint avec le SIEM','mobilisation d’acteurs privés','Appels à Manifestations d’Intérêt','appels à initiatives privées']:
  if norm(q) not in t:raise RuntimeError('Grand Reims evidence missing: '+q)
 p={'schemaVersion':'1.0.0','dataset':'grand-reims-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Communauté urbaine du Grand Reims - stratégie IRVE','country':'FR','region':'Grand Est','department':'Marne','classification':{'publicTerritorySDIRVE':True,'siemCoordination':True,'privateActorDeploymentStrategy':True,'networkFamilyAccountedFor':True,'exactCurrentDirectTariffResolved':False,'directTariffClassable':False},'network':{'sdIRVEAdopted':'2023-09','jointSteeringWith':'SIEM - Syndicat Intercommunal d’Énergies de la Marne','deploymentIncludesPublicDomain':True,'privateActorMobilization':True,'note':'SIEM/Modulo assets are represented by the existing Modulo Marne coverage record. This Grand Reims record accounts for the metropolitan/public-domain strategy and privately financed deployments without asserting a single current CPO.'},'tariff':{'exactCurrentAmount':None,'status':'no_single_current_local_tariff_resolved','historicalEngieIneoTariffNotReused':True},'tccDecision':{'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':st,'officialSha256':hashlib.sha256(raw).hexdigest()},'publicationStatus':'validated_candidate_reference_only'}
 (o/'grand_reims_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Grand Reims IRVE\n\nGrand Reims adopted its SDIRVE in September 2023, with joint steering alongside SIEM and deployment relying on private actors including public-domain sites. No single current direct local tariff is asserted here; SIEM/Modulo remains a separate validated coverage record.\n')
if __name__=='__main__':main()
