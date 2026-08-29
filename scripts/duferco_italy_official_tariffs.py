#!/usr/bin/env python3
"""Validate current official Duferco Mobility Italy consumer tariff rules.

The activation page is client-rendered. We validate against both visible text and the
rendered DOM textContent after opening native details elements. No network credentials,
storage or hidden API headers are inspected.
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

def rendered_texts():
    o=Options();o.add_argument('--headless=new');o.add_argument('--no-sandbox');o.add_argument('--disable-dev-shm-usage');o.add_argument('--window-size=1440,2400');o.add_argument('--lang=it-IT')
    d=webdriver.Chrome(options=o)
    try:
        d.set_page_load_timeout(60);d.get(URL)
        deadline=time.time()+35;visible='';full=''
        while time.time()<deadline:
            try:
                d.execute_script("document.querySelectorAll('details').forEach(x=>x.open=true)")
                v=d.execute_script("return document.body ? document.body.innerText : ''") or ''
                f=d.execute_script("return document.body ? document.body.textContent : ''") or ''
            except Exception:v=f=''
            if len(v)>len(visible):visible=v
            if len(f)>len(full):full=f
            n=norm(full+' '+visible)
            if 'pay per use' in n and any(x in n for x in ('100 kwh','150 kwh','400 kwh')) and ('0,79' in n or '0.79' in n):break
            time.sleep(1)
        return visible,full
    finally:d.quit()

def has_price(t,val):
    a=str(val).replace('.',',');b=str(val)
    return (a in t or b in t) and ('€/kwh' in t or '€ / kwh' in t or '€/ kwh' in t or 'euro/kwh' in t)

def time_pair(t,a,b):
    return (a in t or a.lstrip('0') in t) and (b in t or b.lstrip('0') in t)

def main():
    visible,full=rendered_texts();v=norm(visible);t=norm(full+' '+visible)
    checks={
      # Price cards must be actually visible, not merely present in hidden DOM.
      'payPerUseVisible':'pay per use' in v,
      'peakQfVisible':has_price(v,0.74) and ('quick' in v and 'fast' in v),
      'peakUltraVisible':has_price(v,0.79) and ('ultra fast' in v or 'ultrafast' in v),
      'offpeakQfVisible':has_price(v,0.52),
      'offpeakUltraVisible':has_price(v,0.74) and ('ultra fast' in v or 'ultrafast' in v),
      # Rules may live in collapsed components, but must exist in the rendered DOM.
      'morningPeakDom':time_pair(t,'08:00','12:00'),
      'middayDiscountDom':time_pair(t,'12:00','15:00'),
      'eveningPeakDom':time_pair(t,'15:00','22:00'),
      'sameBandRuleDom':(('inizio' in t and 'fine' in t) and ('medesima fascia' in t or 'stessa fascia' in t)),
      'roamingStationSpecificDom':(('costo indicato' in t or 'prezzo indicato' in t) and 'd-mobility' in t),
      'prepaid100Visible':('65' in v and '100 kwh' in v),
      'prepaid150Visible':('95' in v and '150 kwh' in v),
      'prepaid400Visible':('249' in v and '400 kwh' in v),
      'prepaid3monthsDom':('3 mesi' in t),
      'prepaidUpTo50Dom':('50 kw' in t and ('fino a' in t or '≤' in t or 'massimo' in t)),
    }
    core_price_keys=('payPerUseVisible','peakQfVisible','peakUltraVisible','offpeakQfVisible','offpeakUltraVisible','prepaid100Visible','prepaid150Visible','prepaid400Visible')
    if not all(checks[k] for k in core_price_keys):
        raise RuntimeError(f'Official Duferco current visible pricing incomplete: checks={checks} visibleChars={len(v)} domChars={len(t)}')
    # The detailed timing/eligibility rules remain stored fail-closed. Record whether this
    # particular frontend build exposes them in DOM rather than pretending they were seen.
    payload={
      'schemaVersion':2,'generatedAt':now(),'country':'IT','provider':'Duferco Mobility',
      'source':{'url':URL,'official':True,'validationMode':'rendered_visible_cards_plus_dom_rule_evidence','visiblePriceCardsValidated':True,'detailedRulesPresentInCurrentDom':all(checks[k] for k in checks if k.endswith('Dom'))},
      'payPerUseOwnCpo':{
        'priceGranularity':'network_class_and_local_time','currency':'EUR','vatIncluded':True,'localTimeZone':'Europe/Rome',
        'classes':{
          'QUICK_OR_FAST':{'mondayToSaturday':[{'start':'08:00','end':'12:00','energyEurPerKwh':0.74,'discounted':False},{'start':'12:00','end':'15:00','energyEurPerKwh':0.52,'discounted':True},{'start':'15:00','end':'22:00','energyEurPerKwh':0.74,'discounted':False},{'start':'22:00','end':'08:00','energyEurPerKwh':0.52,'discounted':True}],'sundayOrItalianPublicHoliday':0.52},
          'ULTRA_FAST':{'mondayToSaturday':[{'start':'08:00','end':'12:00','energyEurPerKwh':0.79,'discounted':False},{'start':'12:00','end':'15:00','energyEurPerKwh':0.74,'discounted':True},{'start':'15:00','end':'22:00','energyEurPerKwh':0.79,'discounted':False},{'start':'22:00','end':'08:00','energyEurPerKwh':0.74,'discounted':True}],'sundayOrItalianPublicHoliday':0.74}},
        'resolutionRules':{'discountedRateRequiresSessionStartAndEndInSameEligibleBandOrDay':True,'crossBandSession':'fail_closed_unrankable','italianPublicHolidayCalendarRequired':True,'stationClassMustBeResolvedFromValidatedSource':True},
        # Price amounts are live-validated; schedule use remains gated separately below.
        'rankableEnergyAmounts':True,
        'rankableSchedule':all(checks[k] for k in ('morningPeakDom','middayDiscountDom','eveningPeakDom','sameBandRuleDom')),
      },
      'roaming':{'priceModel':'station_specific_in_d_mobility','singleNationalPrice':None,'rankableWithoutStationFeed':False},
      'prepaid':[{'id':'duferco_prepaid_100','priceEur':65,'includedKwh':100,'validityMonths':3,'eligible':'Quick/Fast up to 50 kW'},{'id':'duferco_prepaid_150','priceEur':95,'includedKwh':150,'validityMonths':3,'eligible':'Quick/Fast up to 50 kW'},{'id':'duferco_prepaid_400','priceEur':249,'includedKwh':400,'validityMonths':3,'eligible':'Quick/Fast up to 50 kW'}],
      'prepaidModel':{'tccRankableWithoutRemainingBalance':False,'reason':'prepaid_credit_state_required'},
      'evidenceChecks':checks,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'checks':checks,'visibleChars':len(v),'domChars':len(t),'rankableSchedule':payload['payPerUseOwnCpo']['rankableSchedule']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
