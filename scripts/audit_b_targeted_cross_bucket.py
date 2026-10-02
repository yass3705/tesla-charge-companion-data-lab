import csv,json,urllib.request,os,gzip
CACHE='data/electroverse/tariff_cache'
MAP='data/electroverse/irve_location_mapping.json'
OVER='data/platforms/electroverse/france-evse'
OUT='reports/electroverse/b-targeted-cross-bucket-completion.json'
LOCS={'346704','1405472','4220939','1291235'}
PAN='https://www.data.gouv.fr/api/1/datasets/r/4ca78c71-4ea4-475d-bd3a-d4aef88f7bf8'
mapping=json.load(open(MAP,encoding='utf-8'))
byloc={str(m.get('electroverseLocationPk')):m for m in mapping.get('mappings',[])}
# published provenance + targets
man=json.load(open(OVER+'/manifest.json',encoding='utf-8'))
pubsrc=set(); pubtgt=set()
for t in man.get('tiles',[]):
    with gzip.open(OVER+'/'+t['file'],'rt',encoding='utf-8') as fh:d=json.load(fh)
    for o in d.get('emspOffers',[]):
        md=o.get('metadata') or {}
        for pk in md.get('electroverseEvsePks') or []: pubsrc.add(str(pk))
        if md.get('electroverseEvsePk') is not None: pubsrc.add(str(md['electroverseEvsePk']))
        for pk in md.get('electroverseAliasEvsePks') or []: pubsrc.add(str(pk))
        for x in o.get('evseIds') or []: pubtgt.add(str(x).upper().replace('*',''))
# all tariff EVSEs at targeted locations
cman=json.load(open(CACHE+'/manifest.json',encoding='utf-8'))
all_by_loc={x:[] for x in LOCS}
for sh in cman.get('shards',[]):
    d=json.load(open(CACHE+'/'+sh['file'],encoding='utf-8'))
    for row in (d.get('stations') or {}).values():
        loc=str(row.get('electroverseLocationPk') or '')
        if loc in LOCS: all_by_loc[loc].extend((row.get('tariff') or {}).get('evses') or [])
# PAN target technical profiles
wanted=set()
for loc in LOCS:
    for p in byloc.get(loc,{}).get('irvePdcIds',[]):wanted.add(str(p).upper().replace('*',''))
path='/tmp/pan.csv';urllib.request.urlretrieve(PAN,path)
official={}
with open(path,'r',encoding='utf-8-sig',newline='') as fh:
    sample=fh.read(4096);fh.seek(0)
    try:dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
    except:dialect=csv.excel
    rd=csv.DictReader(fh,dialect=dialect)
    for row in rd:
        p=str(row.get('id_pdc_itinerance') or '').upper().replace('*','')
        if p in wanted:official[p]=row
def nk(v):
    try:n=float(v)
    except:return None
    for b,t in [(4,1),(7,1.5),(11,1),(18,1.5),(22,1.5),(50,2),(60,3),(160,5),(180,5),(200,5)]:
        if abs(n-b)<=t:return b
    return round(n,2)
def srcstd(c):
    s=c.get('standard')
    if isinstance(s,dict):s=s.get('name')
    return str(s or '')
def tgtstd(r):
    if str(r.get('prise_type_combo_ccs')).lower()=='true':return 'IEC_62196_T2_COMBO'
    if str(r.get('prise_type_chademo')).lower()=='true':return 'CHADEMO'
    if str(r.get('prise_type_2')).lower()=='true':return 'IEC_62196_T2'
    if str(r.get('prise_type_ef')).lower()=='true':return 'DOMESTIC_F'
    return 'OTHER'
def psig(e):
    return json.dumps([{'free':c.get('isChargingFree'),'pc':c.get('priceComponents'),'complex':c.get('complexPricingDetail')} for c in (e.get('connectors') or [])],sort_keys=True,ensure_ascii=False)
ready=[];audit=[]
for loc in sorted(LOCS):
    evses=all_by_loc.get(loc,[])
    unpub=[e for e in evses if str(e.get('pk')) not in pubsrc]
    sg={}
    for e in unpub:
        cs=e.get('connectors') or []
        if len(cs)!=1:continue
        sig=(nk(cs[0].get('kilowatts')),srcstd(cs[0]))
        sg.setdefault(sig,[]).append(e)
    m=byloc.get(loc,{})
    available=[str(p).upper().replace('*','') for p in m.get('irvePdcIds',[]) if str(p).upper().replace('*','') not in pubtgt]
    tg={}
    for p in available:
        r=official.get(p)
        if not r:continue
        sig=(nk(r.get('puissance_nominale')),tgtstd(r));tg.setdefault(sig,[]).append(p)
    locready=[]
    for sig,srcs in sg.items():
        tgts=tg.get(sig,[])
        if not srcs or len(srcs)!=len(tgts):continue
        prices={psig(e) for e in srcs}
        if len(prices)!=1:continue
        cand={
          'mode':'homogeneous_target_subset','operator':'CROSS_BUCKET_B_COMPLETION',
          'electroverseLocationPk':loc,'irveStationId':m.get('irveStationId'),
          'sourceEvsePks':[e.get('pk') for e in srcs],
          'physicalReferences':[e.get('physicalReference') for e in srcs],
          'targetPdcs':tgts,'uniformConnectorCount':True,
          'profile':{'kilowatts':sig[0],'standard':sig[1]},
          'evidence':{'source':'full Electroverse tariff cache + current PAN national IRVE + final overlay exclusion','observed':'2026-10-02','note':'All currently unpublished source EVSEs in the technical class exactly match all currently unclaimed national PDCs in the same class, with identical compiled pricing across sources. Cross-bucket completion prevents operator-prefix classification from hiding siblings.'}
        }
        locready.append(cand);ready.append(cand)
    audit.append({'locationPk':loc,'station':m.get('irveStationId'),'allSourceCount':len(evses),'unpublishedSourceCount':len(unpub),'availableTargetCount':len(available),'sourceGroups':{str(k):len(v) for k,v in sg.items()},'targetGroups':{str(k):len(v) for k,v in tg.items()},'ready':locready})
out={'generatedAt':'2026-10-02','readyGroupCount':len(ready),'readySourceEvses':sum(len(x['sourceEvsePks']) for x in ready),'readyLocations':len(set(x['electroverseLocationPk'] for x in ready)),'ready':ready,'audit':audit}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({k:out[k] for k in ['readyGroupCount','readySourceEvses','readyLocations']},indent=2))
