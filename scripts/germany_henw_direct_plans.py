#!/usr/bin/env python3
"""Extract Hamburger Energiewerke (HEnW) consumer charging plans.

All HEnW plans require an account/tariff choice and are therefore opt-in plan
candidates. None is automatically selected in TCC staging, including Basis with
zero monthly fee. Multiple official HEnW pages are accepted because their CMS
occasionally returns HTTP 500 to non-browser clients.
"""
from __future__ import annotations
import hashlib,html,json,re,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path

PRICE_URLS=[
 'https://www.hamburger-energiewerke.de/e-mobilitaet/private-e-mobilitaet/ladestromtarife',
 'https://www.hamburger-energiewerke.de/services/magazin/neues-ladestromangebot-henw-drive',
]
BLOCK_URLS=[
 'https://www.hamburger-energiewerke.de/e-mobilitaet/private-e-mobilitaet/laden-und-abrechnung',
 'https://www.hamburger-energiewerke.de/e-mobilitaet/wissen-e-mobilitaet/hilfe-faq',
]
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def fetch_one(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'de-DE,de;q=0.9,en;q=0.5'})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read();meta={'url':url,'status':getattr(r,'status',200),'contentType':r.headers.get('Content-Type'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    return raw,meta
def fetch_any(urls,label):
    errors=[]
    for url in urls:
        try:return fetch_one(url)
        except Exception as exc:errors.append(f'{url}: {type(exc).__name__}: {exc}')
    raise RuntimeError(f'No official HEnW {label} source reachable: {errors}')
def textify(raw):
    s=raw.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def require(pattern,text,label):
    if not re.search(pattern,text,re.I|re.S):raise RuntimeError(f'Missing official HEnW evidence: {label}')

def main():
    price_raw,price_source=fetch_any(PRICE_URLS,'tariff');block_raw,block_source=fetch_any(BLOCK_URLS,'blocking-fee')
    price_text=textify(price_raw);block_text=textify(block_raw)
    # Current consumer tariff table.
    require(r'Ladetarif\s+Basis',price_text,'Basis')
    require(r'Ladetarif\s+Plus',price_text,'Plus')
    require(r'Kombi\s+Smart',price_text,'Kombi Smart')
    require(r'Basis.{0,2500}?AC\s*59\s*ct\s*/?\s*kWh.{0,250}?DC\s*69\s*ct\s*/?\s*kWh',price_text,'Basis AC/DC prices')
    require(r'Plus.{0,3000}?AC\s*49\s*ct\s*/?\s*kWh.{0,250}?DC\s*59\s*ct\s*/?\s*kWh',price_text,'Plus AC/DC prices')
    require(r'Kombi\s+Smart.{0,3000}?AC\s*49\s*ct\s*/?\s*kWh.{0,250}?DC\s*59\s*ct\s*/?\s*kWh',price_text,'Kombi AC/DC prices')
    require(r'Roamingpartner.{0,1800}?AC\s*65\s*ct\s*/?\s*kWh.{0,250}?DC\s*75\s*ct\s*/?\s*kWh',price_text,'roaming prices')
    require(r'Basis.{0,1800}?Monatliche\s+Grundgebühr.{0,800}?0\s*€',price_text,'Basis monthly fee')
    require(r'Plus.{0,2200}?4[,.]99\s*€',price_text,'Plus monthly fee')
    require(r'Alle\s+Preise.{0,180}?Mehrwertsteuer|Preise.{0,180}?inkl\.',price_text,'VAT statement')
    # Blocking fee evidence may live on another official page.
    require(r'AC.{0,160}?181\s*Minuten.{0,500}?DC.{0,160}?61\s*Minuten',block_text,'blocking thresholds')
    require(r'5\s*ct\s*/?\s*Min.{0,250}?18\s*€',block_text,'blocking price/cap')
    require(r'nicht.{0,180}?zwischen\s*20:00\s*Uhr\s*und\s*9:00\s*Uhr|nicht.{0,180}?20.?9\s*Uhr',block_text,'night exemption')

    block={'eurPerMinute':0.05,'capEurPerSession':18.0,'activeLocalTime':{'start':'09:00','end':'20:00'},'inactiveLocalTime':{'start':'20:00','end':'09:00'},'afterMinutesByConnectorClass':{'AC':181,'DC':61}}
    own_basis={'AC':0.59,'DC':0.69};own_discount={'AC':0.49,'DC':0.59};roaming={'AC':0.65,'DC':0.75}
    plans=[
      {'planId':'henw_basis','name':'HEnW Basis','userSelectionRequired':True,'eligibility':'public_account','monthlyFeeEur':0.0,'oneTimeOptionalCardFeeEur':9.99,'ownNetworkEurPerKwh':own_basis,'roamingEurPerKwh':roaming,'taxIncluded':True,'blockingFeeOwnNetwork':block},
      {'planId':'henw_plus','name':'HEnW Plus','userSelectionRequired':True,'eligibility':'public_account','monthlyFeeEur':4.99,'oneTimeOptionalCardFeeEur':4.99,'ownNetworkEurPerKwh':own_discount,'roamingEurPerKwh':roaming,'taxIncluded':True,'blockingFeeOwnNetwork':block},
      {'planId':'henw_kombi_smart','name':'HEnW Kombi Smart','userSelectionRequired':True,'eligibility':'active_henw_electricity_contract','monthlyFeeEur':0.0,'oneTimeOptionalCardFeeEur':4.99,'ownNetworkEurPerKwh':own_discount,'roamingEurPerKwh':roaming,'taxIncluded':True,'blockingFeeOwnNetwork':block},
    ]
    result={'schemaVersion':'0.1.0','dataset':'germany-henw-direct-plans','countryCode':'DE','generatedAt':now(),'scope':{'stagedOnly':True,'publishesToTcc':False,'allPlansOptIn':True,'roamingStoredButNotApplied':True},'sources':{'tariff':price_source,'blockingFee':block_source},'operator':{'canonicalName':'Hamburger Energiewerke Mobil','bnetzaExactOperators':['Hamburger Energiewerke Mobil']},'plans':plans}
    out=Path('data/germany/henw_direct_plans.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_HENW_DIRECT_PLANS='+json.dumps(result,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
