#!/usr/bin/env python3
"""Validate current official Atlante Italy commercial rules from public pages."""
from __future__ import annotations
import html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL="https://atlante.energy/it/myatlante-app/"
OUT=Path("data/reference/atlante_italy_offers.json")
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def fetch():
    q=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"it-IT,it;q=0.9"})
    with urllib.request.urlopen(q,timeout=45) as r: return r.read().decode(r.headers.get_content_charset() or 'utf-8','replace')
def text(raw):
    s=re.sub(r'<script\b[^>]*>.*?</script>',' ',raw,flags=re.I|re.S); s=re.sub(r'<style\b[^>]*>.*?</style>',' ',s,flags=re.I|re.S); s=re.sub(r'<[^>]+>',' ',s); return re.sub(r'\s+',' ',html.unescape(s)).strip()
def norm(s): return re.sub(r'\s+',' ',s.lower().replace('–','-').replace('—','-')).strip()

def main():
    t=norm(text(fetch()))
    # Fail closed on the current FAQ pairing, not isolated stale price fragments elsewhere on the page.
    italy_pair=bool(re.search(r'italia\s*-\s*stazioni atlante\s*:\s*0[,.]49\s*€/kwh\s*-\s*stazioni chargeleague\s*:\s*0[,.]59\s*€/kwh',t,re.I))
    fee=bool(re.search(r'9[,.]99\s*€/mese',t,re.I))
    countries=all(x in t for x in ('francia','italia','spagna'))
    partners=all(x in t for x in ('electra','fastned','ionity'))
    if not (italy_pair and fee and countries and partners):
        raise RuntimeError(f"Current Atlante Go Italy evidence incomplete pair={italy_pair} fee={fee} countries={countries} partners={partners}")
    promo=bool(re.search(r'31\s+agosto.*1.?\s*mese\s+gratuito',t,re.I))
    payload={
      "schemaVersion":1,"generatedAt":now(),"country":"IT","operator":"Atlante","service":"myAtlante",
      "directPayAsYouGo":{"priceModel":"station_specific","rankable":False,"reason":"Exact no-subscription direct price is selected-charger specific in myAtlante; no authorized station tariff feed is currently available in this research branch."},
      "subscriptions":[{"id":"atlante_go","name":"Atlante Go","monthlyFeeEur":9.99,"autoRenewMonthly":True,"noCommitment":True,"rankableWhenSelected":True,
        "countryTariffs":{"IT":{"ATLANTE":0.49,"CHARGELEAGUE":0.59},"FR":{"ATLANTE":0.29,"CHARGELEAGUE":0.49},"ES":{"ATLANTE":0.29,"CHARGELEAGUE":0.49}},
        "chargeLeagueOperators":["Electra","Fastned","IONITY"],
        "promotion":{"firstMonthFreeObserved":promo,"deadlineLocal":"2026-08-31T23:59:00+02:00" if promo else None,"mustNotReplaceRecurringFee":True}}],
      "source":{"url":URL,"official":True,"currentItalyPairValidated":italy_pair}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({"italyAtlanteGoEurPerKwh":0.49,"italyChargeLeagueEurPerKwh":0.59,"monthlyFeeEur":9.99,"promotionObserved":promo},indent=2))
if __name__=='__main__': main()
