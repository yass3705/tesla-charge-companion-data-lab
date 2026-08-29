#!/usr/bin/env python3
"""Capture public Duferco station-detail responses produced by normal map interaction.

Chrome is geolocated to Genova, then visible Duferco marker images are clicked. We read
only response bodies already delivered to the public frontend. Request headers, cookies,
storage, request bodies and credentials are never inspected or persisted.
"""
from __future__ import annotations
import json,time,re
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

PAGE='https://mobility.dufercoenergia.com/'
HOST='prod-apimp400.dufercoenergia.com'
OUT=Path('data/reports/duferco_station_detail_response_probe.json')

def safe_detail(j):
    if not isinstance(j,dict): return {'type':type(j).__name__}
    # Keep public station/connector fields useful for PUN reconciliation and tariff semantics.
    scalar_allow=('id','guid','name','address','city','prov','lat','long','latitude','longitude','classType','idChargeType','poolType','isInRoaming','currentChargePointStatus','maxPower','power','operator','cpo','provider','parkingFee','parkingFeeUnit','currency')
    out={k:j.get(k) for k in scalar_allow if k in j}
    # Discover connector arrays conservatively by key name; persist only known technical/public fields.
    connector_keys=[]
    for k,v in j.items():
        if isinstance(v,list) and v and isinstance(v[0],dict) and any(x in str(k).lower() for x in ('connector','plug','socket','evse')):
            connector_keys.append(k)
            rows=[]
            for c in v[:20]:
                rows.append({x:c.get(x) for x in ('id','connectorEVSEID','evseId','evseID','plugId','plugType','status','power','maxPower','current','voltage','price','tariff','parkingFee','currency') if x in c})
            out[k]=rows
    out['_topKeys']=sorted(j.keys())
    out['_connectorArrayKeys']=connector_keys
    return out

def main():
    o=Options();o.add_argument('--headless=new');o.add_argument('--no-sandbox');o.add_argument('--disable-dev-shm-usage');o.add_argument('--window-size=1440,1100');o.add_experimental_option('prefs',{'profile.default_content_setting_values.geolocation':1});o.set_capability('goog:loggingPrefs',{'performance':'ALL'})
    d=webdriver.Chrome(options=o); clicks=[]; responses=[]; errors=[]
    try:
        d.execute_cdp_cmd('Emulation.setGeolocationOverride',{'latitude':44.4056,'longitude':8.9463,'accuracy':20})
        d.set_page_load_timeout(60)
        try:d.get(PAGE)
        except Exception as e:errors.append({'stage':'get','type':type(e).__name__})
        time.sleep(12)
        # Clear initial performance log; subsequent entries are attributable to interactions.
        try:d.get_log('performance')
        except Exception:pass
        # Google Maps renders marker icons as img elements. Click only public charge marker assets,
        # never UI actions that start a session.
        imgs=d.find_elements(By.CSS_SELECTOR,'img')
        candidates=[]
        for el in imgs:
            try:
                src=str(el.get_attribute('src') or '')
                if 'marker-' in src and any(x in src for x in ('quick','fast','ultrafast','base')):
                    candidates.append(el)
            except Exception:continue
        # De-duplicate by screen position and click a small sample.
        seen_pos=set()
        for el in candidates:
            if len(clicks)>=8:break
            try:
                loc=el.location_once_scrolled_into_view; key=(round(loc.get('x',0),0),round(loc.get('y',0),0))
                if key in seen_pos:continue
                seen_pos.add(key)
                d.execute_script("arguments[0].click();",el)
                clicks.append({'position':key})
                time.sleep(2.0)
            except Exception as e:errors.append({'stage':'click','type':type(e).__name__})
        # Capture only GET detail responses, not Range/Slider and not user/session APIs.
        seen=set()
        for row in d.get_log('performance'):
            try:m=json.loads(row['message'])['message']
            except Exception:continue
            if m.get('method')!='Network.responseReceived':continue
            p=m.get('params') or {};resp=p.get('response') or {};url=str(resp.get('url') or '')
            if HOST not in url or '/api/v4.0/Chargepoints/' not in url:continue
            path=url.split('?',1)[0]
            if any(x in path for x in ('/Range/','/Slider/')):continue
            if path in seen:continue
            seen.add(path)
            item={'urlPath':re.sub(r'^https?://[^/]+','',path),'status':resp.get('status'),'mimeType':resp.get('mimeType')}
            try:
                raw=d.execute_cdp_cmd('Network.getResponseBody',{'requestId':p.get('requestId')}).get('body','')
                j=json.loads(raw);item['detail']=safe_detail(j)
            except Exception as e:item['bodyError']=type(e).__name__
            responses.append(item)
    finally:d.quit()
    payload={'source':{'page':PAGE,'backendHost':HOST,'city':'Genova'},'security':{'accountCredentialsUsed':False,'requestHeadersRead':False,'cookiesRead':False,'storageRead':False,'requestBodiesRead':False,'startChargeActionsClicked':False},'clickCount':len(clicks),'detailResponseCount':len(responses),'errors':errors,'responses':responses}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    evse=[]
    for r in responses:
        d0=r.get('detail') or {}
        for k in d0.get('_connectorArrayKeys') or []:
            for c in d0.get(k) or []:
                if c.get('connectorEVSEID'):evse.append(c['connectorEVSEID'])
    print(json.dumps({'clickCount':len(clicks),'detailResponseCount':len(responses),'connectorEvseIds':evse[:30],'errors':errors},ensure_ascii=False,indent=2))
    if not responses:raise RuntimeError(f'No station detail responses captured clicks={len(clicks)} errors={errors}')
    if not evse:raise RuntimeError('Station details captured but no connectorEVSEID found')
if __name__=='__main__':main()
