#!/usr/bin/env python3
"""Extract EnBW own-network ad-hoc intercharge direct prices from official FAQ.

The tariff is connector-class dependent (AC/DC), so this artifact deliberately
contains no single site-level effective price.
"""
from __future__ import annotations
import hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path

URL='https://www.enbw.com/service/faq/e-mobilitaet'
UA='Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)'

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'de-DE,de;q=0.9'})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read(); meta={'url':URL,'status':getattr(r,'status',200),'contentType':r.headers.get('Content-Type'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    return raw,meta

def textify(raw):
    s=raw.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()

def intercharge_windows(text):
    low=text.lower(); start=0
    while True:
        idx=low.find('intercharge direct',start)
        if idx<0: break
        yield text[max(0,idx-800):idx+5000]
        start=idx+1

def parse_mode(text,mode):
    # CMS markup can insert substantial text between the label, kWh price and
    # blocking-fee sentence. Search only windows surrounding intercharge direct.
    patterns=[
        rf'\b{mode}\b\s*:?.{{0,500}}?([0-9]{{2}})\s*ct\s*/?\s*kWh.{{0,1200}}?Blockiergebühr.{{0,300}}?([0-9]{{2,3}})\s*min.{{0,500}}?([0-9]{{2}})\s*ct\s*/?\s*min',
        rf'\b{mode}\b\s*:?.{{0,500}}?([0-9]{{2}})\s*ct.{{0,80}}?kWh.{{0,1200}}?([0-9]{{2,3}})\s*min.{{0,500}}?([0-9]{{2}})\s*ct.{{0,80}}?min',
    ]
    for window in intercharge_windows(text):
        for pattern in patterns:
            m=re.search(pattern,window,re.I|re.S)
            if m:
                price=int(m.group(1)); after=int(m.group(2)); per_min=int(m.group(3))
                return {'currency':'EUR','eurPerKwh':price/100,'blockingFee':{'afterMinutes':after,'eurPerMinute':per_min/100}}
    diagnostic=[]
    for window in intercharge_windows(text):
        diagnostic.append(window[:1200])
        if len(diagnostic)>=2: break
    raise RuntimeError(f'Could not parse {mode} intercharge-direct tariff; windows={diagnostic!r}')

def main():
    raw,source=fetch(); text=textify(raw)
    if 'intercharge direct' not in text.lower(): raise RuntimeError('intercharge direct section not found')
    ac=parse_mode(text,'AC'); dc=parse_mode(text,'DC')
    gross=bool(re.search(r'angegebenen Preise sind Bruttopreise',text,re.I))
    if not gross: raise RuntimeError('Gross-price statement not found')
    # Values are validated against the current official FAQ contract before output.
    expected={'AC':(0.70,120,0.12),'DC':(0.79,30,0.24)}
    for mode,row in [('AC',ac),('DC',dc)]:
        price,after,minute=expected[mode]
        if row['eurPerKwh']!=price or row['blockingFee']['afterMinutes']!=after or row['blockingFee']['eurPerMinute']!=minute:
            raise RuntimeError(f'Unexpected {mode} official values: {row}')
        row['taxIncluded']=True
    result={
      'schemaVersion':'0.1.0','dataset':'germany-enbw-direct-tariff','countryCode':'DE','generatedAt':now(),
      'scope':{'stagedOnly':True,'publishesToTcc':False,'operatorOwnNetworkOnly':True,'siteScalarPriceSafe':False,'requiresConnectorClass':True},
      'source':source,
      'operator':{'canonicalName':'EnBW mobility+','bnetzaExactOperators':['EnBW mobility+ AG und Co.KG']},
      'directOwnNetwork':{
        'accessMethod':'intercharge direct','monthlyFeeEur':0.0,'connectorClassTariffs':{'AC':ac,'DC':dc},
        'rankableCandidateWhenConnectorClassKnown':True,'siteLevelRankableCandidate':False
      }
    }
    out=Path('data/germany/enbw_direct_tariff.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_ENBW_DIRECT_TARIFF='+json.dumps(result,ensure_ascii=False,sort_keys=True))
if __name__=='__main__': main()
