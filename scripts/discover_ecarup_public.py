#!/usr/bin/env python3
import json,re,urllib.request,urllib.parse,html,pathlib

UA={'User-Agent':'Mozilla/5.0','Accept':'*/*'}
urls=['https://www.ecarup.com/code','https://ecarup.com/code','https://app.ecarup.com/','https://web.ecarup.com/']

def get(url,limit=12000000):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=35) as r:
        return {'status':r.status,'finalUrl':r.geturl(),'contentType':r.headers.get('content-type',''),'body':r.read(limit)}

out={'pages':[],'scriptInspection':[]}
scripts=[]
for u in urls:
    try:
        x=get(u); txt=x['body'].decode('utf-8','replace')
        out['pages'].append({'url':u,'status':x['status'],'finalUrl':x['finalUrl'],'contentType':x['contentType'],'preview':txt[:8000]})
        for src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']',txt,re.I):
            su=urllib.parse.urljoin(x['finalUrl'],html.unescape(src))
            if su not in scripts:scripts.append(su)
    except Exception as e:
        out['pages'].append({'url':u,'error':type(e).__name__+': '+str(e)})
patterns=[r'https?://[^\s"\'<>]{5,500}',r'["\']([^"\']*(?:api|station|charger|chargepoint|instant|payment|graphql|tariff|price)[^"\']*)["\']']
for u in scripts[:50]:
    try:
        x=get(u,20000000); txt=x['body'].decode('utf-8','replace'); hits=[]
        for pat in patterns:
            for m in re.finditer(pat,txt,re.I):
                v=m.group(1) if m.lastindex else m.group(0)
                if 3<len(v)<1000 and v not in hits:hits.append(v)
                if len(hits)>=800:break
            if len(hits)>=800:break
        out['scriptInspection'].append({'url':u,'status':x['status'],'bytes':len(x['body']),'hits':hits})
    except Exception as e:
        out['scriptInspection'].append({'url':u,'error':type(e).__name__+': '+str(e)})
out['scriptCount']=len(scripts)
pathlib.Path('docs').mkdir(exist_ok=True)
pathlib.Path('docs/switzerland-ecarup-public-discovery-2026-09-28.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pages':[{k:v for k,v in x.items() if k!='preview'} for x in out['pages']],'scriptCount':len(scripts),'hitScripts':sum(bool(x.get('hits')) for x in out['scriptInspection'])},ensure_ascii=False,indent=2))
