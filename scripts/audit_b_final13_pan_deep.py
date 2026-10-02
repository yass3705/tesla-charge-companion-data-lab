import csv,json,urllib.request,os
RES='reports/electroverse/b-residual-analysis.json'
MAP='data/electroverse/irve_location_mapping.json'
OUT='reports/electroverse/b-final13-pan-deep-audit.json'
URL='https://www.data.gouv.fr/api/1/datasets/r/4ca78c71-4ea4-475d-bd3a-d4aef88f7bf8'
res=json.load(open(RES,encoding='utf-8'))
mapping=json.load(open(MAP,encoding='utf-8'))
byloc={str(m.get('electroverseLocationPk')):m for m in mapping.get('mappings',[])}
targets=set()
for g in res.get('unresolvedSamples',[]):
    m=byloc.get(str(g.get('electroverseLocationPk')),{})
    for p in m.get('irvePdcIds',[]):targets.add(str(p).upper().replace('*',''))
path='/tmp/pan_irve.csv';urllib.request.urlretrieve(URL,path)
official={}
with open(path,'r',encoding='utf-8-sig',newline='') as fh:
    sample=fh.read(4096);fh.seek(0)
    try:dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
    except:dialect=csv.excel
    rd=csv.DictReader(fh,dialect=dialect)
    for row in rd:
        p=str(row.get('id_pdc_itinerance') or '').upper().replace('*','')
        if p in targets:official[p]=row
keepcols=['id_station_itinerance','id_station_local','nom_station','adresse_station','id_pdc_itinerance','id_pdc_local','puissance_nominale','prise_type_ef','prise_type_2','prise_type_combo_ccs','prise_type_chademo','prise_type_autre','date_maj']
rows=[]
for g in res.get('unresolvedSamples',[]):
    loc=str(g.get('electroverseLocationPk'));m=byloc.get(loc,{})
    pan=[]
    for p0 in m.get('irvePdcIds',[]):
        p=str(p0).upper().replace('*','');r=official.get(p)
        if r:pan.append({k:r.get(k) for k in keepcols})
        else:pan.append({'id_pdc_itinerance':p,'missingFromPan':True})
    src=[]
    for r in g.get('refs',[]):
        src.append({
          'evsePk':r.get('evsePk'),'physicalReference':r.get('physicalReference'),
          'connectors':r.get('connectors'),'pricingSignature':json.dumps([{
            'isChargingFree':c.get('isChargingFree'),'priceComponents':c.get('priceComponents'),
            'complexPricingDetail':c.get('complexPricingDetail')
          } for c in (r.get('connectors') or [])],sort_keys=True,ensure_ascii=False)
        })
    rows.append({
      'locationPk':loc,'station':m.get('irveStationId') or g.get('irveStationId'),
      'residualCount':g.get('residualCount'),'availablePdcCount':g.get('availablePdcCount'),
      'mappingPdcs':m.get('irvePdcIds',[]),'sources':src,'panRows':pan
    })
out={'generatedAt':'2026-10-02','sourceResidualGeneratedAt':res.get('generatedAt'),'rows':rows}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({'rows':len(rows),'residualSourceEvses':res.get('residualSourceEvses')},indent=2))
