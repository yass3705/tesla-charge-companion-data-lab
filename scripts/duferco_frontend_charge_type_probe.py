#!/usr/bin/env python3
"""Inspect public Duferco frontend bundles for the idChargeType legend mapping.

Only small text contexts around non-sensitive public UI terms are persisted. No request
headers, cookies, storage, auth data or arbitrary bundle content is saved.
"""
from __future__ import annotations
import json,re,time
from pathlib import Path
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE='https://mobility.dufercoenergia.com/'
OUT=Path('data/reports/duferco_frontend_charge_type_probe.json')
TERMS=('idChargeType','Ultrafast','Ultra Fast','Quick','ChargePoints_DufercoEnergia','idChargeType===','idChargeType ==')

def clean_context(s):
    s=re.sub(r'(?i)(authorization|token|secret|api[-_]?key|password)\s*[:=]\s*["\'][^"\']+["\']',r'\1=<redacted>',s)
    return s[:800]

def main():
    o=Options();o.add_argument('--headless=new');o.add_argument('--no-sandbox');o.add_argument('--disable-dev-shm-usage');o.add_argument('--window-size=1440,1000');o.set_capability('goog:loggingPrefs',{'performance':'ALL'})
    d=webdriver.Chrome(options=o);hits=[];scripts=[]
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
            seen.add(url)
            host=urlparse(url).netloc.lower()
            if not (host.endswith('dufercoenergia.com') or host.endswith('dufercoenergia.it') or 'duferco' in host):continue
            scripts.append({'host':host,'path':urlparse(url).path,'status':r.get('status')})
            try:body=d.execute_cdp_cmd('Network.getResponseBody',{'requestId':p.get('requestId')}).get('body','')
            except Exception:continue
            low=body.lower()
            for term in TERMS:
                start=0;needle=term.lower();count=0
                while True:
                    idx=low.find(needle,start)
                    if idx<0 or count>=12:break
                    a=max(0,idx-260);b=min(len(body),idx+len(term)+520)
                    hits.append({'scriptPath':urlparse(url).path,'term':term,'context':clean_context(body[a:b])})
                    start=idx+len(term);count+=1
    finally:d.quit()
    # Also inspect rendered UI text for the public legend.
    payload={'source':PAGE,'security':{'accountCredentialsUsed':False,'requestHeadersRead':False,'cookiesRead':False,'storageRead':False,'fullBundlesPersisted':False},'scriptCount':len(scripts),'scripts':scripts,'hitCount':len(hits),'hits':hits[:120]}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'scriptCount':len(scripts),'hitCount':len(hits),'hitTerms':sorted({x['term'] for x in hits}),'samples':hits[:20]},ensure_ascii=False,indent=2))
    if not hits:raise RuntimeError('No public frontend contexts found for charge-type mapping')
if __name__=='__main__':main()
