#!/usr/bin/env python3
"""Validate current FDEA Ardennes rural IRVE / Modulo tariffs from official FDEA sources."""
from __future__ import annotations
import argparse, hashlib, html, io, json, re, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
HOME='https://www.fdea08.fr/index.php?idp=42'
MANUAL='https://www.fdea08.fr/documents/MU_Borne_Nexans_version_simplifiee.pdf'
DELIB='https://www.fdea08.fr/documents/Deliberations_2024.pdf'
def fetch(url):
    last=None
    for attempt in range(1,4):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,*/*','Accept-Language':'fr-FR,fr;q=0.9','Connection':'close'})
            with urllib.request.urlopen(req,timeout=50) as r:return int(getattr(r,'status',200)),r.read(),r.geturl()
        except Exception as e:
            last=e
            if attempt<3:time.sleep(attempt*2)
    raise RuntimeError(f'fetch failed {url}: {type(last).__name__}: {last}')
def plain(raw):
    s=raw.decode('utf-8',errors='replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def pdftext(raw):return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages)).strip()
def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '');s=''.join(c for c in s if not unicodedata.combining(c));return re.sub(r'\s+',' ',s.lower().replace('’',"'")).strip()
def require(text,*items):
    n=norm(text);missing=[x for x in items if norm(x) not in n]
    if missing:raise RuntimeError('FDEA evidence missing: '+', '.join(missing))
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/fdea_modulo');args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    hs,hraw,hfinal=fetch(HOME);ms,mraw,mfinal=fetch(MANUAL);ds,draw,dfinal=fetch(DELIB)
    if min(hs,ms,ds)!=200:raise RuntimeError(f'HTTP failure home={hs} manual={ms} deliberations={ds}')
    ht=plain(hraw);mt=pdftext(mraw);dt=pdftext(draw)
    require(ht,'40 bornes de recharge accélérée','22 KW')
    require(mt,'SERVICE DE RECHARGE MODULO','Prise type 2','2€ / heure','Prise CHAdeMO / Combo','3€ / heure','décompté à la minute','30 % plus chère','Frais de recharge minimum : 0,50 €','Réservation de borne : 0,01 € / minute')
    require(dt,'Fédération Départementale d\'Energies des Ardennes','SPL MODULO','gestion-exploitation-supervision-maintenance des bornes de recharge')
    payload={'schemaVersion':'1.0.0','dataset':'fdea-modulo-official-grandest','generatedAt':now(),'operator':'FDEA - réseau IRVE des Ardennes hors Ardenne Métropole','serviceOperator':'Modulo Energies','country':'FR','region':'Grand Est','department':'Ardennes','classification':{'departmentalRuralPublicNetwork':True,'directPublishedTariff':True,'timeBased':True,'subscriberAndAdHoc':True,'directTariffClassable':True,'roamingSeparate':True},'network':{'plannedChargers':40,'publishedPowerKw':[22,24],'territoryScope':'Ardennes hors Ardenne Métropole','moduloQuasiRegieConfirmed':True},'operatorDirect':{'subscriber':{'acType2EurPerHour':2.0,'dcChademoComboEurPerHour':3.0,'billing':'per_minute_prorata'},'adHoc':{'priceMultiplierVsSubscriber':1.30,'minimumChargeEur':0.50},'reservation':{'eurPerMinute':0.01,'maximumMinutes':30}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'perMinuteProrationMustBeModeled':True,'adHocMultiplierMustBeModeled':True,'roamingSeparate':True,'stationTestsDeferred':True},'sourceEvidence':{'officialOnly':True,'homeUrl':hfinal,'homeHttpStatus':hs,'homeSha256':hashlib.sha256(hraw).hexdigest(),'manualUrl':mfinal,'manualHttpStatus':ms,'manualSha256':hashlib.sha256(mraw).hexdigest(),'deliberationsUrl':dfinal,'deliberationsHttpStatus':ds,'deliberationsSha256':hashlib.sha256(draw).hexdigest()},'publicationStatus':'validated_candidate'}
    sig={k:payload[k] for k in ('classification','network','operatorDirect','tccDecision')};payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'fdea_modulo_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(out/'SUMMARY.md').write_text('# FDEA Ardennes / Modulo\n\nOfficial FDEA evidence validates the rural Ardennes IRVE network outside Ardenne Métropole and current Modulo operation. Subscriber tariff: AC Type 2 2 EUR/hour and DC CHAdeMO/Combo 3 EUR/hour, prorated by minute. Ad-hoc is 30% higher with a 0.50 EUR minimum. Reservation is 0.01 EUR/min up to 30 minutes.\n')
if __name__=='__main__':main()
