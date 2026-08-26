#!/usr/bin/env python3
import json,re,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

BASE='https://carburantiq.fr/api'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36'

def norm(v): return re.sub(r'[^A-Z0-9]','',str(v or '').upper())
def fetch_json(url,timeout=20):
    req=Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*','Referer':'https://carburantiq.fr/'})
    with urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode('utf-8',errors='replace'))
def coords(raw):
    m=re.findall(r'-?\d+(?:\.\d+)?',str(raw or ''))
    return (float(m[1]),float(m[0])) if len(m)>=2 else (None,None)
def find_station(obj,target):
    target=norm(target)
    candidates=[]
    def walk(x):
        if isinstance(x,dict):
            sid=x.get('id') or x.get('station_id') or x.get('stationId') or x.get('id_station_itinerance')
            if sid and norm(sid)==target: candidates.append(x)
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(obj)
    return candidates[0] if candidates else None

def compact_station(s):
    if not isinstance(s,dict): return None
    keep=['id','name','operator','network','brand','address','city','postal_code','latitude','longitude','max_power_kw','power_kw','tariff','price','price_per_kwh_eur','price_source','price_status','badge','updated_at']
    return {k:s.get(k) for k in keep if k in s}

def main(index_path,out_path):
    idx=json.loads(Path(index_path).read_text(encoding='utf-8'))
    results=[]; sources=Counter(); statuses=Counter()
    for i,s in enumerate(idx['stations']):
        lat,lon=coords(s.get('coordinatesRaw'))
        row={'stationId':s['stationId'],'stationName':s.get('stationName'),'address':s.get('address'),'powerKw':s.get('powerKw'),'lat':lat,'lon':lon}
        if lat is None:
            row['error']='no_coordinates'; results.append(row); continue
        q=urlencode({'lat':lat,'lon':lon,'radius':1.5,'max_results':20,'resolve_tariff':1,'_r':int(time.time()*1000)})
        try:
            data=fetch_json(BASE+'/charging/nearest?'+q)
            st=find_station(data,s['stationId'])
            row['matched']=bool(st)
            row['apiStation']=compact_station(st)
            tariff=(st or {}).get('tariff') if isinstance(st,dict) else None
            row['tariff']=tariff
            if isinstance(tariff,dict):
                src=str(tariff.get('source') or 'unknown').lower(); sources[src]+=1
                status=str(tariff.get('status') or tariff.get('badge') or '').lower();
                if status: statuses[status]+=1
            if st:
                try:
                    detail=fetch_json(BASE+'/charging/stations/'+str(st.get('id')))
                    ds=find_station(detail,s['stationId']) or (detail.get('station') if isinstance(detail,dict) else None)
                    row['detailStation']=compact_station(ds)
                    if isinstance(ds,dict) and isinstance(ds.get('tariff'),dict): row['detailTariff']=ds['tariff']
                except Exception as e: row['detailError']=f'{type(e).__name__}: {e}'
        except Exception as e:
            row['error']=f'{type(e).__name__}: {e}'
        results.append(row)
        time.sleep(0.15)
    publishable=[]
    for r in results:
        t=r.get('detailTariff') or r.get('tariff')
        if not isinstance(t,dict): continue
        src=str(t.get('source') or '').lower()
        conf=t.get('confidence')
        if src in {'official','confirmed','operator','direct','community_confirmed'} or (isinstance(conf,(int,float)) and conf>=0.7 and src!='estimate'):
            publishable.append({'stationId':r['stationId'],'address':r['address'],'powerKw':r['powerKw'],'tariff':t})
    out={
      'schemaVersion':'1.0.0','dataset':'avia-picoty-carburantiq-public-evidence-sweep','generatedAt':datetime.now(timezone.utc).isoformat(),
      'source':BASE,'policy':'public_unauthenticated_api_evidence_only_estimates_not_publishable',
      'counts':{'stationInput':len(results),'matched':sum(bool(r.get('matched')) for r in results),'publishableEvidence':len(publishable)},
      'sourceSummary':dict(sources),'statusSummary':dict(statuses),'publishableEvidence':publishable,'stations':results
    }
    Path(out_path).parent.mkdir(parents=True,exist_ok=True); Path(out_path).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'counts':out['counts'],'sourceSummary':out['sourceSummary'],'statusSummary':out['statusSummary'],'publishableEvidence':publishable},ensure_ascii=False,indent=2))
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
