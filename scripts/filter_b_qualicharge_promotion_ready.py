import json,os
AUD='reports/electroverse/b-qualicharge-technical-group-audit.json'
RES='reports/electroverse/b-residual-analysis.json'
OUT='reports/electroverse/b-qualicharge-promotion-ready.json'
aud=json.load(open(AUD,encoding='utf-8'))
res=json.load(open(RES,encoding='utf-8'))
refs={}
for g in res.get('unresolvedSamples',[]):
    for r in g.get('refs',[]):
        refs[str(r.get('evsePk'))]=r
def pricing_sig(r):
    cs=r.get('connectors') or []
    rows=[]
    for c in cs:
        rows.append({
          'isChargingFree':c.get('isChargingFree'),
          'priceComponents':c.get('priceComponents'),
          'complexPricingDetail':c.get('complexPricingDetail')
        })
    return json.dumps(rows,sort_keys=True,ensure_ascii=False)
ready=[]; rejected=[]
for g in aud.get('candidates',[]):
    pks=[str(x) for x in g.get('sourceEvsePks',[])]
    if not pks or any(pk not in refs for pk in pks):
        rejected.append({'reason':'not_all_sources_currently_residual','group':g}); continue
    rr=[refs[pk] for pk in pks]
    counts={len(r.get('connectors') or []) for r in rr}
    sigs={pricing_sig(r) for r in rr}
    if len(counts)!=1:
        rejected.append({'reason':'heterogeneous_connector_count','group':g}); continue
    if len(sigs)!=1:
        rejected.append({'reason':'heterogeneous_pricing','group':g}); continue
    ready.append(g)
out={
 'generatedAt':'2026-10-02',
 'sourceResidualGeneratedAt':res.get('generatedAt'),
 'currentResidualSourceEvses':res.get('residualSourceEvses'),
 'currentAffectedLocations':res.get('affectedLocations'),
 'readyGroupCount':len(ready),
 'readySourceEvses':sum(len(g.get('sourceEvsePks',[])) for g in ready),
 'readyLocations':len(set(g.get('electroverseLocationPk') for g in ready)),
 'ready':ready,
 'rejectedCount':len(rejected),
 'rejected':rejected
}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({k:out[k] for k in ['readyGroupCount','readySourceEvses','readyLocations','rejectedCount']},indent=2))
