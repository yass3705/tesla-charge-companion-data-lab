#!/usr/bin/env python3
"""Validate Grand Reims SDIRVE/public charging coverage from durable official reports."""
from __future__ import annotations
import argparse,hashlib,io,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
DD='https://www.reims.fr/fileadmin/reims/MEDIA/13_Qualite_Vie_Environnement/Rapport_DD/DD-Reims-2023-WEB2.pdf'
PCAET='https://www.reims.fr/fileadmin/grandreims/MEDIA/12_cadre_de_vie_environnement/bas_carbone/doc_bas_carbone/Reponses_Etat_Region.pdf'
def fetch(u):
 q=urllib.request.Request(u,headers={'User-Agent':UA,'Accept':'application/pdf,*/*'});r=urllib.request.urlopen(q,timeout=60);return int(getattr(r,'status',200)),r.read(),r.geturl()
def txt(b):return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower().replace('’',"'")).strip()
def need(t,label,*parts):
 n=norm(t)
 if not all(norm(x) in n for x in parts):raise RuntimeError('Grand Reims evidence missing: '+label)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/grand_reims');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
 ds,draw,dfinal=fetch(DD);ps,praw,pfinal=fetch(PCAET)
 if ds!=200 or ps!=200 or not draw.startswith(b'%PDF') or not praw.startswith(b'%PDF'):raise RuntimeError(f'official PDF failure dd={ds} pcaet={ps}')
 dt=txt(draw);pt=txt(praw)
 need(dt,'SDIRVE adoption','Schéma Directeur des Infrastructures de Recharge','adopté par le Grand Reims','septembre 2023')
 need(dt,'public/private deployment incentives','opérateurs publics et privés','75 % de réduction','domaine public')
 need(pt,'SIEM coordination','SDIRVE','Syndicat Intercommunal d\'Energies de la Marne','SIEM')
 p={'schemaVersion':'1.0.0','dataset':'grand-reims-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Communauté urbaine du Grand Reims - stratégie IRVE','country':'FR','region':'Grand Est','department':'Marne','classification':{'publicTerritorySDIRVE':True,'siemCoordination':True,'privateActorDeploymentStrategy':True,'networkFamilyAccountedFor':True,'exactCurrentDirectTariffResolved':False,'directTariffClassable':False},'network':{'sdIRVEAdopted':'2023-09','jointSteeringWith':'SIEM - Syndicat Intercommunal d’Énergies de la Marne','deploymentIncludesPublicDomain':True,'privateActorMobilization':True,'note':'Official Grand Reims reporting confirms an adopted SDIRVE, SIEM coordination and incentives applying to public and private operators. SIEM/Modulo assets remain represented by the separate Modulo Marne coverage record; no single metropolitan CPO or tariff is invented.'},'tariff':{'exactCurrentAmount':None,'status':'no_single_current_local_tariff_resolved','historicalEngieIneoTariffNotReused':True},'tccDecision':{'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'developmentReportUrl':dfinal,'developmentReportHttpStatus':ds,'developmentReportSha256':hashlib.sha256(draw).hexdigest(),'pcaetResponseUrl':pfinal,'pcaetResponseHttpStatus':ps,'pcaetResponseSha256':hashlib.sha256(praw).hexdigest()},'publicationStatus':'validated_candidate_reference_only'}
 (o/'grand_reims_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Grand Reims IRVE\n\nGrand Reims officially reports an SDIRVE adopted in September 2023, coordinated with SIEM and designed to facilitate deployments by public and private operators, including public-domain sites. No single current direct local tariff is asserted; SIEM/Modulo remains a separate validated coverage record.\n')
if __name__=='__main__':main()
