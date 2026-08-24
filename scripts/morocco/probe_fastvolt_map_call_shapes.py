#!/usr/bin/env python3
import json,re
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen

BASE='https://www.fastvolt.net/carte'
UA='TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)'
MAX_BYTES=2_000_000
MAX_ASSETS=24

class P(HTMLParser):
    def __init__(self): super().__init__(); self.scripts=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='script' and d.get('src'): self.scripts.append(d['src'])

def fetch(url,accept):
    req=Request(url,headers={'User-Agent':UA,'Accept':accept},method='GET')
    with urlopen(req,timeout=20) as r:
        b=r.read(MAX_BYTES+1); truncated=len(b)>MAX_BYTES; b=b[:MAX_BYTES]
        return {'status':getattr(r,'status',200),'content_type':r.headers.get('Content-Type'),'bytes_read':len(b),'truncated':truncated,'text':b.decode('utf-8','replace')}

def same_origin(url): return urlparse(url).hostname in {'www.fastvolt.net','fastvolt.net'}

def uniq(xs,limit=80):
    out=[]
    for x in xs:
        if x not in out: out.append(x)
        if len(out)>=limit: break
    return out

def analyze(text):
    # Persist only operation names, URL/path literals, and call-shape metadata; never raw source context or response bodies.
    graphql_ops=[]
    for kind,name in re.findall(r'(?i)\b(query|mutation|subscription)\s+([A-Za-z_][A-Za-z0-9_]*)',text):
        graphql_ops.append({'kind':kind.lower(),'name':name})
    call_targets=[]
    pats=[
      r'fetch\(\s*["\']([^"\']{1,300})["\']',
      r'axios\.(?:get|post|request)\(\s*["\']([^"\']{1,300})["\']',
      r'\.get\(\s*["\']([^"\']{1,300})["\']',
      r'\.post\(\s*["\']([^"\']{1,300})["\']',
    ]
    for pat in pats: call_targets += re.findall(pat,text,flags=re.I)
    endpoint_literals=[]
    for pat in (r'https?://[^"\'\s<>]+',r'(?<![A-Za-z0-9_])/(?:api|app|graphql|map|maps|station|stations|location|locations|charging|charger|chargers|borne|bornes)[A-Za-z0-9_./?=&%:-]*'):
        endpoint_literals += re.findall(pat,text,flags=re.I)
    semantic_literals=[]
    lit_re=re.compile(r'["\']([^"\'\n\r]{1,180})["\']')
    terms=('fastvolt','station','borne','charger','charging','connector','evse','latitude','longitude','marker','map','location')
    for s in lit_re.findall(text):
        low=s.lower()
        if any(t in low for t in terms) and not low.startswith('data:'):
            semantic_literals.append(s)
    coord_like=len(re.findall(r'(?<!\d)-?\d{1,2}\.\d{4,}\s*[,}]\s*-?\d{1,3}\.\d{4,}',text))
    return {
      'graphql_operations':uniq([f"{x['kind']}:{x['name']}" for x in graphql_ops]),
      'call_targets':uniq(call_targets),
      'endpoint_literals':uniq([x.rstrip("'),;]}") for x in endpoint_literals]),
      'semantic_literals':uniq(semantic_literals,120),
      'coordinate_pair_like_count':coord_like,
    }

report={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'policy':{'read_only':True,'get_only':True,'no_login':True,'no_mutations':True,'no_session_start':True,'same_origin_assets_only':True,'raw_bodies_persisted':False,'raw_source_context_persisted':False,'literal_and_operation_names_only':True},'page_url':BASE,'assets':[],'errors':[]}
try:
    page=fetch(BASE,'text/html,*/*;q=0.1'); p=P(); p.feed(page['text'])
    urls=[]
    for src in p.scripts:
        u=urljoin(BASE,src)
        if same_origin(u) and u not in urls: urls.append(u)
    report['page']={k:v for k,v in page.items() if k!='text'}
    report['script_asset_count']=len(urls)
    for u in urls[:MAX_ASSETS]:
        rec={'url':u}
        try:
            a=fetch(u,'application/javascript,text/javascript,*/*;q=0.1')
            rec.update({k:v for k,v in a.items() if k!='text'})
            rec.update(analyze(a['text']))
        except Exception as e:
            rec['error']=type(e).__name__+': '+str(e)[:180]
        report['assets'].append(rec)
except Exception as e:
    report['errors'].append(type(e).__name__+': '+str(e)[:240])
json.dump(report,__import__('sys').stdout,ensure_ascii=False,indent=2); print()
