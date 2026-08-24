#!/usr/bin/env python3
import json, re, sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://www.fastvolt.net/carte"
MAX_ASSETS = 20
MAX_BYTES = 2_000_000
UA = "TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)"

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.scripts=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag == "script" and d.get("src"): self.scripts.append(d["src"])
        if tag == "link" and d.get("href"): self.links.append(d["href"])

def fetch(url):
    req=Request(url, headers={"User-Agent":UA, "Accept":"text/html,application/javascript,text/javascript,*/*;q=0.1"}, method="GET")
    with urlopen(req, timeout=20) as r:
        data=r.read(MAX_BYTES+1)
        truncated=len(data)>MAX_BYTES
        data=data[:MAX_BYTES]
        return {
            "status": getattr(r, "status", 200),
            "content_type": r.headers.get("Content-Type"),
            "bytes_read": len(data),
            "truncated": truncated,
            "text": data.decode("utf-8", "replace")
        }

def same_origin(url):
    return urlparse(url).hostname in {"www.fastvolt.net","fastvolt.net"}

def literals(text):
    pats = [
        r'https?://[^"\'\s<>]+',
        r'(?<![A-Za-z0-9_])/(?:api|app|map|maps|station|stations|charging|charger|chargers|borne|bornes)[A-Za-z0-9_./?=&%:-]*'
    ]
    out=set()
    for p in pats:
        for m in re.findall(p, text, flags=re.I):
            s=m.rstrip("'),;]}")
            if len(s) <= 300: out.add(s)
    return sorted(out)

report={
  "schema_version":1,
  "generated_at":datetime.now(timezone.utc).isoformat(),
  "policy":{"read_only":True,"no_login":True,"no_mutations":True,"no_session_start":True,"same_origin_assets_only":True,"raw_bodies_persisted":False},
  "page_url":BASE,
  "page":{},
  "same_origin_script_assets":[],
  "candidate_public_literals":[],
  "errors":[]
}

try:
    page=fetch(BASE)
    report["page"]={k:v for k,v in page.items() if k!="text"}
    parser=P(); parser.feed(page["text"])
    scripts=[]
    for src in parser.scripts:
        u=urljoin(BASE,src)
        if same_origin(u) and u not in scripts: scripts.append(u)
    candidates=set(literals(page["text"]))
    for u in scripts[:MAX_ASSETS]:
        rec={"url":u}
        try:
            a=fetch(u)
            rec.update({k:v for k,v in a.items() if k!="text"})
            lits=literals(a["text"])
            rec["candidate_literal_count"]=len(lits)
            candidates.update(lits)
        except Exception as e:
            rec["error"]=type(e).__name__+": "+str(e)[:200]
        report["same_origin_script_assets"].append(rec)
    report["candidate_public_literals"]=sorted(candidates)
except Exception as e:
    report["errors"].append(type(e).__name__+": "+str(e)[:300])

json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
print()
