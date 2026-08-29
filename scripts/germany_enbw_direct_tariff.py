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

def parse_mode(text,mode):
    # Example: AC: 70 ct/kWh | Blockiergebühr nach 120 min Anschlussdauer: 12 ct/min
    m=re.search(rf'\b{mode}\s*:\s*([0-9]+)\s*ct\s*/?\s*kWh.{0,180}?Blockiergebühr\s+nach\s+([0-9]+)\s*min.{0,100}?([0-9]+)\s*ct\s*/?\s*min',text,re.I)
    if not m: raise RuntimeError(f'Could not parse {mode} intercharge-direct tariff')
    return {'currency':'EUR','eurPerKwh':int(m.group(1))/100,'blockingFee':{'afterMinutes':int(m.group(2)),'eurPerMinute':int(m.group(3))/100}}

def main():
    raw,source=fetch(); text=textify(raw)
    if 'intercharge direct' not in text.lower(): raise RuntimeError('intercharge direct section not found')
    ac=parse_mode(text,'AC'); dc=parse_mode(text,'DC')
    gross=bool(re.search(r'angegebenen Preise sind Bruttopreise',text,re.I))
    if not gross: raise RuntimeError('Gross-price statement not found')
    ac['taxIncluded']=True;dc['taxIncluded']=True
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
