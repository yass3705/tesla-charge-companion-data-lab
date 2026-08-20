#!/usr/bin/env python3
"""Use e-Totem's confirmed public station selector to derive public station IDs and probe station detail routes.

Safety:
- GET-only, unauthenticated public endpoints;
- no payment/charging/session/account actions;
- no raw-body persistence;
- only a small allow-listed subset of public station metadata is retained.
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
SELECT_URL="https://www.e-totem.fr/api/SelectsBornes"
DETAIL_TMPL="https://www.e-totem.fr/api/Stations/{origin}/{station_id}"
BLOCK_KEYS=("token","secret","cookie","password","motpasse","email","phone","telephone","user","utilisateur","auth","session","payment","paiement")
KEEP_KEYS=("id","label","text","name","nom","source","origine","station","borne","pdc","evse","commune","ville","address","adresse","code","tarif","tariff","price","prix","puissance","power","status","etat")


def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def clean_url(url):
    p=urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",""))

def fetch(url,limit=1_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/html,*/*;q=0.8","Cache-Control":"no-cache"},method="GET")
    with urllib.request.urlopen(req,timeout=35,context=ssl.create_default_context()) as r:
        raw=r.read(limit); charset=r.headers.get_content_charset() or "utf-8"
        return {"status":int(getattr(r,"status",200)),"final_url":r.geturl(),"content_type":r.headers.get("Content-Type","").split(";",1)[0].strip().lower(),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"text":raw.decode(charset,errors="replace")}

def jload(text):
    try:return json.loads(text)
    except Exception:return None

def allowed_key(k):
    low=str(k).lower()
    return not any(x in low for x in BLOCK_KEYS) and any(x in low for x in KEEP_KEYS)

def sanitize(v,depth=0):
    if depth>4:return None
    if isinstance(v,dict):
        out={}
        for k,val in v.items():
            low=str(k).lower()
            if any(x in low for x in BLOCK_KEYS):continue
            if allowed_key(k) or depth==0 or low in ("aselect2","bsucces","data","results","items"):
                s=sanitize(val,depth+1)
                if s is not None:out[str(k)]=s
        return out
    if isinstance(v,list): return [sanitize(x,depth+1) for x in v[:25]]
    if isinstance(v,(str,int,float,bool)) or v is None:
        if isinstance(v,str): return v[:220]
        return v
    return str(v)[:220]

def shape(v):
    if isinstance(v,dict):return {"type":"object","keys":sorted(map(str,v.keys()))[:80],"keyCount":len(v)}
    if isinstance(v,list):
        out={"type":"array","length":len(v)}
        if v and isinstance(v[0],dict):out["itemKeys"]=sorted(map(str,v[0].keys()))[:80]
        return out
    return {"type":type(v).__name__}

def walk_dicts(v):
    if isinstance(v,dict):
        yield v
        for x in v.values():yield from walk_dicts(x)
    elif isinstance(v,list):
        for x in v:yield from walk_dicts(x)

def get_ci(d,*names):
    m={str(k).lower():v for k,v in d.items()}
    for n in names:
        if n.lower() in m:return m[n.lower()]
    return None

def derive_candidates(data):
    out=[];seen=set()
    for d in walk_dicts(data):
        origin=get_ci(d,"sOrigine","origine","origin","source")
        sid=get_ci(d,"nIdStation","idStation","stationId","id")
        label=get_ci(d,"text","label","nom","name")
        if origin is not None and sid is not None:
            s_origin=str(origin).strip(); s_id=str(sid).strip()
            if s_origin and s_id and len(s_origin)<=40 and len(s_id)<=40:
                key=(s_origin,s_id)
                if key not in seen:
                    seen.add(key);out.append({"origin":s_origin,"stationId":s_id,"label":str(label)[:160] if label is not None else None,"derivedBy":"fields"})
        if isinstance(sid,str):
            m=re.match(r"^([A-Za-z][A-Za-z0-9_-]{0,20})[:|_/-]+(\d{1,12})$",sid.strip())
            if m:
                key=(m.group(1),m.group(2))
                if key not in seen:
                    seen.add(key);out.append({"origin":m.group(1),"stationId":m.group(2),"label":str(label)[:160] if label is not None else None,"derivedBy":"compound_id"})
    return out[:20]

def probe_detail(c):
    url=DETAIL_TMPL.format(origin=urllib.parse.quote(c["origin"],safe=""),station_id=urllib.parse.quote(c["stationId"],safe=""))
    try:r=fetch(url)
    except Exception as exc:return {**c,"url":clean_url(url),"errorType":type(exc).__name__,"message":str(exc)[:180]}
    data=jload(r["text"])
    return {**c,"url":clean_url(url),"finalUrl":clean_url(r["final_url"]),"httpStatus":r["status"],"contentType":r["content_type"],"bytesRead":r["bytes"],"contentSha256":r["sha256"],"jsonShape":shape(data) if data is not None else None,"sanitizedPublicFields":sanitize(data) if data is not None else None}

def contains_price(v):
    if isinstance(v,dict):
        return any(any(x in str(k).lower() for x in ("tarif","tariff","price","prix")) or contains_price(val) for k,val in v.items())
    if isinstance(v,list):return any(contains_price(x) for x in v)
    return False

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",default="out/exact-price-stage3/etotem");args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    sel=fetch(SELECT_URL); data=jload(sel["text"])
    if data is None:raise RuntimeError("SelectsBornes did not return JSON")
    sanitized=sanitize(data); candidates=derive_candidates(data)
    details=[probe_detail(c) for c in candidates[:10]]
    usable=[x for x in details if x.get("httpStatus")==200 and x.get("jsonShape")]
    priced=[x for x in usable if contains_price(x.get("sanitizedPublicFields"))]
    payload={
        "schemaVersion":"1.0.0","dataset":"etotem-public-station-stage3","generatedAt":now_iso(),
        "method":{"authenticated":False,"mobilePackageUsed":False,"paymentSubmitted":False,"chargingSessionStarted":False,"persistRawBodies":False,"httpMethods":["GET"]},
        "selector":{"url":SELECT_URL,"httpStatus":sel["status"],"contentType":sel["content_type"],"bytesRead":sel["bytes"],"contentSha256":sel["sha256"],"jsonShape":shape(data),"sanitizedPublicFields":sanitized},
        "derivedStationCandidates":candidates,
        "detailProbes":details,
        "conclusion":{"publicStationIdDerived":bool(candidates),"publicStationDetailConfirmed":bool(usable),"publicStationPriceFieldConfirmed":bool(priced),"nextStep":"validate exact price fields on 2-3 real stations and integrate station-level tariff mapping" if priced else ("inspect station detail response semantics for tariff route" if usable else "selector does not expose enough public IDs for exact-price automation; keep e-Totem network-level reference")},
    }
    (out/"etotem_public_station_stage3.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"SUMMARY.md").write_text(
        "# e-Totem public station stage 3\n\n"
        f"- Public station candidates derived: **{len(candidates)}**\n"
        f"- Public station detail JSON confirmed: **{len(usable)}**\n"
        f"- Detail responses with price/tariff fields: **{len(priced)}**\n"
        f"- Next step: {payload['conclusion']['nextStep']}\n",encoding="utf-8")
if __name__=="__main__":main()
