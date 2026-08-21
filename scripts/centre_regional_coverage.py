#!/usr/bin/env python3
"""Consolidate validated Centre-Val de Loire public-network evidence without inventing universal tariffs."""
from __future__ import annotations
import argparse, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
LOIRET='https://www.loiret.fr/les-projets/schema-directeur-dinfrastructures-de-recharge-des-vehicules-electriques-sdirve'
SIDELC41='https://data.blois.agglopolys.fr/explore/dataset/bornes-de-recharge-pour-vehicule-electrique-du-sidelc-en-loir-et-cher-modulo/table/'
FILES={
    'modulo':'modulo_official_centre.json',
    'chargelec36':'chargelec36_official_centre.json',
    'orleans':'orleans_metropole_official_centre.json',
    'sieely':'sieely_official_idf_centre.json',
}

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return int(getattr(r,'status',200)),r.read().decode('utf-8',errors='replace'),r.geturl()

def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '')
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError('Centre coverage evidence missing: '+', '.join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/centre'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    root=Path('data/operator_direct')
    docs={}
    for key,fn in FILES.items():
        p=root/fn
        if not p.exists(): raise RuntimeError(f'missing validated file {p}')
        docs[key]=json.loads(p.read_text())

    modulo=docs['modulo']; chargelec=docs['chargelec36']; orleans=docs['orleans']; sieely=docs['sieely']
    for k in ('cher','eureEtLoir','indreEtLoire','loirEtCher'):
        if not modulo.get('centreValDeLoireEvidence',{}).get(k,{}).get('operatorConfirmed'):
            raise RuntimeError(f'Modulo Centre mapping missing: {k}')
    if chargelec.get('department')!='Indre' or not chargelec.get('tccDecision',{}).get('operatorValidated'):
        raise RuntimeError('Chargelec36 Indre evidence missing')
    if orleans.get('department')!='Loiret' or not orleans.get('tccDecision',{}).get('operatorValidated'):
        raise RuntimeError('Orleans Metropole evidence missing')
    if 'Eure-et-Loir' not in sieely.get('departments',[]):
        raise RuntimeError('SIE-ELY Eure-et-Loir evidence missing')

    ls,lhtml,lfinal=fetch(LOIRET); ss,shtml,sfinal=fetch(SIDELC41)
    if ls!=200 or ss!=200: raise RuntimeError(f'HTTP failure loiret={ls} sidelc41={ss}')
    require(lhtml,'Schéma Directeur','hors territoire d’Orléans Métropole','290 points de charge','3 400 points de charge','opérateurs privés')
    require(shtml,'Bornes de recharge','SIDELC','Loir et Cher','Modulo')

    departments=[
      {'department':'Cher','publicNetworkFamilies':['SDE18 / Modulo'],'researchStatus':'accounted_for','rankingStatus':'reference_only','reason':'Modulo publishes current from-prices; exact local/station tariff remains required.'},
      {'department':'Eure-et-Loir','publicNetworkFamilies':['Territoire d’Énergie Eure-et-Loir / Modulo','SIE-ELY'],'researchStatus':'accounted_for','rankingStatus':'mixed','exactLocalOffer':'SIE-ELY direct rules are exact on its own footprint','departmentWideDefault':False},
      {'department':'Indre','publicNetworkFamilies':['Chargelec36 / SDEI36'],'researchStatus':'accounted_for','rankingStatus':'reference_only','reason':'Current local 10 EUR amount is corroborated but its billing semantics are not first-party machine-readable.'},
      {'department':'Indre-et-Loire','publicNetworkFamilies':['SIEIL37 / Modulo'],'researchStatus':'accounted_for','rankingStatus':'reference_only','reason':'Modulo publishes from-prices and local/station confirmation is required.'},
      {'department':'Loir-et-Cher','publicNetworkFamilies':['SIDELC / Modulo'],'researchStatus':'accounted_for','rankingStatus':'reference_only','reason':'Current public open-data catalogue confirms SIDELC/Modulo coverage; exact local/station tariff remains required.'},
      {'department':'Loiret','publicNetworkFamilies':['Orléans Métropole / Freshmile','Loiret hors Orléans Métropole - multi-authority SDIRVE / private-operator rollout'],'researchStatus':'accounted_for','rankingStatus':'mixed_reference_only_for_complete_session','reason':'Orléans has an exact 0.50 EUR/kWh energy price but the current page does not restate the long-stay trigger; outside the Métropole there is no single current CPO/tariff to invent.'},
    ]
    payload={
      'schemaVersion':'1.0.0','dataset':'centre-val-de-loire-regional-coverage','generatedAt':now(),'country':'FR','region':'Centre-Val de Loire','departmentsTotal':6,
      'departmentCoverage':departments,
      'coverage':{
        'departmentsAccountedFor':6,
        'regionalResearchCoverageComplete':True,
        'singleUniversalRegionalTariff':False,
        'fullyRankableDepartmentCount':0,
        'exactLocalOfferFamilies':1,
        'partialExactLocalOfferFamilies':1,
        'referenceOnlyOrMixedDepartments':6
      },
      'tccDecision':{
        'regionalCoverageValidated':True,
        'doNotInventDepartmentDefaults':True,
        'preserveStationOrNetworkScope':True,
        'roamingSeparate':True,
        'nextStep':'station-level matching can now proceed without blocking regional public-network discovery'
      },
      'sourceEvidence':{
        'validatedLocalFiles':list(FILES.values()),
        'loiretOfficialSdirveUrl':lfinal,'loiretOfficialSdirveHttpStatus':ls,
        'sidelc41AgglopolysOpenDataUrl':sfinal,'sidelc41AgglopolysOpenDataHttpStatus':ss
      },
      'publicationStatus':'validated_candidate'
    }
    (out/'centre_val_de_loire_regional_coverage.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text(
      '# Centre-Val de Loire coverage\n\n'
      'All six departments are accounted for at public-network research level. Modulo is confirmed in Cher, Eure-et-Loir, Indre-et-Loire and Loir-et-Cher; Chargelec36 covers the Indre; Loiret is split between the Orléans Métropole/Freshmile network and a multi-authority SDIRVE/private-operator rollout outside the Métropole. SIE-ELY is preserved as a separate exact local cross-region offer. No universal department or regional tariff is invented.\n'
    )

if __name__=='__main__': main()
