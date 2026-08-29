#!/usr/bin/env python3
"""Extract Hamburger Energiewerke (HEnW) consumer charging plans.

All HEnW plans require an account/tariff choice and are therefore opt-in plan
candidates. None is automatically selected in TCC staging, including Basis with
zero monthly fee.
"""
from __future__ import annotations
import hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path

URL='https://www.hamburger-energiewerke.de/e-mobilitaet/private-e-mobilitaet/ladestromtarife'
UA='Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)'

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'de-DE,de;q=0.9'})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read();meta={'url':URL,'status':getattr(r,'status',200),'contentType':r.headers.get('Content-Type'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    return raw,meta
def textify(raw):
    s=raw.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def require(pattern,text,label):
    if not re.search(pattern,text,re.I|re.S):raise RuntimeError(f'Missing official HEnW evidence: {label}')

def main():
    raw,source=fetch();text=textify(raw)
    # Validate the live page against the expected current consumer tariff table.
    require(r'Ladetarif\s+Basis',' '.join(text.split()),'Basis')
    require(r'Ladetarif\s+Plus',text,'Plus')
    require(r'Kombi\s+Smart',text,'Kombi Smart')
    require(r'Basis.{0,1500}?AC\s*59\s*ct\s*/?\s*kWh.{0,100}?DC\s*69\s*ct\s*/?\s*kWh',text,'Basis AC/DC prices')
    require(r'Plus.{0,1800}?AC\s*49\s*ct\s*/?\s*kWh.{0,100}?DC\s*59\s*ct\s*/?\s*kWh',text,'Plus AC/DC prices')
    require(r'Kombi\s+Smart.{0,1800}?AC\s*49\s*ct\s*/?\s*kWh.{0,100}?DC\s*59\s*ct\s*/?\s*kWh',text,'Kombi AC/DC prices')
    require(r'Roamingpartner.{0,1000}?AC\s*65\s*ct\s*/?\s*kWh.{0,100}?DC\s*75\s*ct\s*/?\s*kWh',text,'roaming prices')
    require(r'Blockiergebühr.{0,1200}?AC.{0,100}?181\s*Minuten.{0,250}?DC.{0,100}?61\s*Minuten.{0,250}?5\s*ct\s*/?\s*Min.{0,150}?18\s*€',text,'blocking fee')
    require(r'nicht.{0,100}?zwischen\s*20:00\s*Uhr\s*und\s*9:00\s*Uhr|nicht.{0,120}?20.?9\s*Uhr',text,'night exemption')
    require(r'Alle\s+Preise.{0,120}?Mehrwertsteuer',text,'VAT statement')

    block={'eurPerMinute':0.05,'capEurPerSession':18.0,'activeLocalTime':{'start':'09:00','end':'20:00'},'inactiveLocalTime':{'start':'20:00','end':'09:00'},'afterMinutesByConnectorClass':{'AC':181,'DC':61}}
    own_basis={'AC':0.59,'DC':0.69};own_discount={'AC':0.49,'DC':0.59};roaming={'AC':0.65,'DC':0.75}
    plans=[
      {'planId':'henw_basis','name':'HEnW Basis','userSelectionRequired':True,'eligibility':'public_account','monthlyFeeEur':0.0,'oneTimeOptionalCardFeeEur':9.99,'ownNetworkEurPerKwh':own_basis,'roamingEurPerKwh':roaming,'taxIncluded':True,'blockingFeeOwnNetwork':block},
      {'planId':'henw_plus','name':'HEnW Plus','userSelectionRequired':True,'eligibility':'public_account','monthlyFeeEur':4.99,'oneTimeOptionalCardFeeEur':4.99,'ownNetworkEurPerKwh':own_discount,'roamingEurPerKwh':roaming,'taxIncluded':True,'blockingFeeOwnNetwork':block},
      {'planId':'henw_kombi_smart','name':'HEnW Kombi Smart','userSelectionRequired':True,'eligibility':'active_henw_electricity_contract','monthlyFeeEur':0.0,'oneTimeOptionalCardFeeEur':4.99,'ownNetworkEurPerKwh':own_discount,'roamingEurPerKwh':roaming,'taxIncluded':True,'blockingFeeOwnNetwork':block},
    ]
    result={'schemaVersion':'0.1.0','dataset':'germany-henw-direct-plans','countryCode':'DE','generatedAt':now(),'scope':{'stagedOnly':True,'publishesToTcc':False,'allPlansOptIn':True,'roamingStoredButNotApplied':True},'source':source,'operator':{'canonicalName':'Hamburger Energiewerke Mobil','bnetzaExactOperators':['Hamburger Energiewerke Mobil']},'plans':plans}
    out=Path('data/germany/henw_direct_plans.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_HENW_DIRECT_PLANS='+json.dumps(result,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
