#!/usr/bin/env python3
import re,json,urllib.request,urllib.parse
from pathlib import Path
from datetime import datetime,timezone

PAGE="https://portal.eponet.ch/public-charge.php?id=243fdf344f5a44f4872998649ca89eb3"
HEAD={"User-Agent":"Mozilla/5.0","Accept":"text/html,*/*"}
def get(url):
    req=urllib.request.Request(url,headers=HEAD)
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.geturl(),r.read(3000000).decode("utf-8","replace"),dict(r.headers)

final,html,headers=get(PAGE)
scripts=[urllib.parse.urljoin(final,x) for x in re.findall(r'<script[^>]+src=["\']([^"\']+)',html,re.I)]
forms=[]
for m in re.finditer(r'<form\b([^>]*)>',html,re.I):
    a=m.group(1)
    act=re.search(r'action=["\']([^"\']*)',a,re.I)
    method=re.search(r'method=["\']([^"\']*)',a,re.I)
    forms.append({"action":urllib.parse.urljoin(final,act.group(1)) if act else None,"method":method.group(1) if method else None})
interesting_patterns=[
 r'(?:url|action)\s*[:=]\s*["\']([^"\']+)',
 r'(?:fetch|axios\.(?:get|post)|\$\.get|\$\.post)\s*\(\s*["\']([^"\']+)',
 r'["\']([^"\']*(?:public-charge|api\.php|charger|charge|rate|price|payment|connector)[^"\']*)["\']'
]
def hits(text):
    out=[]
    for pat in interesting_patterns:
        for m in re.findall(pat,text,re.I):
            if isinstance(m,tuple):m="".join(m)
            m=m.strip()
            if m and len(m)<500 and m not in out: out.append(m)
    return out

assets=[]
for s in scripts:
    try:
        fu,body,h=get(s)
        assets.append({"url":fu,"bytes":len(body),"hits":hits(body)[:500]})
    except Exception as e:
        assets.append({"url":s,"error":type(e).__name__+": "+str(e)})

# Extract safe page details: no cookies/tokens except the already-public QR id.
text=re.sub(r'<script\b[\s\S]*?</script>',' ',html,flags=re.I)
text=re.sub(r'<style\b[\s\S]*?</style>',' ',text,flags=re.I)
text=re.sub(r'<[^>]+>',' ',text)
text=re.sub(r'\s+',' ',text).strip()
inline_hits=hits(html)
out={
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "page":PAGE,"finalUrl":final,
 "scriptCount":len(scripts),"scripts":scripts,
 "forms":forms,
 "inlineHits":inline_hits[:1000],
 "assets":assets,
 "visibleTextPreview":text[:12000]
}
Path("docs/switzerland-eponet-public-charge-contract-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:120000])
