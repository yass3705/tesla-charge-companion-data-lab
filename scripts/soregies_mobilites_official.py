#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html, io, json, re, time, unicodedata, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
OFFER_URL='https://www.soregies.fr/offre-mobilite-electrique/'
PLUS_URL='https://www.soregies.fr/soregies-mobilites-offre-de-recharge-avec-abonnement-et-sans-engagement/'
PRO_URL='https://www.soregies.fr/professionnels/soregies-mobilites-pro/'
DATASET_PAGE='https://www.data.gouv.fr/datasets/bornes-de-recharges-soregies'
DATASET_CSV='https://www.data.gouv.fr/api/1/datasets/r/acdcb053-0e0a-4c9a-a8e8-7c283d7ed240'
LEGACY_GRID_URL='https://www.soregies.fr/wp-content/uploads/sites/10/2025/11/Tarifs-soregies-mobilites-TTC-01-11.pdf'

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
    oraw,os=fetch(OFFER_URL); praw,ps=fetch(PLUS_URL); pro_raw,pro_s=fetch(PRO_URL); dr,ds=fetch(DATASET_PAGE); cr,cs=fetch(DATASET_CSV)
    if min(os,ps,pro_s,ds,cs)!=200: raise RuntimeError('one or more official sources non-200')
    offer=text_html(oraw); plus=text_html(praw); pro=text_html(pro_raw); dataset=text_html(dr)
    require(offer,'Plus de 500 points de charge','950 000','4,99','0,22','0,27','12€',label='current offer')
    require(plus,'-20%','4,99','0,22','0,27',label='mobilites plus')
    require(pro,'Sorégies Mobilités Pro','application Sorégies Mobilités','carte bancaire','Normale','Accéléré','Rapide','Ultra-rapide',label='pro offer')
    require(dataset,'Sorégies Mobilités','Gireve','application Sorégies Mobilités','carte bancaire',label='dataset')
    rows=parse_csv(cr)
    if len(rows)<100: raise RuntimeError(f'technical dataset unexpectedly small: {len(rows)}')
    smp=samples(rows,3)
    if len(smp)<3: raise RuntimeError('unable to resolve three station samples')
    facts={
      'classification':{'regionalPublicNetwork':True,'scope':'Vienne','operator':'Sorégies','officialDatasetRows':len(rows),'currentRetailModelAmbiguous':True},
      'currentMarketingOffer':{'mobilitesPlusMonthlyEur':4.99,'mobilitesPlusHeadlineEurPerKwh':0.22,'mobilitesPlusDiscountClaimPct':20,'classicCardOneTimeEur':12.0,'classicHeadlineEurPerKwh':0.27,'headlineValuesSafeAsUniversalStationTariff':False},
      'access':{'app':True,'soregiesCard':True,'bankCardInApp':True},
      'roaming':{'gireveIncomingSupported':True,'outgoingCardCoverageClaimedPoints':950000,'thirdPartyRetailMustRemainSeparate':True},
      'technical':{'normalMaxKw':18,'acceleratedMaxKw':50,'rapidRangeKw':'50-200','ultraRapidMinKw':200,'stationExamplesFromOfficialDataset':smp},
      'legacyDetailedGrid':{'sourceUrl':LEGACY_GRID_URL,'date':'2025-11-01','machineReachableInCurrentWorkflow':False,'doNotUseAsCurrentCalculatorTariff':True},
      'tccDecision':{'networkValidated':True,'currentHeadlineOfferValidated':True,'currentExactCalculatorGridValidated':False,'reason':'live official 2026 pages expose headline 0.22/0.27 EUR/kWh offers and require station/app lookup for the tariff in force per charger; the former detailed PDF now returns 404 from GitHub Actions'}
    }
    fp=hashlib.sha256(json.dumps(facts,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    payload={'schemaVersion':'1.1.0','dataset':'soregies-mobilites-official-vienne','generatedAt':now(),'operator':'Sorégies Mobilités','country':'FR',**facts,'sourceEvidence':{'officialOnly':True,'sources':[{'key':'currentOffer','url':OFFER_URL,'httpStatus':os,'sha256':hashlib.sha256(oraw).hexdigest()},{'key':'plusOffer','url':PLUS_URL,'httpStatus':ps,'sha256':hashlib.sha256(praw).hexdigest()},{'key':'proOffer','url':PRO_URL,'httpStatus':pro_s,'sha256':hashlib.sha256(pro_raw).hexdigest()},{'key':'dataGouvPage','url':DATASET_PAGE,'httpStatus':ds,'sha256':hashlib.sha256(dr).hexdigest()},{'key':'dataGouvCsv','url':DATASET_CSV,'httpStatus':cs,'sha256':hashlib.sha256(cr).hexdigest()}],'fingerprint':fp},'publicationStatus':'candidate_validated_source_current_price_manual_check_required','notes':['Do not treat 0.22 or 0.27 EUR/kWh as a universal per-station tariff.','Current official pages explicitly direct users to the map/app for the tariff in force at each charger.','Third-party eMSP prices remain separate from Sorégies direct pricing.','The former detailed 2025-11 tariff PDF is recorded only as legacy context because it now returns 404 from GitHub Actions.']}
    out=Path('out/soregies'); out.mkdir(parents=True,exist_ok=True)
    (out/'soregies_mobilites_official_vienne.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['# Sorégies Mobilités official check','','- Live 2026 official pages: Mobilités+ 4.99 EUR/month, headline 0.22 EUR/kWh and -20%; classic headline 0.27 EUR/kWh with 12 EUR one-time card.','- These are not generalized as universal station tariffs; Sorégies directs users to the map/app for the tariff in force per charger.','- App/card access, bank-card payment in app, Gireve roaming and official technical dataset verified.','- Power families currently documented: normal up to 18 kW, accelerated up to 50 kW, rapid 50-200 kW, ultra-rapid above 200 kW.','- Former detailed 2025-11 PDF is now 404 in Actions and is not used as a current calculator source.',f'- Official technical dataset rows: {len(rows)}; three real station samples embedded.',f'- Fingerprint: `{fp}`']
    (out/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__': main()
