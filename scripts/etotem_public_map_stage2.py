#!/usr/bin/env python3
"""Focused read-only e-Totem public map route probe.

Safety:
- GET-only public first-party endpoints;
- no authentication, cookies, payment or charging actions;
- no raw body persistence;
- only sanitized route templates, response metadata and JSON shapes are stored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
ROUTES_JS="https://www.e-totem.fr/lib/interne/JS/dynamique/Routes.js"
STATIC_PROBES=[
    "https://www.e-totem.fr/public/map/borne-type-prise.json",
    "https://www.e-totem.fr/public/map/etats-borne-legende.json",
    "https://www.e-totem.fr/public/map/filtre-google-map.html",
    "https://www.e-totem.fr/public/map/legende-google-map.html",
    "https://www.e-totem.fr/api/Stations",
    "https://www.e-totem.fr/api/Stations/",
    "https://www.e-totem.fr/api/Stations/Favoris",
]
ROUTE_RE=re.compile(r"[\"'](/(?:api|public)/[^\"'<>\s]{1,220})[\"']",re.I)
PLACEHOLDER_RE=re.compile(r"\[(?:n|s|b)[A-Za-z0-9_]+\]")
SENSITIVE_SEGMENTS=("login","logout","auth","motpasse","password","paiement","payment","payzen","callback","start","stop","arretcharge","reservation","charges/")


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")


def clean_url(url):
    p=urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",""))


def fetch(url,limit=2_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/html,application/javascript,*/*;q=0.8","Cache-Control":"no-cache"},method="GET")
    with urllib.request.urlopen(req,timeout=35,context=ssl.create_default_context()) as r:
        raw=r.read(limit)
        charset=r.headers.get_content_charset() or "utf-8"
        return {
            "status":int(getattr(r,"status",200)),
            "final_url":r.geturl(),
            "content_type":r.headers.get("Content-Type","").split(";",1)[0].strip().lower(),
            "bytes":len(raw),
            "sha256":hashlib.sha256(raw).hexdigest(),
            "text":raw.decode(charset,errors="replace"),
        }


def json_shape(text):
    try:d=json.loads(text)
    except Exception:return None
    if isinstance(d,dict):
        return {"type":"object","keys":sorted(map(str,d.keys()))[:60],"keyCount":len(d)}
    if isinstance(d,list):
        shape={"type":"array","length":len(d)}
        if d and isinstance(d[0],dict):shape["itemKeys"]=sorted(map(str,d[0].keys()))[:60]
        return shape
    return {"type":type(d).__name__}


def route_templates(js):
    routes=[]
    seen=set()
    for raw in ROUTE_RE.findall(js):
        route=raw.replace("\\/","/")
        if route in seen:continue
        seen.add(route)
        low=route.lower()
        if any(x in low for x in ("station","borne","pdc","map","tarif","prix","price","connector","connecteur")):
            routes.append(route)
    return routes[:200]


def safe_concrete_routes(templates):
    out=[]
    for t in templates:
        low=t.lower()
        if PLACEHOLDER_RE.search(t):continue
        if any(x in low for x in SENSITIVE_SEGMENTS):continue
        if any(x in low for x in ("station","borne","pdc","map","tarif","prix","price")):
            u=clean_url(urllib.parse.urljoin("https://www.e-totem.fr/",t))
            if u not in out:out.append(u)
    return out[:50]


def probe(url):
    try:r=fetch(url,1_000_000)
    except Exception as exc:
        return {"url":clean_url(url),"errorType":type(exc).__name__,"message":str(exc)[:180]}
    return {
        "url":clean_url(url),"finalUrl":clean_url(r["final_url"]),"httpStatus":r["status"],
        "contentType":r["content_type"],"bytesRead":r["bytes"],"contentSha256":r["sha256"],
        "jsonShape":json_shape(r["text"]),
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",default="out/exact-price-stage2/etotem");args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    r=fetch(ROUTES_JS,4_000_000)
    templates=route_templates(r["text"])
    concrete=safe_concrete_routes(templates)
    urls=[]
    for u in STATIC_PROBES+concrete:
        if u not in urls:urls.append(u)
    probes=[probe(u) for u in urls]
    json_ok=[x for x in probes if x.get("httpStatus")==200 and x.get("contentType")=="application/json"]
    station_json=[x for x in json_ok if any(k in x["url"].lower() for k in ("station","borne","pdc","map"))]
    payload={
        "schemaVersion":"1.0.0","dataset":"etotem-public-map-stage2","generatedAt":now_iso(),
        "method":{"authenticated":False,"mobilePackageUsed":False,"paymentSubmitted":False,"chargingSessionStarted":False,"persistRawBodies":False,"httpMethods":["GET"]},
        "routesJs":{"url":ROUTES_JS,"httpStatus":r["status"],"bytesRead":r["bytes"],"contentSha256":r["sha256"]},
        "relevantRouteTemplates":templates,
        "concretePublicRouteCount":len(concrete),
        "probes":probes,
        "conclusion":{
            "publicStationJsonConfirmed":bool(station_json),
            "stationJsonEndpoints":[x["url"] for x in station_json],
            "nextStep":"inspect JSON field semantics and identify public station IDs" if station_json else "no station JSON list exposed by concrete public GET routes; retain network-level tariff model",
        },
    }
    (out/"etotem_public_map_stage2.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"SUMMARY.md").write_text(
        "# e-Totem public map stage 2\n\n"
        f"- Relevant route templates: **{len(templates)}**\n"
        f"- Concrete public routes probed: **{len(urls)}**\n"
        f"- JSON 200 responses: **{len(json_ok)}**\n"
        f"- Station/map JSON responses: **{len(station_json)}**\n"
        f"- Next step: {payload['conclusion']['nextStep']}\n",encoding="utf-8")

if __name__=="__main__":main()
