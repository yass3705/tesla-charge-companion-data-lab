import csv,json,urllib.request,os,math
RES='reports/electroverse/b-residual-analysis.json'
MAP='data/electroverse/irve_location_mapping.json'
OUT='reports/electroverse/b-qualicharge-technical-group-audit.json'
URL='https://proxy.transport.data.gouv.fr/resource/qualicharge-irve-statique'
res=json.load(open(RES,encoding='utf-8'))
mapping=json.load(open(MAP,encoding='utf-8'))
byloc={str(m.get('electroverseLocationPk')):m for m in mapping.get('mappings',[])}
locations=[]
for g in res.get('unresolvedSamples',[]):
    loc=str(g.get('electroverseLocationPk'))
    m=byloc.get(loc,{})
    locations.append((loc,g,m))
targets=set()
for loc,g,m in locations:
    for p in m.get('irvePdcIds',[]): targets.add(str(p).upper().replace('*',''))
path='/tmp/qualicharge.csv'
urllib.request.urlretrieve(URL,path)
official={}
with open(path,'r',encoding='utf-8-sig',newline='') as fh:
    rd=csv.DictReader(fh)
    for row in rd:
        p=str(row.get('id_pdc_itinerance') or '').upper().replace('*','')
        if p in targets: official[p]=row
def src_sig(conn):
    kw=conn.get('kilowatts')
    try: kw=float(kw)
    except: kw=None
    if kw is not None:
        if abs(kw-22)<=1: kw=22
        elif abs(kw-50)<=2: kw=50
        elif abs(kw-11)<=1: kw=11
        elif abs(kw-7)<=1: kw=7
        elif abs(kw-180)<=5: kw=180
        else: kw=round(kw,2)
    std=str(conn.get('standard') or '')
    return (kw,std)
def tgt_sig(row):
    try: kw=float(row.get('puissance_nominale') or '')
    except: kw=None
    if kw is not None:
        if abs(kw-22)<=1: kw=22
        elif abs(kw-50)<=2: kw=50
        elif abs(kw-11)<=1: kw=11
        elif abs(kw-7)<=1: kw=7
        elif abs(kw-180)<=5: kw=180
        else: kw=round(kw,2)
    if str(row.get('prise_type_combo_ccs')).lower()=='true': std='IEC_62196_T2_COMBO'
    elif str(row.get('prise_type_2')).lower()=='true': std='IEC_62196_T2'
    else: std='OTHER'
    return (kw,std)
audit=[]
candidates=[]
for loc,g,m in locations:
    sgroups={}
    for r in g.get('refs',[]):
        conns=r.get('connectors') or []
        if len(conns)!=1: continue
        sig=src_sig(conns[0])
        sgroups.setdefault(sig,[]).append({'evsePk':r.get('evsePk'),'physicalReference':r.get('physicalReference')})
    tgroups={}
    missing=[]
    for p0 in m.get('irvePdcIds',[]):
        p=str(p0).upper().replace('*','')
        row=official.get(p)
        if not row: missing.append(p); continue
        sig=tgt_sig(row)
        tgroups.setdefault(sig,[]).append(p)
    locc=[]
    for sig,srcs in sgroups.items():
        tgts=tgroups.get(sig,[])
        if srcs and len(srcs)==len(tgts) and len(srcs)>=1:
            cand={
              'mode':'homogeneous_target_subset','operator':'B','electroverseLocationPk':loc,
              'irveStationId':m.get('irveStationId') or g.get('irveStationId'),
              'sourceEvsePks':[x['evsePk'] for x in srcs],
              'physicalReferences':[x['physicalReference'] for x in srcs],
              'targetPdcs':tgts,'uniformConnectorCount':True,
              'profile':{'kilowatts':sig[0],'standard':sig[1]},
              'evidence':{'source':'QualiCharge static open data','observed':'2026-10-02','note':'Exact technical-group cardinality between residual Electroverse source EVSEs and current official QualiCharge PDC rows; builder must revalidate pricing homogeneity and target uniqueness.'}
            }
            locc.append(cand); candidates.append(cand)
    audit.append({'locationPk':loc,'station':m.get('irveStationId') or g.get('irveStationId'),'residualCount':g.get('residualCount'),'mappingPdcCount':len(m.get('irvePdcIds',[])),'officialPdcFound':len(m.get('irvePdcIds',[]))-len(missing),'missingOfficialPdcs':missing,'sourceGroups':{str(k):v for k,v in sgroups.items()},'targetGroups':{str(k):v for k,v in tgroups.items()},'candidateGroups':locc})
out={'generatedAt':'2026-10-02','qualichargeUrl':URL,'residualSourceEvses':res.get('residualSourceEvses'),'affectedLocations':res.get('affectedLocations'),'candidateGroupCount':len(candidates),'candidateSourceEvses':sum(len(x['sourceEvsePks']) for x in candidates),'candidateLocations':len(set(x['electroverseLocationPk'] for x in candidates)),'candidates':candidates,'audit':audit}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({k:out[k] for k in ['candidateGroupCount','candidateSourceEvses','candidateLocations']},indent=2))
