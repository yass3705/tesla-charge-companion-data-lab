#!/usr/bin/env python3
import json,re,urllib.request
from pathlib import Path
BASE="https://management.charge.agrola.ch/d/c{}"
UA={"User-Agent":"Mozilla/5.0","Accept":"text/html"}
rows=[]
for n in range(166120,166155):
    url=BASE.format(n)
    try:
        req=urllib.request.Request(url,headers=UA)
        with urllib.request.urlopen(req,timeout=20) as r:
            html=r.read().decode("utf-8","replace")
        title=None
        m=re.search(r'<p class="text-lg font-bold[^>]*>(.*?)</p>',html,re.S)
        if m:title=re.sub('<[^>]+>','',m.group(1)).strip()
        price=None; minute=None
        m=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*CHF<span[^>]*>/kWh',html)
        if m:price=float(m.group(1))
        m=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*CHF</span><span[^>]*>/<!-- -->min',html)
        if m:minute=float(m.group(1))
        if title or '137808' in html or '137809' in html:
            rows.append({"id":n,"url":url,"title":title,"pricePerKwh":price,"pricePerMinute":minute,"has137808":"137808" in html,"has137809":"137809" in html})
    except Exception as e:
        pass
out={"range":[166120,166154],"matches":rows}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-powerup-laupen-monta-neighbor-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
