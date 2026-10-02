import csv,json,urllib.request,os
RES='reports/electroverse/b-residual-analysis.json'
MAP='data/electroverse/irve_location_mapping.json'
OUT='reports/electroverse/b-pan-national-promotion-ready.json'
URL='https://www.data.gouv.fr/api/1/datasets/r/4ca78c71-4ea4-475d-bd3a-d4aef88f7bf8'
res=json.load(open(RES,encoding='utf-8'))
mapping=json.load(open(MAP,encoding='utf-8'))
byloc={str(m.get('electroverseLocationPk')):m for m in mapping.get('mappings',[])}
locations=[]
target_ids=set()
for g in res.get('unresolvedSamples',[]):
    loc=str(g.get('electroverseLocationPk')); m=byloc.get(loc,{})
    locations.append((loc,g,m))
    for p in m.get('irvePdcIds',[]): target_ids.add(str(p).upper().replace('*',''))
path='/tmp/pan_irve.csv'
urllib.request.urlretrieve(URL,path)
official={}
with open(path,'r',encoding='utf-8-sig',newline='') as fh:
    sample=fh.read(4096); fh.seek(0)
    try: dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
    except: dialect=csv.excel
    rd=csv.DictReader(fh,dialect=dialect)
    for row in rd:
        p=str(row.get('id_pdc_itinerance') or '').upper().replace('*','')
        if p in target_ids: official[p]=row
def kw_norm(v):
    try: n=float(v)
    except: return None
    for b,tol in [(4,1),(7,1),(11,1),(18,1.5),(22,1.5),(43,2),(47,2),(50,2),(100,3),(150,4),(180,5),(200,5)]:
        if abs(n-b)<=tol:return b
    return round(n,2)
def src_sig(conn):
    return (kw_norm(conn.get('kilowatts')),str(conn.get('standard') or ''))
def tgt_sig(row):
    kw=kw_norm(row.get('puissance_nominale'))
    if str(row.get('prise_type_combo_ccs')).lower()=='true': std='IEC_62196_T2_COMBO'
    elif str(row.get('prise_type_2')).lower()=='true': std='IEC_62196_T2'
    elif str(row.get('prise_type_ef')).lower()=='true': std='DOMESTIC_F'
    else: std='OTHER'
    return (kw,std)
def pricing_sig(ref):
    rows=[]
    for c in ref.get('connectors') or []:
        rows.append({
          'isChargingFree':c.get('isChargingFree'),
          'priceComponents':c.get('priceComponents'),
          'complexPricingDetail':c.get('complexPricingDetail')
        })
    return json.dumps(rows,sort_keys=True,ensure_ascii=False)
ready=[]; audit=[]
for loc,g,m in locations:
    sgroups={}
    for r in g.get('refs',[]):
        cs=r.get('connectors') or []
        if len(cs)!=1: continue
        sig=src_sig(cs[0]); sgroups.setdefault(sig,[]).append(r)
    tgroups={}; missing=[]
    for p0 in m.get('irvePdcIds',[]):
        p=str(p0).upper().replace('*',''); row=official.get(p)
        if not row: missing.append(p); continue
        tgroups.setdefault(tgt_sig(row),[]).append(p)
    loc_ready=[]
    for sig,srcs in sgroups.items():
        tgts=tgroups.get(sig,[])
        if not srcs or len(srcs)!=len(tgts): continue
        if len({len(r.get('connectors') or []) for r in srcs})!=1: continue
        if len({pricing_sig(r) for r in srcs})!=1: continue
        cand={
          'mode':'homogeneous_target_subset','operator':'B','electroverseLocationPk':loc,
          'irveStationId':m.get('irveStationId') or g.get('irveStationId'),
          'sourceEvsePks':[r.get('evsePk') for r in srcs],
          'physicalReferences':[r.get('physicalReference') for r in srcs],
          'targetPdcs':tgts,'uniformConnectorCount':True,
          'profile':{'kilowatts':sig[0],'standard':sig[1]},
          'evidence':{
            'source':'PAN national consolidated IRVE static open data',
            'observed':'2026-10-02',
            'note':'Exact current official PDC technical profile group and exact source/target cardinality; Electroverse source group also has identical connector count and pricing. Builder must revalidate local/global target uniqueness.'
          }
        }
        loc_ready.append(cand); ready.append(cand)
    audit.append({
      'locationPk':loc,'station':m.get('irveStationId') or g.get('irveStationId'),
      'residualCount':g.get('residualCount'),'mappingPdcCount':len(m.get('irvePdcIds',[])),
      'officialPdcFound':len(m.get('irvePdcIds',[]))-len(missing),'missingOfficialPdcs':missing,
      'sourceGroups':{str(k):len(v) for k,v in sgroups.items()},
      'targetGroups':{str(k):len(v) for k,v in tgroups.items()},
      'readyGroups':loc_ready
    })
out={
 'generatedAt':'2026-10-02','sourceResidualGeneratedAt':res.get('generatedAt'),
 'currentResidualSourceEvses':res.get('residualSourceEvses'),'currentAffectedLocations':res.get('affectedLocations'),
 'resourceUrl':URL,'officialMatchedPdcCount':len(official),
 'readyGroupCount':len(ready),'readySourceEvses':sum(len(g['sourceEvsePks']) for g in ready),
 'readyLocations':len(set(g['electroverseLocationPk'] for g in ready)),
 'ready':ready,'audit':audit
}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({k:out[k] for k in ['currentResidualSourceEvses','officialMatchedPdcCount','readyGroupCount','readySourceEvses','readyLocations']},indent=2))
