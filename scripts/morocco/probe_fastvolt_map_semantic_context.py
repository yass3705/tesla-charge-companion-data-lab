#!/usr/bin/env python3
import json,re
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen

BASE='https://www.fastvolt.net/carte'
UA='TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)'
MAX_ASSETS=24
MAX_BYTES=2_000_000
KEYWORDS=('locations','location','station','stations','borne','bornes','marker','markers','latitude','longitude','lat','lng','status','charger','charging','connector','evse')

class P(HTMLParser):
    def __init__(self): super().__init__(); self.scripts=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='script' and d.get('src'): self.scripts.append(d['src'])

def fetch(url):
    req=Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/javascript,text/javascript,*/*;q=0.1'},method='GET')
    with urlopen(req,timeout=20) as r:
        b=r.read(MAX_BYTES+1); trunc=len(b)>MAX_BYTES; b=b[:MAX_BYTES]
        return {'status':getattr(r,'status',200),'content_type':r.headers.get('Content-Type'),'bytes_read':len(b),'truncated':trunc,'text':b.decode('utf-8','replace')}

def same_origin(url): return urlparse(url).hostname in {'www.fastvolt.net','fastvolt.net'}

def endpoint_literals(text):
    out=set()
    for pat in (r'https?://[^"\'\s<>]+',r'(?<![A-Za-z0-9_])/(?:api|app|map|maps|station|stations|location|locations|charging|charger|chargers|borne|bornes)[A-Za-z0-9_./?=&%:-]*'):
        for m in re.findall(pat,text,flags=re.I):
            s=m.rstrip("'),;]}")
            if len(s)<=300: out.add(s)
    return sorted(out)

def identifier_contexts(text):
    records=[]; seen=set()
    ident_re=re.compile(r'\b[A-Za-z_][A-Za-z0-9_]{2,80}\b')
    for kw in KEYWORDS:
        for m in re.finditer(r'(?i)(?<![A-Za-z0-9_])'+re.escape(kw)+r'(?![A-Za-z0-9_])',text):
            lo=max(0,m.start()-600); hi=min(len(text),m.end()+600); ctx=text[lo:hi]
            ids=[]; ids_seen=set()
            for x in ident_re.findall(ctx):
                if x not in ids_seen:
                    ids.append(x); ids_seen.add(x)
            eps=endpoint_literals(ctx)
            # Persist identifier names and endpoint-looking literals only; never raw source/value context.
            key=(kw,tuple(ids[:80]),tuple(eps[:20]))
            if key in seen: continue
            seen.add(key)
            records.append({'keyword':kw,'identifiers':ids[:80],'endpoint_literals':eps[:20]})
            if len(records)>=160: return records
    return records

report={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'policy':{'read_only':True,'get_only':True,'no_login':True,'no_mutations':True,'no_session_start':True,'same_origin_assets_only':True,'raw_bodies_persisted':False,'raw_context_persisted':False,'identifier_names_only':True,'endpoint_literals_only':True},'page_url':BASE,'assets':[],'errors':[]}
try:
    page=fetch(BASE); p=P(); p.feed(page['text'])
    urls=[]
    for src in p.scripts:
        u=urljoin(BASE,src)
        if same_origin(u) and u not in urls: urls.append(u)
    report['page']={k:v for k,v in page.items() if k!='text'}
    for u in urls[:MAX_ASSETS]:
        rec={'url':u}
        try:
            a=fetch(u); rec.update({k:v for k,v in a.items() if k!='text'})
            hits=identifier_contexts(a['text'])
            if hits: rec['semantic_contexts']=hits
            rec['semantic_context_count']=len(hits)
        except Exception as e: rec['error']=type(e).__name__+': '+str(e)[:180]
        report['assets'].append(rec)
except Exception as e: report['errors'].append(type(e).__name__+': '+str(e)[:240])
json.dump(report,__import__('sys').stdout,ensure_ascii=False,indent=2); print()
