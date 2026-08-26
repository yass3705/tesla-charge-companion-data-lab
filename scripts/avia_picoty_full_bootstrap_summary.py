#!/usr/bin/env python3
import json,re
from pathlib import Path
from datetime import datetime,timezone

SRC=Path('data/reports/avia_picoty_full_guest_bootstrap.json')
OUT=Path('data/reports/avia_picoty_full_guest_bootstrap_summary.json')
SAFE_TERMS=('registration','register','tenant','distribution','location','tariff','cpo','deftpower','runtime','expo-channel')
SECRETISH=re.compile(r'(?i)(authorization|subscription[-_]?key|api[-_]?key|access[-_]?token|refresh[-_]?token|client[-_]?secret)')
JWT=re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?')
GOOGLE=re.compile(r'AIza[0-9A-Za-z_-]{20,}')

def safe_literal(v):
    if not isinstance(v,str) or len(v)>300:return False
    low=v.lower()
    return (v.startswith('/') or v.startswith('https://u.expo.dev/') or any(t in low for t in SAFE_TERMS)) and not SECRETISH.search(v) and not JWT.search(v) and not GOOGLE.search(v)

def main():
    d=json.loads(SRC.read_text(encoding='utf-8'))
    ops=[]
    for summary in d.get('operationSummary',[]):
        ops.append({
            'operation':summary.get('operation'),
            'methodCandidates':summary.get('methodCandidates') or [],
            'pathFragments':[x for x in (summary.get('pathFragments') or []) if safe_literal(x)][:80],
            'hitCount':len((d.get('operations') or {}).get(summary.get('operation'),[]) or []),
        })
    cfg={}
    for term,hits in (d.get('configHits') or {}).items():
        vals=[]
        for h in hits or []:
            for v in h.get('publicLiterals') or []:
                if safe_literal(v) and v not in vals:vals.append(v)
        cfg[term]={'hitCount':len(hits or []),'publicLiterals':vals[:80]}
    resources=[]
    for item in d.get('resourceMetadata') or []:
        ctx=item.get('context','')
        if SECRETISH.search(ctx) or JWT.search(ctx) or GOOGLE.search(ctx):
            ctx='<redacted-context>'
        else:
            ctx=ctx[:1200]
        resources.append({'file':item.get('file'),'line':item.get('line'),'context':ctx,'uuidCandidates':item.get('uuidCandidates') or []})
    out={
        'schemaVersion':'1.0.0',
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'sourceGeneratedAt':d.get('generatedAt'),
        'sourceSchemaVersion':d.get('schemaVersion'),
        'bundleChars':d.get('bundleChars'),
        'operationSummary':ops,
        'configSummary':cfg,
        'resourceMetadata':resources[:120],
        'uuidCandidates':d.get('uuidCandidates') or [],
        'safety':{'sourceCredentialsPersisted':(d.get('safety') or {}).get('credentialsPersisted'),'sourceTokensPersisted':(d.get('safety') or {}).get('tokensPersisted')}
    }
    raw=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
    if SECRETISH.search(raw) or JWT.search(raw) or GOOGLE.search(raw):
        raise RuntimeError('unsafe material in compact summary')
    OUT.write_text(raw,encoding='utf-8')
    print(json.dumps({'operations':ops,'configSummary':cfg,'uuidCandidates':out['uuidCandidates'],'resourceMetadataCount':len(resources)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
