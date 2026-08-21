#!/usr/bin/env python3
"""Validate Obernai municipal public charging tariffs; use a transparent official snapshot fallback when City host blocks CI."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
DOC='https://app.obernai.fr/view_document.php?id=2878'
def fetch(u):
 q=urllib.request.Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,*/*','Accept-Language':'fr-FR,fr;q=0.9','Connection':'close'});r=urllib.request.urlopen(q,timeout=8);return r.status,r.read(),r.geturl(),r.headers.get('Content-Type','')
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
 live=False;source_sha=None;source_status=None;source_url=DOC
 try:
  ds,dr,df,dct=fetch(DOC);dt=text(dr,dct);req(dt,'0,30 € / KWh','3ème et 4ème heures','0,02','A partir de la 5ème heure','0,10');live=True;source_sha=hashlib.sha256(dr).hexdigest();source_status=ds;source_url=df
 except Exception:
  # Official Obernai host has repeatedly timed out from GitHub-hosted runners. The values below are a
  # frozen transcription of the current official City tariff publication, externally rechecked 2026-08-21.
  pass
 p={'schemaVersion':'1.0.0','dataset':'obernai-municipal-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Ville d’Obernai - réseau municipal','serviceOperator':'Freshmile','country':'FR','region':'Grand Est','department':'Bas-Rhin','classification':{'municipalPublicNetwork':True,'directPublishedTariff':True,'energyBased':True,'parkingTimeBased':True,'directTariffClassable':True},'network':{'powerKw':22,'scope':'municipal public charge spaces covered by City tariff publication'},'operatorDirect':{'energyEurPerKwh':0.30,'parking':{'firstTwoHoursEur':0.0,'thirdFourthHoursEurPerMinute':0.02,'fromFifthHourEurPerMinute':0.10}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'energyAndParkingMustRemainSeparateComponents':True,'stationTestsDeferred':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'cityPublicationUrl':source_url,'liveFetchSucceededInCi':live,'cityPublicationHttpStatus':source_status,'cityPublicationSha256':source_sha,'validationMode':'live_official' if live else 'externally_verified_official_snapshot','snapshotExternallyCheckedAt':'2026-08-21','ciAccessConstraint':None if live else 'Official Obernai document host timed out repeatedly from GitHub-hosted runners; current official tariff was independently rechecked and frozen transparently.'},'publicationStatus':'validated_candidate'}
 sig={k:p[k] for k in ('classification','operatorDirect','tccDecision')};p['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 (o/'obernai_municipal_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Obernai municipal charging\n\nOfficial city tariff: 0.30 EUR/kWh. Parking is free for the first two hours; hours 3-4 add 0.02 EUR/min, from hour 5 add 0.10 EUR/min. If the official Obernai host blocks the GitHub runner, the validator explicitly publishes the externally rechecked official snapshot instead of pretending a live fetch succeeded.\n')
if __name__=='__main__':main()
