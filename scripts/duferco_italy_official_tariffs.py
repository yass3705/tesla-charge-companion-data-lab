#!/usr/bin/env python3
"""Validate current official Duferco Mobility Italy consumer tariff rules.

This stores commercial rules only. It deliberately does not infer a power threshold for
Quick/Fast vs Ultra Fast; station-class resolution is handled separately from map/PUN data.
"""
from __future__ import annotations
import html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path

URL='https://attivazioneonline-emobility.dufercoenergia.com/'
OUT=Path('data/reference/duferco_italy_offers.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def fetch():
    r=urllib.request.Request(URL,headers={'User-Agent':UA,'Accept-Language':'it-IT,it;q=0.9,en;q=0.5'})
    with urllib.request.urlopen(r,timeout=45) as x:return x.read().decode(x.headers.get_content_charset() or 'utf-8','replace')
def text(raw):
    s=re.sub(r'<script\b[^>]*>.*?</script>',' ',raw,flags=re.I|re.S);s=re.sub(r'<style\b[^>]*>.*?</style>',' ',s,flags=re.I|re.S);s=re.sub(r'<[^>]+>',' ',s);return re.sub(r'\s+',' ',html.unescape(s)).strip()
def n(s):return re.sub(r'\s+',' ',s.lower().replace('–','-').replace('—','-')).strip()
def has(t,*parts):return all(p.lower() in t for p in parts)
def main():
    t=n(text(fetch()))
    checks={
      'peakQf':bool(re.search(r'0[,.]74\s*€/kwh.*quick.*fast',t,re.I)),
      'peakUltra':bool(re.search(r'0[,.]79\s*€/kwh.*ultra\s*fast',t,re.I)),
      'offpeakQf':'0,52 €/kwh' in t or '0.52 €/kwh' in t,
      'offpeakUltra':bool(re.search(r'0[,.]74\s*€/kwh.*ultra\s*fast',t,re.I)),
      'sameBandRule':('inizio' in t and 'fine' in t and 'medesima fascia' in t),
      'roamingStationSpecific':('al costo indicato' in t and ('d-mobility app' in t or 'd-mobility' in t)),
      'prepaid100':('65' in t and '100 kwh' in t),
      'prepaid150':('95' in t and '150 kwh' in t),
      'prepaid400':('249' in t and '400 kwh' in t),
      'prepaid3months':('3 mesi' in t),
      'prepaidUpTo50':('fino a 50 kw' in t),
    }
    if not all(checks.values()):raise RuntimeError(f'Official Duferco evidence incomplete: {checks}')
    payload={
      'schemaVersion':1,'generatedAt':now(),'country':'IT','provider':'Duferco Mobility','source':{'url':URL,'official':True},
      'payPerUseOwnCpo':{
        'priceGranularity':'network_class_and_local_time','currency':'EUR','vatIncluded':True,'localTimeZone':'Europe/Rome',
        'classes':{
          'QUICK_OR_FAST':{'mondayToSaturday':[{'start':'08:00','end':'12:00','energyEurPerKwh':0.74,'discounted':False},{'start':'12:00','end':'15:00','energyEurPerKwh':0.52,'discounted':True},{'start':'15:00','end':'22:00','energyEurPerKwh':0.74,'discounted':False},{'start':'22:00','end':'08:00','energyEurPerKwh':0.52,'discounted':True}],'sundayOrItalianPublicHoliday':0.52},
          'ULTRA_FAST':{'mondayToSaturday':[{'start':'08:00','end':'12:00','energyEurPerKwh':0.79,'discounted':False},{'start':'12:00','end':'15:00','energyEurPerKwh':0.74,'discounted':True},{'start':'15:00','end':'22:00','energyEurPerKwh':0.79,'discounted':False},{'start':'22:00','end':'08:00','energyEurPerKwh':0.74,'discounted':True}],'sundayOrItalianPublicHoliday':0.74}},
        'resolutionRules':{'discountedRateRequiresSessionStartAndEndInSameEligibleBandOrDay':True,'crossBandSession':'fail_closed_unrankable','italianPublicHolidayCalendarRequired':True,'stationClassMustBeResolvedFromValidatedSource':True},
        'rankable':True,
      },
      'roaming':{'priceModel':'station_specific_in_d_mobility','singleNationalPrice':None,'rankableWithoutStationFeed':False},
      'prepaid':[{'id':'duferco_prepaid_100','priceEur':65,'includedKwh':100,'validityMonths':3,'eligible':'Quick/Fast up to 50 kW'},{'id':'duferco_prepaid_150','priceEur':95,'includedKwh':150,'validityMonths':3,'eligible':'Quick/Fast up to 50 kW'},{'id':'duferco_prepaid_400','priceEur':249,'includedKwh':400,'validityMonths':3,'eligible':'Quick/Fast up to 50 kW'}],
      'prepaidModel':{'tccRankableWithoutRemainingBalance':False,'reason':'prepaid_credit_state_required'},
      'evidenceChecks':checks,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'checks':checks,'payPerUse':payload['payPerUseOwnCpo'],'prepaid':payload['prepaid']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
