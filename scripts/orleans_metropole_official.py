#!/usr/bin/env python3
"""Validate current Orléans Métropole public EV charging tariff from first-party sources."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
CURRENT='https://www.orleans-metropole.fr/actions-et-services/mobilite-et-deplacements/stationnement'
DECISION='https://www.orleans-metropole.fr/fileadmin/orleans-metropole/MEDIA/document/metropole/conseil_communaute/proces_verbaux/2023/proces_verbal_2023_11_16.pdf'
NEWS='https://www.orleans-metropole.fr/actualites/detail/le-conseil-metro-dans-le-retro-novembre-2023'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('Orleans Metropole evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/orleans'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    cs,craw,cfinal=fetch(CURRENT); ds,draw,dfinal=fetch(DECISION); ns,nraw,nfinal=fetch(NEWS)
    if min(cs,ds,ns)!=200: raise RuntimeError(f'HTTP failure current={cs} decision={ds} news={ns}')
    ch=craw.decode('utf-8',errors='replace'); nh=nraw.decode('utf-8',errors='replace')
    require(ch,'Bornes électriques','30','0,50','kWh','25','Freshmile','4,99')
    require(nh,'0,50','kWh','25','stationnement longue durée')
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError('pypdf required to validate Orléans Métropole council decision') from e
    text='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(draw)).pages)
    require(text,'Bornes de charge pour véhicules électriques','120 minutes','17 € TTC','0,50 € TTC/ kWh','25 € TTC','1er janvier 2024')
    payload={
      'schemaVersion':'1.0.0','dataset':'orleans-metropole-official-centre','generatedAt':now(),
      'operator':'Orléans Métropole','serviceOperator':'Freshmile','country':'FR','region':'Centre-Val de Loire','department':'Loiret',
      'effectiveFrom':'2024-01-01',
      'classification':{'localPublicNetwork':True,'directPublicTariff':True,'energyTariffExact':True,'longStayFlatFee':True,'currentPageRestatesThreshold':False,'singleFlatTariff':False},
      'directTariff':{'energyEurPerKwhTtc':0.50,'longStayFeeEurTtc':25.0,'priorThresholdMinutes':120,'thresholdContinuitySupportedByCouncilDecision':True},
      'access':{'freshmileApp':True,'freshmileBadge':True,'badgePurchaseEur':4.99},
      'network':{'stations':30,'municipalities':22,'evsePrefix':'FR*M45'},
      'tccDecision':{'operatorValidated':True,'energyPriceCanBeDisplayed':True,'fullSessionRankable':False,'reason':'The current first-party page confirms 0.50 EUR/kWh and a 25 EUR long-stay fee, but does not restate the trigger threshold explicitly; keep the complete session out of ranking until that trigger is independently current-confirmed.'},
      'sourceEvidence':{'officialOnly':True,'currentUrl':CURRENT,'currentHttpStatus':cs,'currentSha256':hashlib.sha256(craw).hexdigest(),'decisionUrl':DECISION,'decisionHttpStatus':ds,'decisionSha256':hashlib.sha256(draw).hexdigest(),'newsUrl':NEWS,'newsHttpStatus':ns,'newsSha256':hashlib.sha256(nraw).hexdigest()},
      'publicationStatus':'validated_candidate'
    }
    sig={k:payload[k] for k in ('classification','directTariff','access','tccDecision')}
    payload['sourceEvidence']['relevantTariffFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'orleans_metropole_official_centre.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Orléans Métropole\n\nCurrent first-party tariff: 0.50 EUR/kWh and a 25 EUR long-stay flat fee. The current page does not restate the long-stay trigger threshold, so TCC should show the energy price but keep the full-session offer out of ranking until the trigger is current-confirmed.\n')

if __name__=='__main__': main()
