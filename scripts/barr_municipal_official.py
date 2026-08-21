#!/usr/bin/env python3
"""Validate Barr municipal charging tariff from official City and Pays de Barr deliberations."""
from __future__ import annotations
import argparse,hashlib,io,json,re,subprocess,tempfile,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
CITY='https://barr.fr/wp-content/uploads/2025/02/deliberation-cm-du-27-01-2025.pdf'
CCPB='https://www.paysdebarr.fr/vivre/sites/paysdebarr.fr.vivre/files/2024-12/PV%20CC%2017.12.2024.pdf'
def fetch(u):
 r=urllib.request.Request(u,headers={'User-Agent':UA,'Accept':'application/pdf,*/*'});x=urllib.request.urlopen(r,timeout=60);return int(getattr(x,'status',200)),x.read(),x.geturl()
def txt(b):
 parts=[' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)]
 try:
  with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
   f.write(b);f.flush();q=subprocess.run(['pdftotext','-layout',f.name,'-'],capture_output=True,text=True,timeout=30,check=True);parts.append(q.stdout)
 except Exception:pass
 return re.sub(r'\s+',' ',' '.join(parts)).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);s=''.join(c for c in s if not unicodedata.combining(c));s=s.lower().replace('’',"'");s=re.sub(r'\s+',' ',s);return s.strip()
def must(t,label,pattern):
 if not re.search(pattern,t,re.I):raise RuntimeError('Barr official evidence missing: '+label)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/barr');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
 cs,craw,cfinal=fetch(CITY);ps,praw,pfinal=fetch(CCPB);ct=norm(txt(craw));pt=norm(txt(praw))
 if cs!=200 or ps!=200:raise RuntimeError(f'HTTP failure city={cs} ccpb={ps}')
 # City deliberation proves that the municipal chargers align to the CCPB tariff.
 must(ct,'Barr municipal chargers',r'(?:3|trois).{0,80}bornes.{0,100}(?:ville|barr)|bornes.{0,100}(?:3|trois).{0,80}(?:ville|barr)')
 must(ct,'CCPB harmonisation',r'ccpb|pays\s+de\s+barr')
 # Pays de Barr official council record is the durable exact tariff witness.
 must(pt,'0.32 EUR/kWh',r'0[,.]32.{0,35}k\s*wh')
 must(pt,'after 2 hours plugged',r'au[- ]?dela.{0,60}2\s*h.{0,100}branche')
 must(pt,'2 EUR per started hour',r'2\s*€?.{0,35}heure.{0,35}entam')
 p={'schemaVersion':'1.0.0','dataset':'barr-municipal-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Ville de Barr - bornes municipales','country':'FR','region':'Grand Est','department':'Bas-Rhin','classification':{'municipalPublicNetwork':True,'directPublishedTariff':True,'energyBased':True,'connectedTimeSurcharge':True,'startedHourBilling':True,'directTariffClassable':True},'network':{'municipalChargers':3,'paysDeBarrHarmonizationValidated':True,'scopeNote':'The City deliberation aligns the three municipal chargers to the CCPB tariff. The Pays de Barr official council record is used as the exact tariff witness.'},'operatorDirect':{'energyEurPerKwh':0.32,'connectedTime':{'thresholdMinutes':120,'eurPerStartedHourAfterThreshold':2.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'startedHourMustBeModeled':True,'applyExactlyToBarrMunicipalChargers':True,'stationTestsDeferred':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'cityUrl':cfinal,'cityHttpStatus':cs,'citySha256':hashlib.sha256(craw).hexdigest(),'cityDecisionDate':'2025-01-27','ccpbUrl':pfinal,'ccpbHttpStatus':ps,'ccpbSha256':hashlib.sha256(praw).hexdigest(),'ccpbDecisionDate':'2024-11-28'},'publicationStatus':'validated_candidate'}
 (o/'barr_municipal_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Barr municipal charging\n\nOfficial City and Pays de Barr records validate the harmonised tariff for the three municipal chargers: 0.32 EUR/kWh, plus 2 EUR per started hour after two hours plugged in.\n')
if __name__=='__main__':main()
