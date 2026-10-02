import csv, json, urllib.request, os
targets={
'FRSRGE12347805851','FRSRGE12347805852','FRSRGE12348894201','FRSRGE12348894202',
'FRSRGE12347806081','FRSRGE12347806082','FRSRGE12348894251','FRSRGE12348894252',
'FRSRGE12347806121','FRSRGE12347806122','FRSRGE12348894291','FRSRGE12348894292',
'FRSRGE12347805821','FRSRGE12347805822','FRSRGE12348894191','FRSRGE12348894192',
'FRSRGE12347805871','FRSRGE12347805872','FRSRGE12348894221','FRSRGE12348894222'
}
sources=[
 ('soregies_official','https://static.data.gouv.fr/resources/bornes-de-recharges-soregies/20260413-074836/irve-soregies-13042026.csv'),
 ('qualicharge_static','https://proxy.transport.data.gouv.fr/resource/qualicharge-irve-statique')
]
out={'sources':[]}
for name,url in sources:
    path=f'/tmp/{name}.csv'
    try:
        urllib.request.urlretrieve(url,path)
        matches=[]
        with open(path,'r',encoding='utf-8-sig',newline='') as fh:
            sample=fh.read(4096); fh.seek(0)
            try: dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
            except: dialect=csv.excel
            reader=csv.DictReader(fh,dialect=dialect)
            fields=reader.fieldnames or []
            for row in reader:
                vals=[str(v or '').strip().upper().replace('*','') for v in row.values()]
                rowblob='|'.join(vals)
                hit=[t for t in targets if t in rowblob]
                if hit:
                    slim={k:v for k,v in row.items() if v not in (None,'')}
                    matches.append({'hits':hit,'row':slim})
        out['sources'].append({'name':name,'url':url,'fields':fields,'matchCount':len(matches),'matches':matches})
    except Exception as e:
        out['sources'].append({'name':name,'url':url,'error':repr(e)})
os.makedirs('reports/electroverse',exist_ok=True)
with open('reports/electroverse/b-srg-official-open-data-audit.json','w',encoding='utf-8') as fh:
    json.dump(out,fh,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))
