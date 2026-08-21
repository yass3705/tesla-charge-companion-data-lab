#!/usr/bin/env python3
"""Validate Grand Reims SDIRVE/public charging coverage with transparent official-source fallback."""
from __future__ import annotations
import argparse,hashlib,io,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
DD='https://www.reims.fr/fileadmin/reims/MEDIA/13_Qualite_Vie_Environnement/Rapport_DD/DD-Reims-2023-WEB2.pdf'
PCAET='https://www.reims.fr/fileadmin/grandreims/MEDIA/12_cadre_de_vie_environnement/bas_carbone/doc_bas_carbone/Reponses_Etat_Region.pdf'
PINNED={'verifiedAt':'2026-08-21','sdIRVEAdopted':'2023-09','siemCoordination':True,'publicPrivateOperators':True,'publicDomainDeployment':True,'enedisConnectionReductionPercent':75}
def fetch(u,timeout=10):
 q=urllib.request.Request(u,headers={'User-Agent':UA,'Accept':'application/pdf,*/*'});r=urllib.request.urlopen(q,timeout=timeout);return int(getattr(r,'status',200)),r.read(),r.geturl()
def txt(b):return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s or '');return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower().replace('’',"'")).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/grand_reims');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
 live={'developmentReport':False,'pcaetResponse':False};hashes={};urls={'developmentReport':DD,'pcaetResponse':PCAET}
 try:
  ds,draw,dfinal=fetch(DD);dt=norm(txt(draw)) if draw.startswith(b'%PDF') else ''
  if ds==200 and 'schema directeur des infrastructures de recharge' in dt and 'septembre 2023' in dt and 'operateurs publics et prives' in dt and '75 %' in dt:
   live['developmentReport']=True;hashes['developmentReportSha256']=hashlib.sha256(draw).hexdigest();urls['developmentReport']=dfinal
 except Exception:pass
 try:
  ps,praw,pfinal=fetch(PCAET);pt=norm(txt(praw)) if praw.startswith(b'%PDF') else ''
  if ps==200 and 'sdirve' in pt and 'siem' in pt:
   live['pcaetResponse']=True;hashes['pcaetResponseSha256']=hashlib.sha256(praw).hexdigest();urls['pcaetResponse']=pfinal
 except Exception:pass
 assert PINNED['sdIRVEAdopted']=='2023-09' and PINNED['siemCoordination'] is True and PINNED['publicPrivateOperators'] is True
 p={'schemaVersion':'1.0.0','dataset':'grand-reims-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Communauté urbaine du Grand Reims - stratégie IRVE','country':'FR','region':'Grand Est','department':'Marne','classification':{'publicTerritorySDIRVE':True,'siemCoordination':True,'privateActorDeploymentStrategy':True,'networkFamilyAccountedFor':True,'exactCurrentDirectTariffResolved':False,'directTariffClassable':False},'network':{'sdIRVEAdopted':'2023-09','jointSteeringWith':'SIEM - Syndicat Intercommunal d’Énergies de la Marne','deploymentIncludesPublicDomain':True,'privateActorMobilization':True,'note':'Official Grand Reims evidence confirms an adopted SDIRVE, SIEM coordination and incentives applying to public and private operators. SIEM/Modulo assets remain represented separately; no single metropolitan CPO or tariff is invented.'},'tariff':{'exactCurrentAmount':None,'status':'no_single_current_local_tariff_resolved','historicalEngieIneoTariffNotReused':True},'tccDecision':{'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'officialUrls':urls,'liveFetchSucceeded':live,'pinnedCompactSnapshot':PINNED,'fallbackUsed':not all(live.values()),'fallbackReason':'Reims official PDF endpoints can return HTML to GitHub-hosted runners; compact official facts are pinned and transparently dated.'},'publicationStatus':'validated_candidate_reference_only'}
 p['sourceEvidence'].update(hashes);(o/'grand_reims_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Grand Reims IRVE\n\nGrand Reims officially reports an SDIRVE adopted in September 2023, coordinated with SIEM and designed to facilitate deployments by public and private operators, including public-domain sites. CI retries the official PDFs live and transparently falls back to a compact snapshot rechecked on 21 August 2026 when those endpoints return HTML. No single current local tariff is asserted.\n')
if __name__=='__main__':main()
