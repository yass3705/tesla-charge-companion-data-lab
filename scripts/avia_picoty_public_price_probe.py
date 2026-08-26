#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36'

TARGETS=[
    ('carburantiq_chateauponsac','https://carburantiq.fr/borne-recharge/chateauponsac'),
    ('carburantiq_la_souterraine','https://carburantiq.fr/borne-recharge/saint-amand-magnazeix'),
    ('picoty_station_map','https://www.picoty.fr/implantations/carte-des-stations/'),
]
TOKENS=[
    'P23300','FR*PY2','FRPY2','0,40','0.40','0,50','0.50','tarif','price','estimate','estimation',
    'confirm','source','api/','/api','graphql','wp-json','admin-ajax','fetch(','axios','supabase'
]


def fetch(url, timeout=25):
    req=Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8'})
    with urlopen(req,timeout=timeout) as r:
        body=r.read()
        return r.status, r.headers.get('content-type',''), body.decode('utf-8',errors='replace')


def snippets(text, token, radius=180, limit=8):
    out=[]
    low=text.lower(); needle=token.lower(); start=0
    while len(out)<limit:
        i=low.find(needle,start)
        if i<0: break
        a=max(0,i-radius); b=min(len(text),i+len(token)+radius)
        s=re.sub(r'\s+',' ',unescape(text[a:b]))
        out.append(s)
        start=i+len(token)
    return out


def js_urls(base, html):
    urls=[]
    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']',html,re.I):
        u=urljoin(base,unescape(m.group(1)))
        if u not in urls: urls.append(u)
    return urls


def candidate_urls(text, base):
    vals=[]
    patterns=[
        r'https?://[^\s"\'<>]+',
        r'["\']((?:/|\.\.?/)[^"\']*(?:api|ajax|graphql|station|charge|price|tarif)[^"\']*)["\']',
    ]
    for pat in patterns:
        for m in re.finditer(pat,text,re.I):
            raw=m.group(1) if m.lastindex else m.group(0)
            raw=raw.rstrip(');,}')
            if any(k in raw.lower() for k in ['api','ajax','graphql','station','charge','price','tarif','deftpower','picoty']):
                u=urljoin(base,raw)
                if u not in vals: vals.append(u)
                if len(vals)>=120: return vals
    return vals


def main(out_path):
    report={'generatedAt':datetime.now(timezone.utc).isoformat(),'targets':[]}
    for name,url in TARGETS:
        item={'name':name,'url':url}
        try:
            status,ctype,html=fetch(url)
            item.update({'status':status,'contentType':ctype,'bytes':len(html.encode('utf-8'))})
            item['tokenSnippets']={t:snippets(html,t) for t in TOKENS if t.lower() in html.lower()}
            scripts=js_urls(url,html)
            item['scriptUrls']=scripts[:60]
            item['pageCandidateUrls']=candidate_urls(html,url)
            bundles=[]
            for js in scripts[:25]:
                # Keep the probe on public first-party/static assets referenced by the page.
                try:
                    st,ct,body=fetch(js,20)
                except Exception as e:
                    bundles.append({'url':js,'error':f'{type(e).__name__}: {e}'})
                    continue
                hits={t:snippets(body,t,220,5) for t in TOKENS if t.lower() in body.lower()}
                urls=candidate_urls(body,js)
                if hits or urls:
                    bundles.append({'url':js,'status':st,'contentType':ct,'bytes':len(body.encode('utf-8')),'tokenSnippets':hits,'candidateUrls':urls})
            item['bundleFindings']=bundles
        except Exception as e:
            item['error']=f'{type(e).__name__}: {e}'
        report['targets'].append(item)
    with open(out_path,'w',encoding='utf-8') as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print(json.dumps(report,ensure_ascii=False,indent=2)[:30000])

if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else 'data/reports/avia_picoty_public_price_probe.json')
