#!/usr/bin/env python3
"""Find public station-detail endpoint strings in Duferco frontend bundles.

Persists only small redacted contexts around Chargepoint route names. No credentials,
request headers, cookies, storage or full bundle bodies are retained.
"""
from __future__ import annotations
import json,re,time
from pathlib import Path
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE='https://mobility.dufercoenergia.com/'
OUT=Path('data/reports/duferco_frontend_station_endpoint_probe.json')
TERMS=('Chargepoints/','ChargePoints/','Chargepoint/','ChargePoint/','chargepoints/','GetChargePoint','ChargePointDetail','chargePointId','idChargePoint')

def redact(s):
    s=re.sub(r'(?i)(authorization|bearer|token|secret|api[-_]?key|password)\s*[:=]\s*["\'][^"\']+["\']',r'\1=<redacted>',s)
    return s[:1200]

def main():
    o=Options();o.add_argument('--headless=new');o.add_argument('--no-sandbox');o.add_argument('--disable-dev-shm-usage');o.add_argument('--window-size=1440,1000');o.set_capability('goog:loggingPrefs',{'performance':'ALL'})
    d=webdriver.Chrome(options=o);hits=[]
    try:
        d.set_page_load_timeout(60)
        try:d.get(PAGE)
        except Exception:pass
        time.sleep(10)
        seen=set()
        for row in d.get_log('performance'):
            try:m=json.loads(row['message'])['message']
            except Exception:continue
            if m.get('method')!='Network.responseReceived':continue
            p=m.get('params') or {};r=p.get('response') or {};url=str(r.get('url') or '');mime=str(r.get('mimeType') or '')
            if url in seen or ('javascript' not in mime and not url.lower().split('?')[0].endswith('.js')):continue
            seen.add(url);host=urlparse(url).netloc.lower()
            if 'duferco' not in host:continue
            try:body=d.execute_cdp_cmd('Network.getResponseBody',{'requestId':p.get('requestId')}).get('body','')
            except Exception:continue
            low=body.lower()
            for term in TERMS:
                needle=term.lower();pos=0;n=0
                while True:
                    i=low.find(needle,pos)
                    if i<0 or n>=20:break
                    hits.append({'scriptPath':urlparse(url).path,'term':term,'context':redact(body[max(0,i-450):min(len(body),i+len(term)+750)])})
                    pos=i+len(term);n+=1
    finally:d.quit()
    payload={'source':PAGE,'security':{'accountCredentialsUsed':False,'requestHeadersRead':False,'cookiesRead':False,'storageRead':False,'fullBundlesPersisted':False},'hitCount':len(hits),'hits':hits[:160]}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'hitCount':len(hits),'terms':sorted({x['term'] for x in hits}),'samples':hits[:30]},ensure_ascii=False,indent=2))
    if not hits:raise RuntimeError('No public station endpoint contexts found')
if __name__=='__main__':main()
