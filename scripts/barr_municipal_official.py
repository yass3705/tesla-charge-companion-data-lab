#!/usr/bin/env python3
"""Validate current Barr municipal charging tariff from official deliberation."""
from __future__ import annotations
import argparse,hashlib,io,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36';URL='https://barr.fr/wp-content/uploads/2025/02/deliberation-cm-du-27-01-2025.pdf'
def fetch(u):
 r=urllib.request.Request(u,headers={'User-Agent':UA});x=urllib.request.urlopen(r,timeout=60);return x.status,x.read(),x.geturl()
def txt(b):return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s);s=''.join(c for c in s if not unicodedata.combining(c));s=s.lower().replace('’',"'");s=re.sub(r'\s+',' ',s);return s.strip()
def must_regex(t,label,pattern):
 if not re.search(pattern,t,re.I):raise RuntimeError('Barr official evidence missing: '+label)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/barr');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True);st,raw,final=fetch(URL);t=norm(txt(raw))
 must_regex(t,'0.32 EUR/kWh',r'0[,.]32\s*€?\s*(?:ttc\s*)?(?:par\s*)?k\s*wh')
 must_regex(t,'surcharge after 2h',r'(?:au[- ]?dela|apres)[^\n]{0,80}2\s*h[^\n]{0,100}(?:branche|branchement|connexion)')
 must_regex(t,'2 EUR per started hour',r'2\s*€?\s*(?:ttc\s*)?(?:par\s*)?heure[^\n]{0,40}entam')
 must_regex(t,'CCPB B22/2024 harmonisation reference',r'b\s*22\s*/\s*2024[^\n]{0,160}ccpb|ccpb[^\n]{0,160}b\s*22\s*/\s*2024')
 p={'schemaVersion':'1.0.0','dataset':'barr-municipal-official-grandest','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'operator':'Ville de Barr - bornes municipales','country':'FR','region':'Grand Est','department':'Bas-Rhin','classification':{'municipalPublicNetwork':True,'directPublishedTariff':True,'energyBased':True,'connectedTimeSurcharge':True,'startedHourBilling':True,'directTariffClassable':True},'network':{'paysDeBarrHarmonizationReferenced':True,'scopeNote':'Exact tariff is directly validated for City of Barr municipal charging. The deliberation references CCPB harmonisation at Jardin des Sports, but this file does not automatically extend the tariff to every future Pays de Barr charger.'},'operatorDirect':{'energyEurPerKwh':0.32,'connectedTime':{'thresholdMinutes':120,'eurPerStartedHourAfterThreshold':2.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'startedHourMustBeModeled':True,'applyExactlyToBarrMunicipalChargers':True,'stationTestsDeferred':True},'sourceEvidence':{'officialOnly':True,'officialUrl':final,'officialHttpStatus':st,'officialSha256':hashlib.sha256(raw).hexdigest(),'decisionDate':'2025-01-27'},'publicationStatus':'validated_candidate'}
 (o/'barr_municipal_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Barr municipal charging\n\nOfficial 27 January 2025 municipal tariff: 0.32 EUR/kWh, plus 2 EUR per started hour after two hours plugged in. The deliberation references tariff harmonisation with CCPB Jardin des Sports; do not extrapolate to every future Pays de Barr charger without station/network confirmation.\n')
if __name__=='__main__':main()
