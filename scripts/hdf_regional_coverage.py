#!/usr/bin/env python3
"""Consolidate validated Hauts-de-France public charging network evidence."""
from __future__ import annotations
import argparse, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
VALENCIENNES='https://www.valenciennes-metropole.fr/competences/amenagement-du-territoire/mode-doux-mobilite/'
SE60='https://www.se60.fr/infrastructures-et-reseaux-lies/mobilite-durable'
CAPSO='https://webdelib.ca-pso.fr/webdelibplus/jsp/seance_agenda.jsp?assembly=Conseil+communautaire&date=20250410&role=usager&type=apres'
FILES={
    'passpass':'passpass_hdf_official.json',
    'useda':'useda_dirve02_official_hdf.json',
    'te80':'te80_somme_official_hdf.json',
}

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read().decode('utf-8',errors='replace'),r.geturl()

def norm(s):
    import unicodedata
    s=unescape(s or '')
    s=re.sub(r'<[^>]+>',' ',s)
    s=unicodedata.normalize('NFKD',s)
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('HDF coverage evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/hdf'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    root=Path('data/operator_direct')
    docs={}
    for key,fn in FILES.items():
        p=root/fn
        if not p.exists(): raise RuntimeError(f'missing validated file {p}')
        docs[key]=json.loads(p.read_text())

    passpass=docs['passpass']; useda=docs['useda']; te80=docs['te80']
    if passpass.get('region')!='Hauts-de-France' or not passpass.get('tccDecision',{}).get('networkRulesClassable'):
        raise RuntimeError('validated Pass Pass evidence missing or not classable')
    if useda.get('department')!='Aisne' or not useda.get('tccDecision',{}).get('directTariffClassable'):
        raise RuntimeError('validated USEDA Aisne evidence missing')
    if te80.get('department')!='Somme' or not te80.get('tccDecision',{}).get('directTariffClassable'):
        raise RuntimeError('validated TE80 Somme evidence missing')

    vs,vhtml,vfinal=fetch(VALENCIENNES)
    ss,shtml,sfinal=fetch(SE60)
    cs,chtml,cfinal=fetch(CAPSO)
    if min(vs,ss,cs)!=200: raise RuntimeError(f'HTTP failure valenciennes={vs} se60={ss} capso={cs}')
    require(vhtml,'Electromobilité','40 bornes','80 points de charge','Pass Pass Electrique','22kW','50 kW')
    require(shtml,"1er janvier 2025",'Mouv\'Oise','Pass Pass','Région Hauts-de-France','SE60 conserve')
    require(chtml,'D105-25','nouvelle grille tarifaire','recharge électrique','pass pass')

    departments=[
      {
        'department':'Aisne','publicNetworkFamilies':['USEDA DIRVE 02'],
        'researchStatus':'accounted_for','pricingRuleStatus':'exact_direct_classable',
        'rule':'0.36 EUR/kWh direct from 2025-09-01; roaming/eMSP fees separate'
      },
      {
        'department':'Nord','publicNetworkFamilies':['Pass Pass Electrique'],
        'researchStatus':'accounted_for','pricingRuleStatus':'classable_by_station_category',
        'currentLocalEvidence':'Valenciennes Métropole currently documents 40 Pass Pass stations / 80 charge points including 22 kW AC and some 50 kW DC',
        'stationCategoryRequired':True,'stationDisplayedTariffHasPriority':True
      },
      {
        'department':'Oise','publicNetworkFamilies':['SE60 / former Mouv\'Oise -> Pass Pass Electrique'],
        'researchStatus':'accounted_for','pricingRuleStatus':'classable_by_station_category',
        'currentLocalEvidence':'SE60 documents Mouv\'Oise joining the regional Pass Pass network from 2025 while retaining infrastructure ownership',
        'stationCategoryRequired':True,'stationDisplayedTariffHasPriority':True
      },
      {
        'department':'Pas-de-Calais','publicNetworkFamilies':['Pass Pass Electrique'],
        'researchStatus':'accounted_for','pricingRuleStatus':'classable_by_station_category',
        'currentLocalEvidence':'CAPSO official 2025 council agenda records adoption of the new Pass Pass charging tariff grid',
        'stationCategoryRequired':True,'stationDisplayedTariffHasPriority':True
      },
      {
        'department':'Somme','publicNetworkFamilies':['Territoire d’Energie Somme (TE80) / Freshmile'],
        'researchStatus':'accounted_for','pricingRuleStatus':'exact_direct_classable_by_station_power_class',
        'stationPowerClassRequired':True,'roamingSeparate':True
      },
    ]

    payload={
      'schemaVersion':'1.0.0','dataset':'hauts-de-france-regional-coverage','generatedAt':now(),
      'country':'FR','region':'Hauts-de-France','departmentsTotal':5,'departmentCoverage':departments,
      'coverage':{
        'departmentsAccountedFor':5,
        'regionalPublicNetworkResearchCoverageComplete':True,
        'singleUniversalRegionalTariff':False,
        'directExactDepartmentFamilies':2,
        'passPassStationCategoryDepartments':3,
        'allDepartmentsHaveValidatedPricingRules':True,
        'allStationsRankableWithoutStationMetadata':False
      },
      'tccDecision':{
        'regionalCoverageValidated':True,
        'doNotInventDepartmentDefaults':True,
        'preserveStationCategoryAndPowerClass':True,
        'stationDisplayedTariffHasPriorityForPassPass':True,
        'roamingSeparate':True,
        'nextStep':'match real Hauts-de-France stations to Pass Pass category or local power class, then compare Electra/Electroverse offers separately'
      },
      'sourceEvidence':{
        'validatedOperatorFiles':list(FILES.values()),
        'nordValenciennesUrl':vfinal,'nordValenciennesHttpStatus':vs,
        'oiseSe60Url':sfinal,'oiseSe60HttpStatus':ss,
        'pasDeCalaisCapsoAgendaUrl':cfinal,'pasDeCalaisCapsoAgendaHttpStatus':cs
      },
      'notes':[
        'Pass Pass rules are exact at network-category level, but the station category and station-displayed tariff must be preserved before ranking.',
        'Aisne USEDA and Somme TE80 remain separate local public-network families; their direct tariffs must not be replaced by Pass Pass or roaming prices.',
        'This regional coverage concerns validated public-network families, not every private CPO operating commercially in Hauts-de-France.'
      ],
      'publicationStatus':'validated_candidate'
    }
    (out/'hauts_de_france_regional_coverage.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text(
      '# Hauts-de-France coverage\n\n'
      'All five departments are accounted for at public-network research level. Aisne uses USEDA DIRVE 02, Somme uses TE80/Freshmile, and current first-party local evidence confirms Pass Pass footprints in Nord, Oise and Pas-de-Calais. Pass Pass pricing is classable only after preserving each station category and the tariff displayed on the station; no universal regional tariff is invented.\n'
    )

if __name__=='__main__': main()
