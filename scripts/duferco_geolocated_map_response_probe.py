#!/usr/bin/env python3
"""Capture the public Duferco map's own Range response after geolocating Chrome in Italy.

No request headers, cookies, request bodies or credentials are read or persisted. We only
parse the JSON response already delivered to the public map frontend.
"""
from __future__ import annotations
import json,time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE='https://mobility.dufercoenergia.com/'
HOST='prod-apimp400.dufercoenergia.com'
OUT=Path('data/reports/duferco_geolocated_map_response_probe.json')

def sanitize(v,depth=0):
    if depth>3:return None
    if isinstance(v,dict):
        out={}
        for k,x in v.items():
            lk=str(k).lower()
            if any(s in lk for s in ('token','secret','authorization','apikey','api_key','password','email','phone')):continue
            if isinstance(x,(str,int,float,bool)) or x is None:out[k]=x
            elif isinstance(x,(dict,list)):out[k]=sanitize(x,depth+1)
        return out
    if isinstance(v,list):return [sanitize(x,depth+1) for x in v[:12]]
    return v if isinstance(v,(str,int,float,bool)) or v is None else None

def main():
    o=Options();o.add_argument('--headless=new');o.add_argument('--no-sandbox');o.add_argument('--disable-dev-shm-usage');o.add_argument('--window-size=1440,1000');o.add_experimental_option('prefs',{'profile.default_content_setting_values.geolocation':1});o.set_capability('goog:loggingPrefs',{'performance':'ALL'})
    d=webdriver.Chrome(options=o);rows=[];errors=[]
    try:
        d.execute_cdp_cmd('Emulation.setGeolocationOverride',{'latitude':44.4056,'longitude':8.9463,'accuracy':20})
        d.set_page_load_timeout(60)
        try:d.get(PAGE)
        except Exception as e:errors.append({'stage':'get','type':type(e).__name__})
        time.sleep(15)
        for r in d.get_log('performance'):
            try:m=json.loads(r['message'])['message']
            except Exception:continue
            if m.get('method')!='Network.responseReceived':continue
            p=m.get('params') or {};resp=p.get('response') or {};url=str(resp.get('url') or '')
            if HOST not in url or '/Chargepoints/Range/' not in url:continue
            item={'url':url,'status':resp.get('status'),'mimeType':resp.get('mimeType')}
            try:
                raw=d.execute_cdp_cmd('Network.getResponseBody',{'requestId':p.get('requestId')}).get('body','');j=json.loads(raw)
                markers=j.get('markers') or [] if isinstance(j,dict) else []
                item['topKeys']=sorted(j.keys()) if isinstance(j,dict) else []
                item['markerCount']=len(markers) if isinstance(markers,list) else None
                item['markerKeySets']=[list(x) for x in sorted({tuple(sorted(z.keys())) for z in markers if isinstance(z,dict)},key=str)[:30]]
                item['samples']=[sanitize(z) for z in markers[:8]] if isinstance(markers,list) else []
            except Exception as e:item['bodyError']=type(e).__name__
            rows.append(item)
    finally:d.quit()
    payload={'source':{'page':PAGE,'backendHost':HOST,'geolocation':{'lat':44.4056,'lon':8.9463,'city':'Genova'}},'security':{'accountCredentialsUsed':False,'requestHeadersRead':False,'requestHeadersPersisted':False,'cookiesRead':False,'requestBodiesRead':False},'errors':errors,'responses':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload,ensure_ascii=False,indent=2))
    assert any(x.get('status')==200 and (x.get('markerCount') or 0)>0 for x in rows), payload
if __name__=='__main__':main()
