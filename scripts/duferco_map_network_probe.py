#!/usr/bin/env python3
"""Discover read-only data calls made by the public Duferco Mobility map.

Stores only request URL/method/resource type and small response schema summaries for
station/map-like XHR/fetch calls. No cookies, auth headers or request bodies are persisted.
"""
from __future__ import annotations
import json,time
from collections import Counter
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE='https://mobility.dufercoenergia.com/'
OUT=Path('data/reports/duferco_map_network_probe.json')
KEYWORDS=('station','charge','map','point','connector','location','infrastructure','colonn','presa','marker')

def summary(v,depth=0):
    if depth>2:return type(v).__name__
    if isinstance(v,dict): return {'type':'object','keys':sorted(map(str,v.keys()))[:80]}
    if isinstance(v,list): return {'type':'array','length':len(v),'first':summary(v[0],depth+1) if v else None}
    return {'type':type(v).__name__}

def main():
    o=Options(); o.add_argument('--headless=new'); o.add_argument('--no-sandbox'); o.add_argument('--disable-dev-shm-usage'); o.add_argument('--window-size=1440,1000'); o.set_capability('goog:loggingPrefs',{'performance':'ALL'})
    d=webdriver.Chrome(options=o); calls=[]; errors=[]
    try:
        d.set_page_load_timeout(60)
        try:d.get(PAGE)
        except Exception as e: errors.append({'stage':'get','type':type(e).__name__})
        time.sleep(12)
        logs=d.get_log('performance')
        seen=set()
        for row in logs:
            try:m=json.loads(row['message'])['message']
            except Exception:continue
            if m.get('method')!='Network.responseReceived':continue
            p=m.get('params') or {}; r=p.get('response') or {}; url=str(r.get('url') or ''); typ=str(p.get('type') or '')
            if typ not in {'XHR','Fetch'}:continue
            if url in seen:continue
            seen.add(url)
            item={'url':url,'status':r.get('status'),'mimeType':r.get('mimeType'),'resourceType':typ}
            low=url.lower()
            if any(k in low for k in KEYWORDS):
                try:
                    body=d.execute_cdp_cmd('Network.getResponseBody',{'requestId':p.get('requestId')}).get('body','')
                    if len(body)<=4_000_000:
                        try:item['jsonSummary']=summary(json.loads(body))
                        except Exception:item['textPrefix']=body[:250] if body.lstrip().startswith(('{','[')) else None
                except Exception as e:item['bodyReadError']=type(e).__name__
            calls.append(item)
    finally:d.quit()
    hosts=Counter()
    from urllib.parse import urlparse
    for c in calls:hosts[urlparse(c['url']).netloc]+=1
    payload={'page':PAGE,'security':{'accountCredentialsUsed':False,'requestHeadersPersisted':False,'cookiesPersisted':False,'requestBodiesPersisted':False},'errors':errors,'xhrFetchCount':len(calls),'hostCounts':dict(hosts),'calls':calls}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'errors':errors,'xhrFetchCount':len(calls),'hostCounts':dict(hosts),'interesting':[x for x in calls if x.get('jsonSummary')][:30]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
