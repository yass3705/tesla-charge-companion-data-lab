import json, os
RES='reports/electroverse/b-residual-analysis.json'
E55='reports/electroverse/b-final-fr55c-electric55-base-audit.json'
OUT='reports/electroverse/b-fr55c-current-tech-duplicate-groups.json'
res=json.load(open(RES,encoding='utf-8'))
e55=json.load(open(E55,encoding='utf-8'))
e55by={str(r.get('stationId')):r for r in e55.get('rows',[])}
def price_sig(r):
    return json.dumps([{
      'isChargingFree':c.get('isChargingFree'),
      'priceComponents':c.get('priceComponents'),
      'complexPricingDetail':c.get('complexPricingDetail')
    } for c in (r.get('connectors') or [])],sort_keys=True,ensure_ascii=False)
ready=[];audit=[]
for g in res.get('unresolvedSamples',[]):
    sid=str(g.get('irveStationId') or '')
    ev=e55by.get(sid)
    if not ev or not ev.get('found'): continue
    cps=ev.get('station',{}).get('chargePoints',[])
    # current direct-inventory groups by normalized power+kind
    tg={}
    for cp in cps:
        kw=cp.get('powerKw')
        if kw is None: continue
        nkw=22 if abs(float(kw)-22)<=1.5 else 7 if abs(float(kw)-7)<=1.5 else round(float(kw),2)
        kind='IEC_62196_T2' if cp.get('kind')=='AC' and 'TYPE_2' in (cp.get('connectors') or []) else 'OTHER'
        tg.setdefault((nkw,kind),[]).append(cp.get('evseId'))
    sg={}
    for r in g.get('refs',[]):
        cs=r.get('connectors') or []
        if len(cs)!=1: continue
        c=cs[0]
        kw=float(c.get('kilowatts'))
        nkw=22 if abs(kw-22)<=1.5 else 7 if abs(kw-7)<=1.5 else round(kw,2)
        std=c.get('standard')
        if isinstance(std,dict): std=std.get('name')
        sg.setdefault((nkw,std),[]).append(r)
    locready=[]
    for sig,srcs in sg.items():
        tgts=tg.get(sig,[])
        if not tgts: continue
        # allow multiple Electroverse duplicate sources for same current technical target set,
        # only if all source tariffs are identical and every current target is globally part of this station.
        if len({price_sig(r) for r in srcs})!=1: continue
        if len(srcs)<len(tgts): continue
        cand={
          'mode':'homogeneous_target_subset',
          'operator':'B',
          'electroverseLocationPk':str(g.get('electroverseLocationPk')),
          'irveStationId':sid,
          'sourceEvsePks':[r.get('evsePk') for r in srcs],
          'physicalReferences':[r.get('physicalReference') for r in srcs],
          'targetPdcs':tgts,
          'uniformConnectorCount':True,
          'profile':{'kilowatts':sig[0],'standard':sig[1]},
          'evidence':{
            'source':'Electric55 direct station base + Electroverse live residuals',
            'observed':'2026-10-02',
            'note':'All residual source EVSEs in this technical class have identical compiled pricing and the current Electric55 direct inventory exposes exactly this target technical class. Multiple historical/live Electroverse aliases may share the current target set; no source-to-branch identity is asserted.'
          }
        }
        locready.append(cand); ready.append(cand)
    audit.append({'station':sid,'locationPk':g.get('electroverseLocationPk'),'residualCount':g.get('residualCount'),'ready':locready})
out={'generatedAt':'2026-10-02','readyGroupCount':len(ready),'readySourceEvses':sum(len(x['sourceEvsePks']) for x in ready),'readyLocations':len(set(x['electroverseLocationPk'] for x in ready)),'ready':ready,'audit':audit}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({k:out[k] for k in ['readyGroupCount','readySourceEvses','readyLocations']},indent=2))
