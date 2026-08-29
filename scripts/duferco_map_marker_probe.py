#!/usr/bin/env python3
"""Read-only probe of Duferco public map range endpoint in Italy.

Uses browser-origin fetch without persisting any request headers/cookies. If the endpoint
requires hidden authorization, the probe fails closed rather than extracting it.
"""
from __future__ import annotations
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE='https://mobility.dufercoenergia.com/'
API='https://prod-apimp400.dufercoenergia.com/api/v4.0/Chargepoints/Range/{south}/{west}/{north}/{east}/{zoom}'
OUT=Path('data/reports/duferco_map_marker_probe.json')
# Areas around known PUN DUF stations: Bergamo/Genoa/Aosta.
AREAS=[('bergamo',45.60,9.45,45.80,9.80,11),('genova',44.30,8.75,44.55,9.30,10),('aosta',45.55,6.85,45.85,7.75,9)]

def safe_marker(m):
    if not isinstance(m,dict):return {'type':type(m).__name__}
    # Persist only fields plausibly needed for public map identity/class/status, never arbitrary nested blobs.
    keys=('id','uid','code','name','title','latitude','longitude','lat','lng','status','type','category','power','maxPower','isDuferco','cpo','operator','provider','markerType','icon','cluster','chargePointId','evseId')
    return {k:m.get(k) for k in keys if k in m}

def main():
    o=Options();o.add_argument('--headless=new');o.add_argument('--no-sandbox');o.add_argument('--disable-dev-shm-usage');o.add_argument('--window-size=1280,900')
    d=webdriver.Chrome(options=o);results=[]
    try:
        d.set_page_load_timeout(60)
        try:d.get(PAGE)
        except Exception:pass
        d.set_script_timeout(40)
        for name,s,w,n,e,z in AREAS:
            url=API.format(south=s,west=w,north=n,east=e,zoom=z)
            r=d.execute_async_script("""
              const u=arguments[0],done=arguments[1];
              fetch(u,{method:'GET',credentials:'omit',headers:{'Accept':'application/json'}})
                .then(async x=>{const t=await x.text();let j=null;try{j=JSON.parse(t)}catch(_){};done({ok:x.ok,status:x.status,json:j,text:j?null:t.slice(0,200)})})
                .catch(e=>done({ok:false,status:null,error:String(e)}));
            """,url)
            row={'area':name,'ok':r.get('ok'),'status':r.get('status')}
            if r.get('ok') and isinstance(r.get('json'),dict):
                j=r['json']; markers=j.get('markers') or []
                row['topKeys']=sorted(j.keys());row['markerCount']=len(markers) if isinstance(markers,list) else None
                row['markerKeySets']=sorted({tuple(sorted(x.keys())) for x in markers if isinstance(x,dict)},key=str)[:20]
                row['samples']=[safe_marker(x) for x in markers[:25]] if isinstance(markers,list) else []
            else:row['error']=r.get('error') or r.get('text')
            results.append(row)
    finally:d.quit()
    if not any(x.get('ok') and (x.get('markerCount') or 0)>0 for x in results):raise RuntimeError(f'No readable public Italy markers: {results}')
    payload={'source':{'page':PAGE,'rangeEndpointTemplate':API},'security':{'accountCredentialsUsed':False,'requestHeadersPersisted':False,'cookiesPersisted':False,'hiddenAuthorizationExtracted':False},'areas':results}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
