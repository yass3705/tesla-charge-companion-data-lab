#!/usr/bin/env python3
"""Stage 2 public exact-price discovery for Freshmile and Qovoltis.

Safety:
- unauthenticated GET only
- no cookies, credentials, mobile packages or login flows
- raw HTML/JS/API bodies are never persisted
- only sanitized URLs, status codes, content metadata and tiny structural hints are written
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
ATTR_RE = re.compile(r"\b(?:href|action|src)=[\"']([^\"']+)[\"']", re.I)
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
ABS_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
QUOTED_RE = re.compile(r"[\"']([^\"'<>]{2,240})[\"']")
KEYWORDS = ("api","graphql","location","locations","station","stations","evse","connector","tariff","price","pricing","chargepoint","charger")


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_url(url: str) -> str:
    p=urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",""))


def same_vendor(url: str, suffix: str) -> bool:
    h=urllib.parse.urlsplit(url).netloc.lower().split(":",1)[0]
    root=suffix.lstrip('.')
    return h==root or h.endswith(suffix)


def fetch(url: str) -> dict:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/html,application/json,application/javascript,text/javascript;q=0.9,*/*;q=0.8",
        "Accept-Language":"fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control":"no-cache",
    },method="GET")
    ctx=ssl.create_default_context()
    try:
        with urllib.request.urlopen(req,timeout=35,context=ctx) as resp:
            raw=resp.read(2_000_000)
            status=int(getattr(resp,"status",200))
            final=resp.geturl()
            ctype=(resp.headers.get("Content-Type","").split(";",1)[0].strip().lower())
    except urllib.error.HTTPError as exc:
        raw=exc.read(200_000)
        status=int(exc.code)
        final=exc.geturl()
        ctype=(exc.headers.get("Content-Type","").split(";",1)[0].strip().lower()) if exc.headers else ""
    charset="utf-8"
    text=raw.decode(charset,errors="replace")
    return {"status":status,"final":final,"ctype":ctype,"text":text,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def json_shape(text: str):
    try:d=json.loads(text)
    except Exception:return None
    if isinstance(d,dict):
        return {"type":"object","keys":sorted(str(k) for k in d.keys())[:40]}
    if isinstance(d,list):
        first=d[0] if d else None
        return {"type":"array","length":len(d),"firstKeys":sorted(str(k) for k in first.keys())[:30] if isinstance(first,dict) else []}
    return {"type":type(d).__name__}


def meta(url: str, result: dict):
    return {
        "requestedUrl":sanitize_url(url),
        "finalUrl":sanitize_url(result["final"]),
        "httpStatus":result["status"],
        "contentType":result["ctype"],
        "bytesRead":result["bytes"],
        "contentSha256":result["sha256"],
        "jsonShape":json_shape(result["text"]),
    }


def interesting(s: str) -> bool:
    low=s.lower()
    return any(k in low for k in KEYWORDS)


def discover_literals(base: str, text: str, suffix: str):
    out=set()
    for raw in ABS_RE.findall(text):
        raw=html.unescape(raw).rstrip("),.;")
        if interesting(raw) and same_vendor(raw,suffix):out.add(sanitize_url(raw))
    for raw in QUOTED_RE.findall(text):
        raw=html.unescape(raw)
        if not interesting(raw):continue
        if any(x in raw for x in ("{","}","<",">","${","\\")):continue
        absolute=urllib.parse.urljoin(base,raw)
        p=urllib.parse.urlsplit(absolute)
        if p.scheme in ("http","https") and same_vendor(absolute,suffix):out.add(sanitize_url(absolute))
    return out


def freshmile(out: Path):
    seed="https://charge.freshmile.com/"
    page=fetch(seed)
    scripts=[]; literals=set(); probes=[]
    for src in SCRIPT_RE.findall(page["text"]):
        u=sanitize_url(urllib.parse.urljoin(seed,html.unescape(src)))
        if not same_vendor(u,".freshmile.com"):continue
        try:r=fetch(u)
        except Exception:continue
        scripts.append({"url":u,"httpStatus":r["status"],"bytesRead":r["bytes"],"contentSha256":r["sha256"]})
        literals.update(discover_literals(u,r["text"],".freshmile.com"))
    fixed=[
        "https://prod-driver-api.freshmile.com/",
        "https://prod-driver-api.freshmile.com/charge/api/v2",
        "https://prod-driver-api.freshmile.com/charge/api/v2/locations",
        "https://prod-driver-api.freshmile.com/charge/api/v2/stations",
        "https://prod-driver-api.freshmile.com/charge/api/v2/evses",
        "https://prod-driver-api.freshmile.com/charge/api/v2/tariffs",
        "https://prod-driver-api.freshmile.com/charge/api/v2/chargepoints",
        "https://prod-driver-api.freshmile.com/openapi.json",
        "https://prod-driver-api.freshmile.com/swagger.json",
        "https://prod-driver-api.freshmile.com/charge/api/v2/openapi.json",
        "https://prod-driver-api.freshmile.com/charge/api/v2/swagger.json",
    ]
    discovered=[u for u in sorted(literals) if "users" not in u.lower() and "logout" not in u.lower()][:80]
    for u in list(dict.fromkeys(fixed+discovered))[:100]:
        try:probes.append(meta(u,fetch(u)))
        except Exception as exc:probes.append({"requestedUrl":sanitize_url(u),"errorType":type(exc).__name__,"message":str(exc)[:200]})
    candidate=[p for p in probes if p.get("httpStatus") not in (404,405) and (p.get("jsonShape") or p.get("httpStatus") in (200,400,401,403))]
    return {
        "target":"freshmile",
        "seed":meta(seed,page),
        "scripts":scripts,
        "discoveredLiteralCount":len(literals),
        "discoveredLiterals":discovered,
        "probes":probes,
        "candidateProbeCount":len(candidate),
        "candidateProbes":candidate,
        "conclusion":{
            "publicApiSurfaceStillPresent":bool(candidate),
            "nextStep":"inspect candidate route semantics and required public parameters" if candidate else "stop Freshmile public-web path and keep reference-only pricing"
        }
    }


def qovoltis(out: Path):
    seed="https://chargenow.qovoltis.com/"
    page=fetch(seed)
    links=[]; probes=[]
    for raw in ATTR_RE.findall(page["text"]):
        absolute=sanitize_url(urllib.parse.urljoin(seed,html.unescape(raw)))
        p=urllib.parse.urlsplit(absolute)
        if p.scheme not in ("http","https"):continue
        links.append({"url":absolute,"sameVendor":same_vendor(absolute,".qovoltis.com")})
    unique=[];seen=set()
    for x in links:
        if x["url"] in seen:continue
        seen.add(x["url"]);unique.append(x)
    for x in unique:
        u=x["url"]
        if not x["sameVendor"]:continue
        if re.search(r"\.(?:png|jpe?g|svg|ico|css|js|woff2?)$",urllib.parse.urlsplit(u).path,re.I):continue
        try:probes.append(meta(u,fetch(u)))
        except Exception as exc:probes.append({"requestedUrl":u,"errorType":type(exc).__name__,"message":str(exc)[:200]})
    interesting_links=[x for x in unique if any(k in x["url"].lower() for k in ("charge","pay","payment","card","cb","guest","station","borne","start"))]
    return {
        "target":"qovoltis",
        "seed":meta(seed,page),
        "linksAndActions":unique[:100],
        "interestingLinks":interesting_links[:60],
        "probes":probes[:60],
        "conclusion":{
            "publicCardFlowRouteDiscovered":bool(interesting_links),
            "nextStep":"follow same-vendor public card-flow route with read-only GET" if interesting_links else "no machine-readable public route found; keep Qovoltis reference-only for now"
        }
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--target",choices=("freshmile","qovoltis"),required=True);ap.add_argument("--out",required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    payload={
        "schemaVersion":"1.0.0","dataset":f"{args.target}-public-exact-price-stage2","generatedAt":now_iso(),
        "method":{"authenticated":False,"mobilePackageUsed":False,"persistRawBodies":False,"httpMethods":["GET"]},
    }
    payload.update(freshmile(out) if args.target=="freshmile" else qovoltis(out))
    (out/f"{args.target}_stage2.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    c=payload["conclusion"]
    summary=f"# {args.target} exact-price stage 2\n\n- Conclusion: `{json.dumps(c,ensure_ascii=False)}`\n"
    (out/"SUMMARY.md").write_text(summary,encoding="utf-8")
    print(summary)

if __name__=="__main__":main()
