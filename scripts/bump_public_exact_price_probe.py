#!/usr/bin/env python3
"""Probe Bump public web surfaces for unauthenticated station/tariff endpoints.

Safety:
- public GET requests only
- no account/login, cookies, credentials or mobile packages
- no charging/payment actions
- raw HTML/JS is not persisted; only sanitized metadata and URL paths are stored
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
PAGES = [
    "https://www.bump-charge.com/recharger",
    "https://help.bump-charge.com/en/articles/9811842",
    "https://help.bump-charge.com/en/articles/4104770",
    "https://help.bump-charge.com/en/articles/9052866",
]
ALLOWED_SUFFIX = ".bump-charge.com"
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
ABS_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
REL_RE = re.compile(r"[\"'](/[^\"'<>\s]{2,260})[\"']")
KEYWORDS = (
    "api", "graphql", "station", "stations", "evse", "connector", "chargepoint",
    "tariff", "tariffs", "price", "pricing", "map", "location", "availability",
)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed(host: str) -> bool:
    host=(host or "").lower().split(":",1)[0]
    root=ALLOWED_SUFFIX.lstrip(".")
    return host==root or host.endswith(ALLOWED_SUFFIX)


def clean_url(url: str) -> str:
    p=urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",""))


def fetch(url: str) -> dict:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/html,application/javascript,text/javascript,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language":"fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control":"no-cache",
    },method="GET")
    with urllib.request.urlopen(req,timeout=35,context=ssl.create_default_context()) as resp:
        raw=resp.read(5_000_000)
        charset=resp.headers.get_content_charset() or "utf-8"
        return {
            "status":int(getattr(resp,"status",200)),
            "final_url":resp.geturl(),
            "content_type":resp.headers.get("Content-Type","").split(";",1)[0].strip().lower(),
            "text":raw.decode(charset,errors="replace"),
            "bytes":len(raw),
            "sha256":hashlib.sha256(raw).hexdigest(),
        }


def interesting(s: str) -> bool:
    low=s.lower()
    return any(k in low for k in KEYWORDS)


def candidates(base: str, text: str) -> set[str]:
    out=set()
    for raw in ABS_RE.findall(text):
        raw=html.unescape(raw).rstrip("),.;")
        try:p=urllib.parse.urlsplit(raw)
        except ValueError:continue
        if p.scheme in ("http","https") and allowed(p.netloc) and interesting(raw):
            out.add(clean_url(raw))
    for raw in REL_RE.findall(text):
        if not interesting(raw) or any(x in raw for x in ("{","}","<",">","${","\\")):
            continue
        absolute=urllib.parse.urljoin(base,html.unescape(raw))
        p=urllib.parse.urlsplit(absolute)
        if allowed(p.netloc):out.add(clean_url(absolute))
    return out


def classify(url: str) -> str:
    low=url.lower()
    if "graphql" in low:return "graphql_candidate"
    if "tariff" in low or "price" in low:return "pricing_candidate"
    if "evse" in low or "connector" in low or "chargepoint" in low:return "evse_candidate"
    if "station" in low or "location" in low or "map" in low:return "station_candidate"
    return "api_candidate"


def main():
    pages=[]; scripts_seen=set(); found=set(); errors=[]; semantic=[]
    for url in PAGES:
        try:r=fetch(url)
        except Exception as exc:
            errors.append({"url":clean_url(url),"errorType":type(exc).__name__,"message":str(exc)[:180]});continue
        pages.append({
            "requestedUrl":clean_url(url),"finalUrl":clean_url(r["final_url"]),
            "httpStatus":r["status"],"contentType":r["content_type"],
            "bytesRead":r["bytes"],"contentSha256":r["sha256"],
        })
        found.update(candidates(r["final_url"],r["text"]))
        low=r["text"].lower()
        for marker in ("voir le tarif","tarifs des bornes","map interactive","qr code","application bump"):
            if marker in low: semantic.append(marker)
        for src in SCRIPT_RE.findall(r["text"]):
            absolute=urllib.parse.urljoin(r["final_url"],html.unescape(src))
            p=urllib.parse.urlsplit(absolute)
            if not allowed(p.netloc):continue
            u=clean_url(absolute)
            if u in scripts_seen:continue
            scripts_seen.add(u)
            try:js=fetch(u)
            except Exception as exc:
                errors.append({"url":u,"errorType":type(exc).__name__,"message":str(exc)[:180]});continue
            found.update(candidates(u,js["text"]))

    seed={clean_url(x) for x in PAGES}
    clean=[]
    for url in sorted(found):
        if url in seed:continue
        path=urllib.parse.urlsplit(url).path.lower()
        if re.search(r"\.(?:js|css|png|jpe?g|svg|ico|woff2?|ttf|map)$",path):continue
        clean.append({"url":url,"kind":classify(url)})

    machine=[x for x in clean if x["kind"] in {"graphql_candidate","pricing_candidate","evse_candidate","station_candidate","api_candidate"}]
    payload={
        "schemaVersion":"1.0.0",
        "dataset":"bump-public-exact-price-discovery",
        "generatedAt":now_iso(),
        "method":{
            "authenticated":False,"mobilePackageUsed":False,"paymentSubmitted":False,
            "chargingSessionStarted":False,"persistRawBodies":False,"httpMethods":["GET"],
        },
        "pages":pages,
        "sameVendorScriptsInspected":len(scripts_seen),
        "candidateEndpoints":clean[:120],
        "candidateEndpointCount":len(clean),
        "semanticMarkers":sorted(set(semantic)),
        "conclusion":{
            "publicMachineReadableExactPriceCandidateFound":bool(machine),
            "nextStep":"probe concrete public candidate routes with station identifiers" if machine else "stop Bump public-web exact-price discovery; exact tariff remains app/station specific",
        },
        "errors":errors[-30:],
    }
    out=Path("out/exact-price/bump");out.mkdir(parents=True,exist_ok=True)
    (out/"bump_public_exact_price_probe.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary=(
        "# Bump public exact-price discovery\n\n"
        f"- Pages checked: **{len(pages)}**\n"
        f"- Same-vendor scripts inspected: **{len(scripts_seen)}**\n"
        f"- Candidate endpoints: **{len(clean)}**\n"
        f"- Public machine-readable exact-price candidate: **{'yes' if machine else 'no'}**\n"
        f"- Next step: {payload['conclusion']['nextStep']}\n"
    )
    (out/"SUMMARY.md").write_text(summary,encoding="utf-8")
    print(summary)

if __name__=="__main__":main()
