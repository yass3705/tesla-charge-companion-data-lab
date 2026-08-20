#!/usr/bin/env python3
"""Discover DRIVECO's public QR/web-portal or station-price surface from first-party web assets.

Safety:
- public unauthenticated GET requests only;
- no QR decoding, login, payment submission or charging/session actions;
- raw HTML/JS is not persisted;
- output stores only sanitized URLs and response metadata.
"""
from __future__ import annotations

import argparse, hashlib, html, json, re, ssl, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
PAGES=[
 "https://driveco.com/conducteurs/",
 "https://driveco.com/comment-recharger-borne-de-recharge-driveco/",
 "https://driveco.com/dco001-rechargez-vous-chez-driveco/",
 "https://driveco.com/cgvu/",
]
ALLOWED_ROOT="driveco.com"
REFERENCE_EVSES=["FRSSDE10482P1","FRSSDE10485P1","FRE11E10293P1"]
ABS_RE=re.compile(r"https?://[^\s\"'<>]+",re.I)
SCRIPT_RE=re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']",re.I)
REL_RE=re.compile(r"[\"'](/[^\"'<>\s]{2,220})[\"']")
KEYWORDS=("api","portal","charge","charging","station","evse","connector","qr","price","pricing","tariff","tarif","payment","app")
BLOCK=("login","logout","signin","signup","register","account","user","payment","pay","start","stop","session","token","callback")

def now_iso():return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def clean(url):
 p=urllib.parse.urlsplit(url);return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",""))
def allowed(host):
 h=(host or "").lower().split(":",1)[0];return h==ALLOWED_ROOT or h.endswith("."+ALLOWED_ROOT)
def fetch(url,limit=4_000_000):
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/javascript,application/json,*/*;q=0.8","Cache-Control":"no-cache"},method="GET")
 with urllib.request.urlopen(req,timeout=35,context=ssl.create_default_context()) as r:
  raw=r.read(limit);cs=r.headers.get_content_charset() or "utf-8"
  return {"status":int(getattr(r,"status",200)),"final_url":r.geturl(),"content_type":r.headers.get("Content-Type","").split(";",1)[0].strip().lower(),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"text":raw.decode(cs,errors="replace")}
def meta(url,r):return {"requestedUrl":clean(url),"finalUrl":clean(r["final_url"]),"httpStatus":r["status"],"contentType":r["content_type"],"bytesRead":r["bytes"],"contentSha256":r["sha256"]}
def interesting(s):return any(k in s.lower() for k in KEYWORDS)
def candidates(base,text):
 out=set()
 for raw in ABS_RE.findall(text):
  raw=html.unescape(raw).rstrip("),.;`]")
  try:p=urllib.parse.urlsplit(raw)
  except ValueError:continue
  if p.scheme in ("http","https") and allowed(p.netloc) and interesting(raw):out.add(clean(raw))
 for raw in REL_RE.findall(text):
  raw=html.unescape(raw)
  if not interesting(raw) or any(x in raw for x in ("{","}","${","<",">","\\")):continue
  u=urllib.parse.urljoin(base,raw);p=urllib.parse.urlsplit(u)
  if allowed(p.netloc):out.add(clean(u))
 return out
def scripts(base,text):
 out=[];seen=set()
 for src in SCRIPT_RE.findall(text):
  u=clean(urllib.parse.urljoin(base,html.unescape(src)));p=urllib.parse.urlsplit(u)
  if allowed(p.netloc) and u not in seen:seen.add(u);out.append(u)
 return out[:60]
def kind(u):
 l=u.lower()
 if "api" in l:return "api_candidate"
 if any(x in l for x in ("price","pricing","tariff","tarif")):return "pricing_candidate"
 if any(x in l for x in ("station","evse","connector")):return "station_candidate"
 if any(x in l for x in ("portal","charge","charging","qr","app")):return "portal_candidate"
 return "other_candidate"
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--out",default="out/exact-price/driveco");args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 pages=[];script_meta=[];found=set();errs=[];seen=set()
 for page in PAGES:
  try:r=fetch(page)
  except Exception as e:errs.append({"url":clean(page),"errorType":type(e).__name__,"message":str(e)[:180]});continue
  pages.append(meta(page,r));found.update(candidates(r["final_url"],r["text"]))
  for jsu in scripts(r["final_url"],r["text"]):
   if jsu in seen:continue
   seen.add(jsu)
   try:j=fetch(jsu,6_000_000)
   except Exception as e:errs.append({"url":jsu,"errorType":type(e).__name__,"message":str(e)[:180]});continue
   script_meta.append({"url":jsu,"httpStatus":j["status"],"bytesRead":j["bytes"],"contentSha256":j["sha256"]});found.update(candidates(jsu,j["text"]))
 endpoints=[]
 seeds={clean(x) for x in PAGES}
 for u in sorted(found):
  if u in seeds:continue
  path=urllib.parse.urlsplit(u).path.lower()
  if re.search(r"\.(?:js|css|png|jpe?g|svg|ico|woff2?|ttf|map)$",path):continue
  endpoints.append({"url":u,"kind":kind(u)})
 probes=[]
 for x in endpoints[:50]:
  u=x["url"];low=u.lower()
  if any(b in low for b in BLOCK):continue
  try:r=fetch(u,750_000);probes.append({"url":u,"kind":x["kind"],"httpStatus":r["status"],"finalUrl":clean(r["final_url"]),"contentType":r["content_type"],"bytesRead":r["bytes"],"contentSha256":r["sha256"]})
  except Exception as e:probes.append({"url":u,"kind":x["kind"],"errorType":type(e).__name__,"message":str(e)[:180]})
 viable=[x for x in probes if x.get("httpStatus")==200 and x.get("kind") in ("api_candidate","pricing_candidate","station_candidate","portal_candidate")]
 payload={"schemaVersion":"1.0.0","dataset":"driveco-public-portal-exact-price-discovery","generatedAt":now_iso(),"method":{"authenticated":False,"mobilePackageUsed":False,"qrImageDecoded":False,"paymentSubmitted":False,"chargingSessionStarted":False,"persistRawBodies":False,"httpMethods":["GET"]},"pages":pages,"sameVendorScriptsInspected":len(script_meta),"scripts":script_meta[:60],"knownPublicEvseIdsUsedOnlyAsReference":REFERENCE_EVSES,"candidateEndpoints":endpoints[:120],"probes":probes,"conclusion":{"publicPortalOrApiCandidateFound":bool(endpoints),"publicReadableCandidateConfirmed":bool(viable),"nextStep":"inspect confirmed public candidate with a real public EVSE identifier" if viable else "no public exact-price web endpoint discovered; keep DRIVECO station-specific reference-only tariff"},"errors":errs[-30:]}
 (out/"driveco_public_portal_probe.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (out/"SUMMARY.md").write_text("# DRIVECO public portal discovery\n\n"+f"- Pages checked: **{len(pages)}**\n- Same-vendor scripts inspected: **{len(script_meta)}**\n- Candidate endpoints: **{len(endpoints)}**\n- Readable public candidates: **{len(viable)}**\n- Next step: {payload['conclusion']['nextStep']}\n",encoding="utf-8")
if __name__=="__main__":main()
