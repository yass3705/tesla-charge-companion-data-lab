import csv,json,urllib.request,re,os
URL='https://www.data.gouv.fr/api/1/datasets/r/4ca78c71-4ea4-475d-bd3a-d4aef88f7bf8'
path='/tmp/pan.csv';urllib.request.urlretrieve(URL,path)
hits=[]
with open(path,'r',encoding='utf-8-sig',newline='') as fh:
    sample=fh.read(4096);fh.seek(0)
    try:dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
    except:dialect=csv.excel
    rd=csv.DictReader(fh,dialect=dialect)
    for r in rd:
        blob=' '.join(str(v or '') for v in r.values()).upper()
        if 'FERDINAND BRAUN' in blob and ('DREAM' in blob or 'FRDRE' in blob):
            hits.append(r)
out={'generatedAt':'2026-10-02','url':URL,'count':len(hits),'rows':hits}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open('reports/electroverse/b-dree-ferdinand-braun-pan-all.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps({'count':len(hits),'rows':[{
 k:r.get(k) for k in ['id_station_itinerance','id_station_local','nom_station','adresse_station','id_pdc_itinerance','id_pdc_local','puissance_nominale','prise_type_2','prise_type_combo_ccs','prise_type_chademo','date_maj','nom_operateur']
} for r in hits]},ensure_ascii=False,indent=2))
