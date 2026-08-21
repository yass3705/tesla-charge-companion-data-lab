#!/usr/bin/env python3
"""Validate current Ardenne Métropole public EV charging tariffs from the first-party page."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
URL='https://ardenne-metropole.fr/bornes-de-recharge/'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('Ardenne Metropole evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/ardenne_metropole'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    st,raw,final=fetch(URL)
    if st!=200: raise RuntimeError(f'HTTP failure {st}')
    text=raw.decode('utf-8',errors='replace')
    require(text,'149 bornes','été 2025','Freshmile','Borne 7 kVA','1,10','heure','Borne 22 kVA','2,20','application ou le badge Freshmile','autres opérateurs','frais supplémentaires')
    payload={
      'schemaVersion':'1.0.0','dataset':'ardenne-metropole-official-grandest','generatedAt':now(),
      'operator':'Ardenne Métropole','serviceOperator':'Freshmile','country':'FR','region':'Grand Est','department':'Ardennes',
      'classification':{'localPublicNetwork':True,'directPublishedTariff':True,'timeBased':True,'powerDependent':True,'freshmileManagedSince2025':True,'roamingMayDiffer':True},
      'operatorDirect':{
        '7kva':{'powerKva':7.0,'eurPerHour':1.10},
        '22kva':{'powerKva':22.0,'eurPerHour':2.20}
      },
      'access':{'freshmileAppRecommended':True,'freshmileBadgeRecommended':True,'otherOperatorsSupported':True,'otherOperatorsMayAddFees':True},
      'network':{'stations':149,'managementTransfer':'summer 2025'},
      'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'roamingSeparate':True,'note':'Use the local Ardenne Métropole/Freshmile tariff as the operator-direct/local offer; other eMSP prices remain separate.'},
      'sourceEvidence':{'officialOnly':True,'url':URL,'httpStatus':st,'rawSha256':hashlib.sha256(raw).hexdigest()},
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','operatorDirect','access','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'ardenne_metropole_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Ardenne Métropole\n\nValidated first-party tariff managed by Freshmile since summer 2025: 1.10 EUR/hour at 7 kVA and 2.20 EUR/hour at 22 kVA. Other eMSP/operator retail prices may add fees and remain separate.\n')

if __name__=='__main__': main()
