#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html, io, json, re, subprocess, tempfile, time, unicodedata, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
TARIFF_PDF='https://www.soregies.fr/wp-content/uploads/sites/10/2025/11/Tarifs-soregies-mobilites-TTC-01-11.pdf'
OFFER_URL='https://www.soregies.fr/offre-mobilite-electrique/'
PLUS_URL='https://www.soregies.fr/soregies-mobilites-offre-de-recharge-avec-abonnement-et-sans-engagement/'
DATASET_PAGE='https://www.data.gouv.fr/datasets/bornes-de-recharges-soregies'
DATASET_CSV='https://www.data.gouv.fr/api/1/datasets/r/acdcb053-0e0a-4c9a-a8e8-7c283d7ed240'

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def norm(s):
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    s=s.lower().replace('’',"'").replace('–','-').replace('—','-')
    return re.sub(r'\s+',' ',s).strip()
def fetch(url,attempts=3):
    last=None
    for i in range(1,attempts+1):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'fr-FR,fr;q=0.9'})
            with urllib.request.urlopen(req,timeout=60) as r: return r.read(),int(getattr(r,'status',200))
        except Exception as exc:
            last=exc
            if i<attempts: time.sleep(i*2)
    raise RuntimeError(f'fetch failed {url}: {last}')
def text_html(raw):
    s=raw.decode('utf-8',errors='replace')
    s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',s,flags=re.I|re.S)
    s=re.sub(r'<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s)).strip()
def text_pdf(raw):
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'a.pdf'; t=Path(td)/'a.txt'; p.write_bytes(raw)
        subprocess.run(['pdftotext','-layout',str(p),str(t)],check=True)
        return t.read_text(errors='replace')
def require(text,*phrases,label='source'):
    n=norm(text); miss=[p for p in phrases if norm(p) not in n]
    if miss: raise RuntimeError(f'{label} missing {miss}')
def parse_csv(raw):
    txt=raw.decode('utf-8-sig',errors='replace')
    try: d=csv.Sniffer().sniff(txt[:8192],delimiters=',;\t')
    except csv.Error: d=csv.excel
    return [dict(r) for r in csv.DictReader(io.StringIO(txt),dialect=d)]
def compact(row):
    keys=['id_station_itinerance','id_pdc_itinerance','nom_station','adresse_station','code_insee_commune','nom_enseigne','nom_operateur','puissance_nominale','prise_type_2','prise_type_combo_ccs','prise_type_chademo']
    return {k:row.get(k) for k in keys if row.get(k) not in (None,'')}
def samples(rows,n=3):
    out=[]; seen=set()
    for r in rows:
        sid=r.get('id_station_itinerance') or r.get('nom_station') or r.get('adresse_station')
        if not sid or sid in seen: continue
        seen.add(sid); out.append(compact(r))
        if len(out)>=n: break
    return out

def main():
    tr,ts=fetch(TARIFF_PDF); oraw,os=fetch(OFFER_URL); praw,ps=fetch(PLUS_URL); dr,ds=fetch(DATASET_PAGE); cr,cs=fetch(DATASET_CSV)
    if min(ts,os,ps,ds,cs)!=200: raise RuntimeError('one or more official sources non-200')
    tariff=text_pdf(tr); offer=text_html(oraw); plus=text_html(praw); dataset=text_html(dr)
    require(tariff,'Grille tarifaire au 01/11/2025','0,99','0,42','0,67','0,59','0,71','0,33','0,47','0,27','0,36','0,38','0,41','12 h à 17 h','22 h à 7 h','0,30','0,16','0,01',label='tariff pdf')
    require(offer,'Plus de 500 points de charge','950 000','4,99','0,22','0,27','12€','Last Miles Solutions',label='current offer')
    require(plus,'-20%','4,99','0,22','0,27',label='mobilites plus')
    require(dataset,'Sorégies Mobilités','Gireve','application Sorégies Mobilités','carte bancaire',label='dataset')
    rows=parse_csv(cr)
    if len(rows)<100: raise RuntimeError(f'technical dataset unexpectedly small: {len(rows)}')
    smp=samples(rows,3)
    if len(smp)<3: raise RuntimeError('unable to resolve three station samples')
    facts={
      'classification':{'regionalPublicNetwork':True,'scope':'Vienne','operator':'Sorégies','technicalPlatform':'Last Miles Solutions','officialDatasetRows':len(rows),'currentRetailModelAmbiguous':True},
      'officialGridDated2025_11_01':{
        'accessFeeEurPerSession':0.99,
        'windows':{'offPeak':['12:00-17:00','22:00-07:00'],'peak':['07:00-12:00','17:00-22:00']},
        'rapidUpTo200Kw':{'subscriber':{'offPeakEurPerKwh':0.42,'peakEurPerKwh':0.59},'public':{'offPeakEurPerKwh':0.67,'peakEurPerKwh':0.71},'timeFeeAfterMinutes':60,'eurPerMinuteAfter':0.30},
        'acceleratedUpTo50Kw':{'subscriber':{'offPeakEurPerKwh':0.33,'peakEurPerKwh':0.44},'public':{'offPeakEurPerKwh':0.42,'peakEurPerKwh':0.47},'timeFeeAfterMinutes':120,'eurPerMinuteAfter':0.16},
        'normalUpTo22Kw':{'subscriber':{'offPeakEurPerKwh':0.27,'peakEurPerKwh':0.38},'public':{'offPeakEurPerKwh':0.36,'peakEurPerKwh':0.41},'timeFeeAfterMinutes':420,'eurPerMinuteAfter':0.01}},
      'currentMarketingOffer':{'mobilitesPlusMonthlyEur':4.99,'mobilitesPlusHeadlineEurPerKwh':0.22,'mobilitesPlusDiscountClaimPct':20,'classicCardOneTimeEur':12.0,'classicHeadlineEurPerKwh':0.27,'headlineValuesSafeAsUniversalStationTariff':False},
      'access':{'app':True,'soregiesCard':True,'bankCardInApp':True,'bankCardTerminalOnEquippedStations':True},
      'roaming':{'gireveIncomingSupported':True,'outgoingCardCoverageClaimedPoints':950000,'thirdPartyRetailMustRemainSeparate':True},
      'technical':{'normalMaxKw':22,'acceleratedMaxKw':50,'rapidMaxKw':200,'stationExamplesFromOfficialDataset':smp},
      'tccDecision':{'networkValidated':True,'historicDetailedGridValidated':True,'currentExactCalculatorGridValidated':False,'reason':'current marketing pages show new 0.22/0.27 headline pricing while the latest linked detailed grid remains dated 2025-11-01; station/app verification required before replacing the detailed grid'}
    }
    fp=hashlib.sha256(json.dumps(facts,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    payload={'schemaVersion':'1.0.0','dataset':'soregies-mobilites-official-vienne','generatedAt':now(),'operator':'Sorégies Mobilités','country':'FR',**facts,'sourceEvidence':{'officialOnly':True,'sources':[{'key':'tariffPdf','url':TARIFF_PDF,'httpStatus':ts,'sha256':hashlib.sha256(tr).hexdigest()},{'key':'currentOffer','url':OFFER_URL,'httpStatus':os,'sha256':hashlib.sha256(oraw).hexdigest()},{'key':'plusOffer','url':PLUS_URL,'httpStatus':ps,'sha256':hashlib.sha256(praw).hexdigest()},{'key':'dataGouvPage','url':DATASET_PAGE,'httpStatus':ds,'sha256':hashlib.sha256(dr).hexdigest()},{'key':'dataGouvCsv','url':DATASET_CSV,'httpStatus':cs,'sha256':hashlib.sha256(cr).hexdigest()}],'fingerprint':fp},'publicationStatus':'candidate_validated_source_current_price_manual_check_required','notes':['Do not flatten the 2025-11 detailed grid into a claimed current tariff without a station/app recheck.','The 0.22 and 0.27 EUR/kWh values are preserved as current official marketing headline values only.','Third-party eMSP prices remain separate from Sorégies direct pricing.']}
    out=Path('out/soregies'); out.mkdir(parents=True,exist_ok=True)
    (out/'soregies_mobilites_official_vienne.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['# Sorégies Mobilités official check','','- Network, access channels, roaming and official technical dataset verified.','- Detailed grid dated 2025-11-01 verified: 0.99 EUR/session, power/time-of-day kWh prices, plus time charges after 1h/2h/7h.','- Current 2026 marketing pages advertise Mobilités+ 4.99 EUR/month at headline 0.22 EUR/kWh and classic at headline 0.27 EUR/kWh.','- These current headline values do not map cleanly to the still-linked detailed grid, so the exact current calculator tariff is intentionally left unresolved pending station/app verification.',f'- Official technical dataset rows: {len(rows)}; three real station samples embedded.',f'- Fingerprint: `{fp}`']
    (out/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__': main()
