#!/usr/bin/env python3
"""Validate current official Duferco Mobility Italy consumer tariff rules.

The activation page is client-rendered, so validation uses the visible browser text.
Commercial rules are stored without inferring any Quick/Fast/Ultra power threshold;
station-class resolution remains a separate, fail-closed step.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

URL='https://attivazioneonline-emobility.dufercoenergia.com/'
OUT=Path('data/reference/duferco_italy_offers.json')

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def norm(s):return re.sub(r'\s+',' ',str(s).lower().replace('–','-').replace('—','-').replace('\u00a0',' ')).strip()

def rendered_text():
    o=Options();o.add_argument('--headless=new');o.add_argument('--no-sandbox');o.add_argument('--disable-dev-shm-usage');o.add_argument('--window-size=1440,2200');o.add_argument('--lang=it-IT')
    d=webdriver.Chrome(options=o)
    try:
        d.set_page_load_timeout(60)
        d.get(URL)
        deadline=time.time()+35
        best=''
        while time.time()<deadline:
            try:t=d.execute_script("return document.body ? document.body.innerText : ''") or ''
            except Exception:t=''
            if len(t)>len(best):best=t
            n=norm(best)
            if ('pay per use' in n and ('0,74' in n or '0.74' in n) and ('100 kwh' in n or '150 kwh' in n or '400 kwh' in n)):
                break
            time.sleep(1)
        return best
    finally:d.quit()

def has_price(t,val):
    a=str(val).replace('.',',');b=str(val)
    return (a in t or b in t) and ('€/kwh' in t or '€ / kwh' in t or '€/ kwh' in t)

def main():
    t=norm(rendered_text())
    # Validate each fact independently. Matching is intentionally tolerant only to spacing,
    # decimal separator and nearby wording; missing visible evidence fails the run.
    checks={
      'payPerUseVisible':'pay per use' in t,
      'peakQf':has_price(t,0.74) and ('quick' in t and 'fast' in t),
      'peakUltra':has_price(t,0.79) and ('ultra fast' in t or 'ultrafast' in t),
      'offpeakQf':has_price(t,0.52),
      'offpeakUltra':has_price(t,0.74) and ('ultra fast' in t or 'ultrafast' in t),
      'morningPeak':('08:00' in t or '8:00' in t) and '12:00' in t,
      'middayDiscount':'12:00' in t and '15:00' in t,
      'eveningPeak':'15:00' in t and '22:00' in t,
      'sameBandRule':(('inizio' in t and 'fine' in t) and ('medesima fascia' in t or 'stessa fascia' in t)),
      'roamingStationSpecific':(('costo indicato' in t or 'prezzo indicato' in t) and 'd-mobility' in t),
      'prepaid100':('65' in t and '100 kwh' in t),
      'prepaid150':('95' in t and '150 kwh' in t),
      'prepaid400':('249' in t and '400 kwh' in t),
      'prepaid3months':('3 mesi' in t),
      'prepaidUpTo50':('50 kw' in t and ('fino a' in t or '≤' in t or 'massimo' in t)),
    }
    if not all(checks.values()):
        # Log only booleans and a harmless length; do not dump the full rendered page.
        raise RuntimeError(f'Official Duferco visible evidence incomplete: checks={checks} renderedChars={len(t)}')
    payload={
      'schemaVersion':1,'generatedAt':now(),'country':'IT','provider':'Duferco Mobility','source':{'url':URL,'official':True,'validationMode':'rendered_visible_text'},
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
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'checks':checks,'renderedChars':len(t),'payPerUse':payload['payPerUseOwnCpo'],'prepaid':payload['prepaid']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
