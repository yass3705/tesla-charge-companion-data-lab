#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.request
from pathlib import Path
URL='https://qwello.de/js/app.af0ea5b4.js'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
TOKENS=['https://services.qwello.eu/v1/us/public/web','https://services.qwello.eu/v1']
def main():
    req=urllib.request.Request(URL,headers={'User-Agent':UA,'Accept':'application/javascript,*/*'})
    with urllib.request.urlopen(req,timeout=60) as r:text=r.read().decode('utf-8','replace')
    contexts={}
    for token in TOKENS:
        arr=[];start=0
        while True:
            i=text.find(token,start)
            if i<0:break
            arr.append(text[max(0,i-4000):min(len(text),i+len(token)+5000)])
            start=i+len(token)
        contexts[token]=arr
    out={'dataset':'germany-qwello-api-context','contexts':contexts}
    p=Path('data/germany/qwello_api_context.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_API_CONTEXT='+json.dumps(contexts,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
