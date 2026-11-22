#!/usr/bin/env python3
"""Capture the current Qwello webpack runtime around chunk filename generation."""
from __future__ import annotations
import hashlib,json,re,urllib.request
from pathlib import Path

SHELL='https://qwello.de/de/how-to'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'

def fetch(url,accept='*/*'):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':accept,'Accept-Language':'de-DE,de;q=0.9'})
    with urllib.request.urlopen(req,timeout=60) as r:
        raw=r.read();return raw,{'url':r.geturl(),'status':getattr(r,'status',200),'contentType':r.headers.get('Content-Type'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def contexts(text,token,r=5000,limit=12):
    out=[];start=0
    while len(out)<limit:
        i=text.find(token,start)
        if i<0:break
        out.append(text[max(0,i-r):min(len(text),i+len(token)+r)])
        start=i+len(token)
    return out

def main():
    raw,shell_meta=fetch(SHELL,'text/html,*/*');html=raw.decode('utf-8','replace')
    scripts=[]
    for m in re.finditer(r'\bsrc\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))',html,re.I):
        value=m.group(1) or m.group(2) or m.group(3)
        if value and value.endswith('.js'):
            from urllib.parse import urljoin
            scripts.append(urljoin(shell_meta['url'],value))
    scripts=list(dict.fromkeys(scripts))
    bundles=[]
    for url in scripts:
        raw,meta=fetch(url,'application/javascript,*/*');text=raw.decode('utf-8','replace')
        token_context={}
        for token in ('.u=', 'u=function', 'return"js/', "return'js/", 'webmap','home','webpackChunk','__webpack_require__'):
            c=contexts(text,token)
            if c:token_context[token]=c
        # Generic numeric mapping fragments, deliberately loose for diagnostics.
        map_fragments=[]
        for m in re.finditer(r'\d+:["\'][^"\']{1,120}["\']',text):
            frag=text[max(0,m.start()-500):min(len(text),m.start()+3500)]
            if any(x in frag for x in ('js/','home','webmap','.js','chunk')):
                map_fragments.append(frag)
            if len(map_fragments)>=30:break
        bundles.append({'meta':meta,'contexts':token_context,'mapFragments':list(dict.fromkeys(map_fragments))})
    out={'dataset':'germany-qwello-runtime-context','shell':shell_meta,'scriptUrls':scripts,'bundles':bundles}
    p=Path('data/germany/qwello_runtime_context.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_RUNTIME_CONTEXT='+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
