import csv,json,urllib.request,os,re
RES='reports/electroverse/b-residual-analysis.json'
MAP='data/electroverse/irve_location_mapping.json'
OUT='reports/electroverse/b-final-site-extra-pan-inventory.json'
URL='https://www.data.gouv.fr/api/1/datasets/r/4ca78c71-4ea4-475d-bd3a-d4aef88f7bf8'
res=json.load(open(RES,encoding='utf-8'))
mapping=json.load(open(MAP,encoding='utf-8'))
byloc={str(m.get('electroverseLocationPk')):m for m in mapping.get('mappings',[])}
wanted_stations={str(g.get('irveStationId') or '') for g in res.get('unresolvedSamples',[])}
path='/tmp/pan.csv';urllib.request.urlretrieve(URL,path)
rows=[]
with open(path,'r',encoding='utf-8-sig',newline='') as fh:
    sample=fh.read(4096);fh.seek(0)
    try:dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
    except:dialect=csv.excel
    rd=csv.DictReader(fh,dialect=dialect)
    fields=rd.fieldnames or []
    rows=list(rd)
def norm(s):
    s=str(s or '').upper()
    s=re.sub(r'[^A-Z0-9]+',' ',s)
    return ' '.join(s.split())
anchors={}
for sid in wanted_stations:
    rr=[r for r in rows if str(r.get('id_station_itinerance') or '').upper()==sid.upper()]
    if rr:anchors[sid]=rr
outrows=[]
for g in res.get('unresolvedSamples',[]):
    sid=str(g.get('irveStationId') or ''); loc=str(g.get('electroverseLocationPk'))
    m=byloc.get(loc,{})
    anchor=anchors.get(sid,[])
    addresses={norm(r.get('adresse_station')) for r in anchor if r.get('adresse_station')}
    names={norm(r.get('nom_station')) for r in anchor if r.get('nom_station')}
    same=[]
    for r in rows:
        if not addresses:continue
        if norm(r.get('adresse_station')) in addresses:
            same.append({k:r.get(k) for k in ['id_station_itinerance','id_station_local','nom_station','adresse_station','id_pdc_itinerance','id_pdc_local','puissance_nominale','prise_type_ef','prise_type_2','prise_type_combo_ccs','prise_type_chademo','nom_operateur','nom_amenageur','date_maj']})
    mapped={str(x).upper().replace('*','') for x in m.get('irvePdcIds',[])}
    extras=[r for r in same if str(r.get('id_pdc_itinerance') or '').upper().replace('*','') not in mapped]
    outrows.append({'locationPk':loc,'stationId':sid,'anchorAddresses':list(addresses),'anchorNames':list(names),'mappedPdcs':sorted(mapped),'sameAddressCount':len(same),'extraPdcCount':len(extras),'extraRows':extras,'sameAddressRows':same})
out={'generatedAt':'2026-10-02','resourceUrl':URL,'fieldNames':fields,'rows':outrows}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({'stations':len(outrows),'extras':{x['stationId']:x['extraPdcCount'] for x in outrows}},indent=2,ensure_ascii=False))
