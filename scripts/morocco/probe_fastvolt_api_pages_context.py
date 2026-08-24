#!/usr/bin/env python3
import json, re, sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE='https://www.fastvolt.net/carte'
TARGET='/api/pages'
UA='TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)'
MAX_BYTES=2_000_000
MAX_ASSETS=24

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.scripts=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='script' and d.get('src'): self.scripts.append(d['src'])

def fetch(url):
    req=Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/javascript,text/javascript,*/*;q=0.1'},method='GET')
    with urlopen(req,timeout=20) as r:
        b=r.read(MAX_BYTES+1); trunc=len(b)>MAX_BYTES; b=b[:MAX_BYTES]
        return {'status':getattr(r,'status',200),'content_type':r.headers.get('Content-Type'),'bytes_read':len(b),'truncated':trunc,'text':b.decode('utf-8','replace')}

def same_origin(u):
    return urlparse(u).hostname in {'www.fastvolt.net','fastvolt.net'}

def inspect_context(text):
    out=[]
    for m in re.finditer(re.escape(TARGET),text,re.I):
        s=max(0,m.start()-700); e=min(len(text),m.end()+700); ctx=text[s:e]
        # Persist only structural identifiers/method names and route-shaped literals; never raw context or arbitrary values.
        ids=[]; seen=set()
        for x in re.findall(r'\b[A-Za-z_$][A-Za-z0-9_$]{1,80}\b',ctx):
            xl=x.lower()
            if xl in {'fetch','axios','get','post','put','patch','delete','method','headers','body','params','query','slug','page','pages','url','pathname','searchparams','json'} or any(k in xl for k in ('page','slug','map','station','borne','charger','location')):
                if x not in seen: ids.append(x); seen.add(x)
        routes=[]; rseen=set()
        for q in re.findall(r'["\']([^"\']{1,180})["\']',ctx):
            if q.startswith('/') and any(k in q.lower() for k in ('api','page','map','station','borne','charger','location')):
                if q not in rseen: routes.append(q); rseen.add(q)
        methods=[]
        for meth in ('GET','POST','PUT','PATCH','DELETE'):
            if re.search(r'\b'+meth+r'\b',ctx,re.I): methods.append(meth)
        out.append({'identifiers':ids[:80],'route_literals':routes[:30],'http_method_tokens':methods})
    return out

report={
 'schema_version':1,
 'generated_at':datetime.now(timezone.utc).isoformat(),
 'policy':{'read_only':True,'no_login':True,'no_mutations':True,'no_session_start':True,'same_origin_assets_only':True,'raw_bodies_persisted':False,'raw_context_persisted':False,'identifier_names_only':True},
 'page_url':BASE,'target_literal':TARGET,'assets':[],'summary':{'occurrence_count':0,'assets_with_target':0},'errors':[]
}
try:
    p=fetch(BASE); parser=P(); parser.feed(p['text'])
    scripts=[]
    for src in parser.scripts:
        u=urljoin(BASE,src)
        if same_origin(u) and u not in scripts: scripts.append(u)
    total=0; hit_assets=0
    for u in scripts[:MAX_ASSETS]:
        rec={'url':u}
        try:
            a=fetch(u); contexts=inspect_context(a['text'])
            rec.update({k:v for k,v in a.items() if k!='text'})
            rec['target_occurrences']=len(contexts)
            if contexts:
                hit_assets+=1; total+=len(contexts); rec['contexts']=contexts
        except Exception as ex:
            rec['error']=type(ex).__name__+': '+str(ex)[:180]
        report['assets'].append(rec)
    report['summary']={'occurrence_count':total,'assets_with_target':hit_assets}
except Exception as ex:
    report['errors'].append(type(ex).__name__+': '+str(ex)[:250])
json.dump(report,sys.stdout,ensure_ascii=False,indent=2); print()
