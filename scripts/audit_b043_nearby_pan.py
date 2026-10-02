import csv,json,urllib.request,math,os
MAP='data/electroverse/irve_location_mapping.json'
OUT='reports/electroverse/b043-nearby-pan-audit.json'
URL='https://www.data.gouv.fr/api/1/datasets/r/4ca78c71-4ea4-475d-bd3a-d4aef88f7bf8'
m=json.load(open(MAP,encoding='utf-8'))
row=next(x for x in m.get('mappings',[]) if str(x.get('electroverseLocationPk'))=='4464822')
lat=float(row['electroverse']['lat']);lon=float(row['electroverse']['lon'])
def hav(a,b,c,d):
 R=6371000
 p1,p2=math.radians(a),math.radians(c)
 dp=math.radians(c-a);dl=math.radians(d-b)
 x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 2*R*math.asin(math.sqrt(x))
path='/tmp/pan.csv';urllib.request.urlretrieve(URL,path)
hits=[]
with open(path,'r',encoding='utf-8-sig',newline='') as fh:
 sample=fh.read(4096);fh.seek(0)
 try:d=csv.Sniffer().sniff(sample,delimiters=',;\t')
 except:d=csv.excel
 rd=csv.DictReader(fh,dialect=d)
 for r in rd:
  try:
   la=float(str(r.get('consolidated_latitude') or r.get('latitude') or '').replace(',','.'))
   lo=float(str(r.get('consolidated_longitude') or r.get('longitude') or '').replace(',','.'))
  except: continue
  dist=hav(lat,lon,la,lo)
  if dist<=500:
   hits.append({
    'distanceM':round(dist,2),'station':r.get('id_station_itinerance'),'pdc':r.get('id_pdc_itinerance'),
    'stationLocal':r.get('id_station_local'),'pdcLocal':r.get('id_pdc_local'),
    'name':r.get('nom_station'),'address':r.get('adresse_station'),
    'powerKw':r.get('puissance_nominale'),'t2':r.get('prise_type_2'),'ef':r.get('prise_type_ef'),
    'ccs':r.get('prise_type_combo_ccs'),'chademo':r.get('prise_type_chademo'),
    'operator':r.get('nom_operateur'),'dateMaj':r.get('date_maj')
   })
hits.sort(key=lambda x:x['distanceM'])
out={'generatedAt':'2026-10-02','electroverseLocationPk':'4464822','lat':lat,'lon':lon,'mappedStation':row.get('irveStationId'),'mappedPdcs':row.get('irvePdcIds'),'nearbyCount':len(hits),'hits':hits}
os.makedirs('reports/electroverse',exist_ok=True)
json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))
