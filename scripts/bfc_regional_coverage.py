#!/usr/bin/env python3
"""Consolidate already-validated Bourgogne-Franche-Comté operator evidence and current regional public surfaces."""
from __future__ import annotations
import argparse, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
BFC='https://www.territoiredenergie-bourgogne-franche-comte.com/nos-offres-et-tarifs/'
MODULO='https://modulo-energies.fr/'
FILES={
 'Yonne':'sdey_official_yonne.json',
 "Côte-d'Or":'siceco_cotedor_official.json',
 'Nièvre':'sieeen_nievre_official.json',
 'Doubs':'syded_doubs_official.json',
 'Haute-Saône':'sied70_official_haute_saone.json',
 'Territoire de Belfort':'tde90_belfort_official.json',
 'Saône-et-Loire':'qwello_saone_et_loire_official.json'
}
STATION_VERIFICATIONS={
 'Saône-et-Loire':'data/station_verifications/qwello_autun_12_petite_rue_marchaux.json'
}

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read().decode('utf-8',errors='replace')

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('BFC coverage evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/bfc'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    root=Path('data/operator_direct')
    rows={}
    for dept,fn in FILES.items():
        p=root/fn
        if not p.exists(): raise RuntimeError(f'missing validated file {p}')
        rows[dept]=json.loads(p.read_text())

    station_checks={}
    for dept,fn in STATION_VERIFICATIONS.items():
        p=Path(fn)
        if not p.exists(): raise RuntimeError(f'missing station verification {p}')
        station_checks[dept]=json.loads(p.read_text())
    qwello_check=station_checks['Saône-et-Loire']
    if qwello_check.get('operator')!='Qwello': raise RuntimeError('Qwello station verification operator mismatch')
    if qwello_check.get('tccDecision',{}).get('currentStationDirectTariffVerified') is not True: raise RuntimeError('Qwello station tariff is not marked verified')
    tariff=qwello_check.get('directTariff',{})
    if tariff.get('energyEurPerKwh')!=0.30 or tariff.get('timeEurPerMinute')!=0.02 or tariff.get('nightMinuteComponentCapEur')!=3.60:
        raise RuntimeError('Qwello Autun verified tariff changed unexpectedly')

    bs,bhtml=fetch(BFC); ms,mhtml=fetch(MODULO)
    if bs!=200 or ms!=200: raise RuntimeError(f'HTTP failure bfc={bs} modulo={ms}')
    require(bhtml,"Côte-d’Or",'SYDED','SIEEEN','SIED70','SDEY',"Territoire d'Energie 90",'Electromaps')
    require(mhtml,'804','Sans Abonnement','0,52','Abonnement','0,40')
    exact=[]; reference=[]
    exact_map={
      'Yonne':'SDEY','Côte-d\'Or':'SICECO','Nièvre':'SIEEEN','Doubs':'SYDED','Haute-Saône':'SIED70','Territoire de Belfort':"Territoire d'Énergie 90"
    }
    for dept,op in exact_map.items():
        exact.append({'department':dept,'operator':op,'tccDecision':'classable_by_validated_operator_rules'})
    reference.append({
      'department':'Saône-et-Loire',
      'operator':'Qwello',
      'tccDecision':'reference_only_with_station_level_verification',
      'currentVerifiedStationCount':1,
      'verifiedStation':{
        'name':qwello_check['station']['name'],
        'city':qwello_check['station']['city'],
        'powerKw':qwello_check['station']['powerKw'],
        'eurPerKwh':tariff['energyEurPerKwh'],
        'eurPerMinute':tariff['timeEurPerMinute'],
        'nightMinuteComponentCapEur':tariff['nightMinuteComponentCapEur']
      },
      'reason':'current direct tariff is verified for Qwello Autun 12 Petite Rue Marchaux, but network-wide uniformity across Saône-et-Loire is not yet established'
    })
    reference.append({'department':'Jura','operator':'Modulo candidate from SIDEC public history','tccDecision':'reference_only','reason':'Modulo current public prices are from-values and current first-party Jura station/operator mapping is not yet machine-confirmed'})
    payload={
      'schemaVersion':'1.0.0','dataset':'bfc-regional-coverage','generatedAt':now(),'region':'Bourgogne-Franche-Comté','country':'FR',
      'departmentsTotal':8,'exactRuleDepartments':exact,'referenceOnlyDepartments':reference,
      'coverage':{'departmentsAccountedFor':8,'exactRuleCount':6,'referenceOnlyCount':2,'currentStationLevelVerifications':1,'regionalResearchCoverageComplete':True,'allDepartmentsRankable':False},
      'sourceEvidence':{'bfcCurrentTariffPage':BFC,'bfcHttpStatus':bs,'moduloCurrentHome':MODULO,'moduloHttpStatus':ms,'validatedLocalFiles':list(FILES.values()),'stationVerificationFiles':list(STATION_VERIFICATIONS.values())},
      'notes':['Existing exact-rule files were generated from first-party sources on 2026-08-20 and are reused rather than rerun blindly one day later.','Qwello Autun 12 Petite Rue Marchaux is now current-station verified at 0.30 EUR/kWh + 0.02 EUR/min with a 3.60 EUR night cap on the minute component from 21:00 to 07:00.','Saône-et-Loire remains reference-only at department level until more Qwello stations confirm uniformity; Jura/Modulo remains reference-only until current local station/operator mapping and exact pricing are confirmed.'],
      'publicationStatus':'validated_candidate'
    }
    (out/'bfc_regional_coverage.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Bourgogne-Franche-Comté coverage\n\nAll eight departments are accounted for at research level. Six have current exact operator-rule grids. Saône-et-Loire now has one current Qwello station-level verification (Autun, 12 Petite Rue Marchaux) but remains reference-only at department level pending more samples. Jura/Modulo remains reference-only.\n')

if __name__=='__main__': main()
