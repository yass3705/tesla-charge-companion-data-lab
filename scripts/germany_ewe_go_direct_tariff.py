#!/usr/bin/env python3
"""Extract the official EWE Go own/partner charging tariff from ewe-go.de.

Staging source artifact only. The own-network tariff is eligible to become a
direct-CPO candidate; the partner price is retained for future roaming logic but
is not applied to other operators by this script.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL="https://www.ewe-go.de/ladetarif"
UA="Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"


def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'de-DE,de;q=0.9'})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read(); status=getattr(r,'status',200); ctype=r.headers.get('Content-Type')
    return raw,{'url':URL,'status':status,'contentType':ctype,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def textify(raw:bytes):
    s=raw.decode('utf-8','replace')
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s)
    s=html.unescape(s).replace('\xa0',' ')
    return re.sub(r'\s+',' ',s).strip()


def price_after(text,label):
    # Official page wording is stable but allow punctuation/spacing variation.
    m=re.search(re.escape(label)+r'.{0,220}?([0-9]+[,.][0-9]{2})\s*€\s*/?\s*kWh',text,re.I)
    if not m: raise RuntimeError(f'Could not find price after label {label!r}')
    return float(m.group(1).replace(',','.'))


def main():
    raw,transport=fetch(); text=textify(raw)
    own=price_after(text,'EWE Go-Ladestation')
    partner=price_after(text,'Partner-Ladestation')
    vat=bool(re.search(r'Alle Preise inkl\.?\s*19\s*%\s*MwSt',text,re.I))
    no_monthly=bool(re.search(r'Keine monatliche Grundgebühr',text,re.I))
    partner_only_block=bool(re.search(r'Blockiergebühr.{0,120}ausschließlich an Partner-Ladestationen',text,re.I))
    block=re.search(r'Ab\s*4\s*Std\.?\s*Standzeit\s*0[,.]10\s*€\s*/?\s*Min\..{0,100}?max\.?\s*24[,.]00\s*€',text,re.I)
    if not (vat and no_monthly and partner_only_block and block):
        raise RuntimeError('Official EWE Go tariff conditions could not be validated')
    result={
      'schemaVersion':'0.1.0','dataset':'germany-ewe-go-direct-tariff','countryCode':'DE','generatedAt':now(),
      'scope':{'stagedOnly':True,'publishesToTcc':False,'operatorOwnNetworkOnly':True,'partnerTariffStoredButNotApplied':True},
      'source':transport,
      'operator':{'canonicalName':'EWE Go','bnetzaExactOperators':['EWE Go GmbH']},
      'directOwnNetwork':{'currency':'EUR','eurPerKwh':own,'acDcSamePrice':True,'monthlyFeeEur':0.0,'taxIncluded':vat,'blockingFee':None,'rankableCandidate':True},
      'roamingPartner':{'currency':'EUR','eurPerKwh':partner,'taxIncluded':vat,'blockingFee':{'afterMinutes':240,'eurPerMinute':0.10,'capEurPerSession':24.0},'rankableCandidate':False},
      'evidence':{'noMonthlyBaseFee':no_monthly,'blockingFeeOnlyPartnerStations':partner_only_block}
    }
    out=Path('data/germany/ewe_go_direct_tariff.json');out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_EWE_GO_DIRECT_TARIFF='+json.dumps(result,ensure_ascii=False,sort_keys=True))

if __name__=='__main__':main()
