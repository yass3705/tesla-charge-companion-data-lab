#!/usr/bin/env python3
"""Validate Obernai municipal public charging tariffs from official city publication."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'; PAGE='https://www.obernai.fr/Fr/Deplacer/Voiture/Voiture-electrique.html'; DOC='https://app.obernai.fr/view_document.php?id=2371'
def fetch(u):
 q=urllib.request.Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,*/*','Accept-Language':'fr-FR,fr;q=0.9'});r=urllib.request.urlopen(q,timeout=60);return r.status,r.read(),r.geturl(),r.headers.get('Content-Type','')
def text(b,ct):
 if b[:4]==b'%PDF' or 'pdf' in ct.lower():
  from pypdf import PdfReader;import io;return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)).strip()
 s=b.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);return re.sub(r'\s+',' ',''.join(c for c in s if not unicodedata.combining(c)).lower().replace('’',"'")).strip()
def req(t,*qs):
 n=norm(t);m=[q for q in qs if norm(q) not in n]
 if m:raise RuntimeError('Obernai evidence missing: '+', '.join(m))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/obernai');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
 ps,pr,pf,pct=fetch(PAGE);ds,dr,df,dct=fetch(DOC);pt=text(pr,pct);dt=text(dr,dct)
 req(pt,'Place des Fines Herbes','Parking de l\'Altau','Parking des Remparts')
 req(dt,'10 emplacements de charge','0,30 € / KWh','3e et 4e heures','0,02','A partir de la 5e heure','0,10','Freshmile')
 p={'schemaVersion':'1.0.0','dataset':'obernai-municipal-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Ville d’Obernai - réseau municipal','serviceOperator':'Freshmile','country':'FR','region':'Grand Est','department':'Bas-Rhin','classification':{'municipalPublicNetwork':True,'directPublishedTariff':True,'energyBased':True,'parkingTimeBased':True,'directTariffClassable':True},'network':{'publishedChargeSpaces':10,'powerKw':22,'coreMunicipalSites':['Fines Herbes','Groupe Scolaire Europe','Remparts','Altau'],'leonardsauExpansionAnnouncedFor2025':True},'operatorDirect':{'energyEurPerKwh':0.30,'parking':{'firstTwoHoursEur':0.0,'thirdFourthHoursEurPerMinute':0.02,'fromFifthHourEurPerMinute':0.10}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'energyAndParkingMustRemainSeparateComponents':True,'stationTestsDeferred':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'cityPageUrl':pf,'cityPageHttpStatus':ps,'cityPageSha256':hashlib.sha256(pr).hexdigest(),'cityPublicationUrl':df,'cityPublicationHttpStatus':ds,'cityPublicationSha256':hashlib.sha256(dr).hexdigest()},'publicationStatus':'validated_candidate'}
 (o/'obernai_municipal_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Obernai municipal charging\n\nOfficial city tariff: 0.30 EUR/kWh. Parking is free for the first two hours; hours 3-4 add 0.02 EUR/min, from hour 5 add 0.10 EUR/min. Keep parking separate from energy. Freshmile is referenced for the municipal network.\n')
if __name__=='__main__':main()
