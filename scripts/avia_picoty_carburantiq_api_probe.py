#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE='https://carburantiq.fr/api'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36'

# Coordinates come from the current PAN FR*PY2 extract. Spread across price/power classes.
SAMPLES=[
    {'name':'saint-maurice-la-souterraine','stationId':'FRPY2P233000008','lat':46.20279,'lon':1.39517},
    {'name':'la-souterraine','stationId':'FRPY2233000000','lat':46.24066,'lon':1.48931},
    {'name':'narbonne','stationId':'FRPY2P111000080','lat':43.18157,'lon':2.97679},
    {'name':'saint-sauveur-daunis','stationId':'FRPY2P175400067','lat':46.23016,'lon':-0.88306},
    {'name':'gien','stationId':'FRPY2P455000110','lat':47.71791,'lon':2.64833},
    {'name':'cholet','stationId':'FRPY2P493000035','lat':47.04210,'lon':-0.91614},
    {'name':'niort','stationId':'FRPY2P790000005','lat':46.33560,'lon':-0.40571},
    {'name':'les-sables','stationId':'FRPY2P851000109','lat':46.52164,'lon':-1.78087},
    {'name':'limoges','stationId':'FRPY2P870000032','lat':45.82714,'lon':1.25897},
]

def fetch_json(url, timeout=25):
    req=Request(url, headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*','Referer':'https://carburantiq.fr/'})
    try:
        with urlopen(req, timeout=timeout) as r:
            raw=r.read().decode('utf-8',errors='replace')
            try: data=json.loads(raw)
            except Exception: data=None
            return {'ok':True,'status':r.status,'contentType':r.headers.get('content-type',''),'bytes':len(raw.encode()),'json':data,'rawPreview':raw[:1200] if data is None else None}
    except HTTPError as e:
        raw=e.read().decode('utf-8',errors='replace')
        return {'ok':False,'status':e.code,'error':f'HTTPError: {e}','rawPreview':raw[:1200]}
    except Exception as e:
        return {'ok':False,'error':f'{type(e).__name__}: {e}'}

def contains_picoty(obj):
    try: s=json.dumps(obj,ensure_ascii=False).lower()
    except Exception: s=str(obj).lower()
    return any(x in s for x in ['frpy2','fr*py2','picoty','avia volt'])

def compact_picoty(obj, limit=120):
    """Recursively retain list/dict branches mentioning Picoty/FRPY2, bounded for audit output."""
    found=[]
    def walk(x,path=''):
        if len(found)>=limit: return
        if isinstance(x,dict):
            if contains_picoty(x):
                # Store compact records that look station/charger/tariff related.
                keys={k:v for k,v in x.items() if k.lower() in {
                    'id','station_id','stationid','station_name','stationname','name','operator','operator_name','network','brand','evse_id','evseid','id_pdc_itinerance',
                    'price','price_per_kwh','price_per_kwh_eur','resolved_price','resolved_price_eur','tariff','tariff_source','tariff_status','price_source','price_status','price_confidence','badge','status',
                    'power_kw','max_power_kw','latitude','longitude','lat','lon','address','city','postal_code','postcode','updated_at','validated_at','confirmed_at'
                }}
                if keys and any(k in ''.join(keys.keys()).lower() for k in ['id','name','operator','price','tariff','power']):
                    found.append({'path':path,'record':keys})
            for k,v in x.items(): walk(v,f'{path}.{k}' if path else str(k))
        elif isinstance(x,list):
            for i,v in enumerate(x): walk(v,f'{path}[{i}]')
    walk(obj)
    return found

def main(out_path):
    out={'generatedAt':datetime.now(timezone.utc).isoformat(),'base':BASE,'policy':'public_unauthenticated_endpoints_only','operatorPrices':None,'samples':[]}
    op=fetch_json(BASE+'/charging/operator-prices')
    out['operatorPrices']={'response':op,'picotyFindings':compact_picoty(op.get('json')) if op.get('json') is not None else []}
    for s in SAMPLES:
        q=urlencode({'lat':s['lat'],'lon':s['lon'],'radius':3,'max_results':30,'resolve_tariff':1})
        url=BASE+'/charging/nearest?'+q
        resp=fetch_json(url)
        findings=compact_picoty(resp.get('json')) if resp.get('json') is not None else []
        item={'sample':s,'nearestUrl':url,'nearestResponseMeta':{k:v for k,v in resp.items() if k!='json'},'picotyFindings':findings}
        # Collect candidate internal station ids from findings and probe at most 5 unique public details.
        candidate=[]
        for f in findings:
            r=f.get('record') or {}
            for key in ['id','station_id','stationId']:
                val=r.get(key)
                if val is not None and str(val) not in candidate: candidate.append(str(val))
        details=[]
        for cid in candidate[:5]:
            durl=BASE+'/charging/stations/'+cid
            d=fetch_json(durl)
            details.append({'id':cid,'url':durl,'responseMeta':{k:v for k,v in d.items() if k!='json'},'picotyFindings':compact_picoty(d.get('json')) if d.get('json') is not None else []})
        item['stationDetails']=details
        out['samples'].append(item)
    with open(out_path,'w',encoding='utf-8') as f:
        json.dump(out,f,ensure_ascii=False,indent=2); f.write('\n')
    summary={
        'operatorPricesStatus':(out['operatorPrices']['response'] or {}).get('status'),
        'operatorPricesPicotyFindings':len(out['operatorPrices']['picotyFindings']),
        'samples':[{'name':x['sample']['name'],'status':x['nearestResponseMeta'].get('status'),'picotyFindings':len(x['picotyFindings']),'detailProbes':len(x['stationDetails'])} for x in out['samples']]
    }
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else 'data/reports/avia_picoty_carburantiq_api_probe.json')
