#!/usr/bin/env python3
import hashlib,json,re,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser

AUDIT=Path("reports/fixed-tariff-refresh-audit.json")
OUT=Path("reports/fixed-tariff-source-watch.json")
UA="TeslaChargeCompanion/9 fixed-tariff-watch"

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,t,a):
        if t in ("script","style","noscript"): self.skip+=1
    def handle_endtag(self,t):
        if t in ("script","style","noscript") and self.skip: self.skip-=1
    def handle_data(self,d):
        if not self.skip and d.strip(): self.parts.append(d.strip())

def canon_text(body,ctype):
    if "html" not in ctype.lower(): return None
    try:
        p=Text(); p.feed(body.decode("utf-8","ignore"))
        s=" ".join(p.parts)
        s=re.sub(r"\s+"," ",s).strip()
        return s
    except Exception:
        return None

audit=json.loads(AUDIT.read_text())
previous={}
if OUT.exists():
    try:
        old=json.loads(OUT.read_text())
        previous={x["url"]:x for x in old.get("sources",[])}
    except Exception: pass

url_to_files={}
for row in audit.get("unmanaged",[]):
    for u in row.get("sourceUrlSamples",[]):
        url_to_files.setdefault(u,set()).add(row["path"])

sources=[]
now=datetime.now(timezone.utc).isoformat()
for url,files in sorted(url_to_files.items()):
    item={"url":url,"files":sorted(files),"checkedAt":now}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/pdf,*/*"})
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read(8_000_000)
            status=getattr(r,"status",200)
            ctype=r.headers.get("Content-Type","")
            final=r.geturl()
        raw_hash=hashlib.sha256(body).hexdigest()
        text=canon_text(body,ctype)
        semantic_hash=hashlib.sha256(text.encode()).hexdigest() if text else None
        item.update({
            "httpStatus":status,
            "contentType":ctype,
            "finalUrl":final,
            "bytes":len(body),
            "rawSha256":raw_hash,
            "semanticSha256":semantic_hash,
            "semanticTextSample":text[:500] if text else None
        })
        prev=previous.get(url) or {}
        prev_hash=prev.get("semanticSha256") or prev.get("rawSha256")
        cur_hash=semantic_hash or raw_hash
        item["baselineEstablished"]=bool(prev_hash)
        item["changedSincePrevious"]=bool(prev_hash and prev_hash!=cur_hash)
        item["previousCheckedAt"]=prev.get("checkedAt")
        item["state"]="SOURCE_CHANGED_REVIEW_REQUIRED" if item["changedSincePrevious"] else "ok"
    except Exception as e:
        item.update({
            "httpStatus":None,
            "error":str(e),
            "baselineEstablished":bool(previous.get(url)),
            "changedSincePrevious":False,
            "state":"FETCH_FAILED_KEEP_LAST_VALID_TARIFF"
        })
    sources.append(item)

changed=[x for x in sources if x["state"]=="SOURCE_CHANGED_REVIEW_REQUIRED"]
failed=[x for x in sources if x["state"]=="FETCH_FAILED_KEEP_LAST_VALID_TARIFF"]
out={
    "schemaVersion":1,
    "generatedAt":now,
    "policy":"Never overwrite a validated fixed tariff on source fetch/parser failure. A detected source change requires refresh/revalidation; last validated tariff remains active until replacement is validated.",
    "sourceCount":len(sources),
    "changedCount":len(changed),
    "failedCount":len(failed),
    "sources":sources
}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({
    "sourceCount":len(sources),
    "changedCount":len(changed),
    "failedCount":len(failed),
    "changed":[{"url":x["url"],"files":x["files"]} for x in changed],
    "failed":[{"url":x["url"],"files":x["files"],"error":x.get("error")} for x in failed]
},ensure_ascii=False,indent=2))
