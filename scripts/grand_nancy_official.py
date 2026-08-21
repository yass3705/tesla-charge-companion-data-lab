#!/usr/bin/env python3
"""Validate current Grand Nancy legacy Modulo network and Easy Charge Services rollout."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
LEGACY='https://www.grandnancy.eu/se-deplacer/electromobilites'
EXPANSION='https://www.grandnancy.eu/actualites/actualite/news/un-reseau-public-de-recharge-pour-vehicules-electriques-dans-la-metropole-du-grand-nancy'
def fetch(u):
 q=urllib.request.Request(u,headers={'User-Agent':UA,'Accept-Language':'fr-FR,fr;q=0.9'});r=urllib.request.urlopen(q,timeout=60);return r.status,r.read(),r.geturl()
def text(b):
 s=b.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower().replace('’',"'")).strip()
def req(t,*qs):
 n=norm(t);m=[q for q in qs if norm(q) not in n]
 if m:raise RuntimeError('Grand Nancy evidence missing: '+', '.join(m))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/grand_nancy');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
 ls,lr,lf=fetch(LEGACY);es,er,ef=fetch(EXPANSION);lt=text(lr);et=text(er)
 req(lt,'plus de 70 points de recharge','21 sites','1er avril 2023','MODULO','Liste des parkings équipés')
 req(et,'Easy Charge Services','133 bornes','266 points de charge','83 stations','20 communes','22 kW','60 kW','120 kW','17 ans')
 p={'schemaVersion':'1.0.0','dataset':'grand-nancy-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Métropole du Grand Nancy - réseaux publics IRVE','country':'FR','region':'Grand Est','department':'Meurthe-et-Moselle','classification':{'metropolitanPublicNetwork':True,'legacyModuloNetwork':True,'easyChargeExpansion':True,'networkFamiliesAccountedFor':True,'singleExactCurrentTariffResolved':False,'directTariffClassable':False},'legacyNetwork':{'serviceOperator':'Modulo Energies','publishedChargePointsAtLeast':70,'publishedSites':21,'moduloSince':'2023-04-01'},'expansion':{'operator':'Easy Charge Services','localPartner':'CITEOS Nancy / VINCI Energies','plannedChargers':133,'plannedChargePoints':266,'plannedStations':83,'territoryCommunes':20,'powerKw':[22,60,120],'contractYears':17,'deploymentHorizonEnd':2026,'openAccess':True},'tariff':{'exactCurrentAmount':None,'status':'network_or_station_specific','reuseExistingModuloReferenceRulesForLegacy':True,'easyChargeTariffToBeReadAtLiveInterface':True,'note':'Current official pages confirm operators and network scope but do not expose one exact universal tariff suitable for ranking both families.'},'tccDecision':{'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','stationTestsDeferred':True,'exactTariffFollowupRequired':True,'keepLegacyAndExpansionDistinct':True},'sourceEvidence':{'officialOnly':True,'legacyUrl':lf,'legacyHttpStatus':ls,'legacySha256':hashlib.sha256(lr).hexdigest(),'expansionUrl':ef,'expansionHttpStatus':es,'expansionSha256':hashlib.sha256(er).hexdigest()},'publicationStatus':'validated_candidate_reference_only'}
 (o/'grand_nancy_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Grand Nancy public IRVE\n\nCurrent official sources account for both network families: the legacy 70+ point / 21-site network managed via Modulo since April 2023, and the Easy Charge Services expansion of 133 chargers / 266 points / 83 stations across all 20 communes through end-2026. Keep both families distinct and reference-only until exact live tariff mapping is confirmed.\n')
if __name__=='__main__':main()
