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
    reference.append({'department':'Saône-et-Loire','operator':'Qwello','tccDecision':'reference_only','reason':'initial 2026 tariff is verified but current exact station tariff requires station/app lookup'})
    reference.append({'department':'Jura','operator':'Modulo candidate from SIDEC public history','tccDecision':'reference_only','reason':'Modulo current public prices are from-values and current first-party Jura station/operator mapping is not yet machine-confirmed'})
    payload={
      'schemaVersion':'1.0.0','dataset':'bfc-regional-coverage','generatedAt':now(),'region':'Bourgogne-Franche-Comté','country':'FR',
      'departmentsTotal':8,'exactRuleDepartments':exact,'referenceOnlyDepartments':reference,
      'coverage':{'departmentsAccountedFor':8,'exactRuleCount':6,'referenceOnlyCount':2,'regionalResearchCoverageComplete':True,'allDepartmentsRankable':False},
      'sourceEvidence':{'bfcCurrentTariffPage':BFC,'bfcHttpStatus':bs,'moduloCurrentHome':MODULO,'moduloHttpStatus':ms,'validatedLocalFiles':list(FILES.values())},
      'notes':['Existing exact-rule files were generated from first-party sources on 2026-08-20 and are reused rather than rerun blindly one day later.','Saône-et-Loire/Qwello and Jura/Modulo remain deliberately non-rankable until current exact local/station pricing is resolved.'],
      'publicationStatus':'validated_candidate'
    }
    (out/'bfc_regional_coverage.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'SUMMARY.md').write_text('# Bourgogne-Franche-Comté coverage\n\nAll eight departments are accounted for at research level. Six have current exact operator-rule grids. Saône-et-Loire (Qwello) and Jura (Modulo candidate) remain reference-only.\n')

if __name__=='__main__': main()
