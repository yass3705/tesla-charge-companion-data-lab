#!/usr/bin/env python3
"""Focused public discovery on ENGIE Vianeo's official station-map page.

Safety: unauthenticated GET only; no account/payment/session actions; raw bodies are not persisted.
"""
from __future__ import annotations
import hashlib, html, json, re, ssl, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SEEDS=[
 "https://www.engie-vianeo.com/carte-borne-recharge-voiture-electrique/",
 "https://www.engie-vianeo.com/selection/",
 "https://www.engie-vianeo.com/tarifs-recharge-voiture-electrique/",
]
ALLOWED_ROOT="engie-vianeo.com"
REFERENCE_NAMES=["Igny Palaiseau","Lieusaint Carré Sénart","Noisy-le-Grand"]
URL_RE=re.compile(r"https?://[^\s\"'<>]+",re.I)
SCRIPT_RE=re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']",re.I)
IFRAME_RE=re.compile(r"<iframe\b[^>]*\bsrc=[\"']([^\"']+)[\"']",re.I)
REL_RE=re.compile(r"[\"'](/[^\"'<>\s]{2,260})[\"']")
KEYWORDS=("station","borne","charge","map","carte","api","json","evse","connector","tarif","price","pricing","location")
BLOCK=("login","logout","account","user","payment","pay","start","stop","session","token","callback")

def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def clean(url):
 p=urllib.parse.urlsplit(url); return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",""))
def allowed(host):
 h=(host or "").lower().split(":",1)[0]; return h==ALLOWED_ROOT or h.endswith("."+ALLOWED_ROOT)
def fetch(url,limit=5_000_000):
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/javascript,application/json,*/*;q=0.8","Cache-Control":"no-cache"},method="GET")
 with urllib.request.urlopen(req,timeout=35,context=ssl.create_default_context()) as r:
  raw=r.read(limit); cs=r.headers.get_content_charset() or "utf-8"
  return {"status":int(getattr(r,"status",200)),"final":r.geturl(),"ctype":r.headers.get("Content-Type","").split(";",1)[0].strip().lower(),"bytes":len(raw),"sha":hashlib.sha256(raw).hexdigest(),"text":raw.decode(cs,errors="replace")}
def meta(url,r): return {"url":clean(url),"finalUrl":clean(r["final"]),"httpStatus":r["status"],"contentType":r["ctype"],"bytesRead":r["bytes"],"contentSha256":r["sha"]}
def interesting(s): return any(k in s.lower() for k in KEYWORDS)
def candidate_urls(base,text):
 out=set()
 for raw in URL_RE.findall(text):
  raw=html.unescape(raw).rstrip("),.;`]")
  try:p=urllib.parse.urlsplit(raw)
  except ValueError: continue
  if p.scheme in ("http","https") and interesting(raw): out.add(clean(raw))
 for raw in REL_RE.findall(text):
  raw=html.unescape(raw)
  if interesting(raw) and not any(x in raw for x in ("{","}","${","<",">","\\")):
   out.add(clean(urllib.parse.urljoin(base,raw)))
 return out
def script_urls(base,text):
 out=[]; seen=set()
 for src in SCRIPT_RE.findall(text):
  u=clean(urllib.parse.urljoin(base,html.unescape(src)))
  if allowed(urllib.parse.urlsplit(u).netloc) and u not in seen: seen.add(u); out.append(u)
 return out[:80]
def semantic(text):
 low=text.lower(); keys=("station","borne","evse","connector","tarif","price","pricing","latitude","longitude","map","api","json","iframe")
 return [k for k in keys if k in low]
def station_name_hits(text): return [n for n in REFERENCE_NAMES if n.lower() in text.lower()]

def main():
 pages=[]; scripts=[]; discovered=set(); iframe_hosts=set(); refs=[]; errors=[]; seen=set()
 for seed in SEEDS:
  try:r=fetch(seed)
  except Exception as e: errors.append({"url":clean(seed),"errorType":type(e).__name__,"message":str(e)[:180]}); continue
  m=meta(seed,r); m["semanticMarkers"]=semantic(r["text"]); m["referenceStationNameHits"]=station_name_hits(r["text"]); pages.append(m)
  discovered.update(candidate_urls(r["final"],r["text"]))
  for src in IFRAME_RE.findall(r["text"]):
   u=urllib.parse.urljoin(r["final"],html.unescape(src)); p=urllib.parse.urlsplit(u)
   if p.scheme in ("http","https"):
    iframe_hosts.add(p.netloc.lower()); refs.append({"type":"iframe","url":clean(u),"sameVendor":allowed(p.netloc)})
  for jsu in script_urls(r["final"],r["text"]):
   if jsu in seen: continue
   seen.add(jsu)
   try:j=fetch(jsu,6_000_000)
   except Exception as e: errors.append({"url":jsu,"errorType":type(e).__name__,"message":str(e)[:180]}); continue
   scripts.append({"url":jsu,"httpStatus":j["status"],"bytesRead":j["bytes"],"contentSha256":j["sha"],"semanticMarkers":semantic(j["text"]),"referenceStationNameHits":station_name_hits(j["text"])})
   discovered.update(candidate_urls(jsu,j["text"]))

 candidates=[]
 for u in sorted(discovered):
  p=urllib.parse.urlsplit(u); low=u.lower()
  if re.search(r"\.(?:css|png|jpe?g|svg|ico|woff2?|ttf|webp)$",p.path.lower()): continue
  if not interesting(u): continue
  candidates.append({"url":u,"sameVendor":allowed(p.netloc),"host":p.netloc.lower()})

 probes=[]
 for x in [c for c in candidates if c["sameVendor"]][:50]:
  u=x["url"]; low=u.lower()
  if any(b in low for b in BLOCK): continue
  try:r=fetch(u,1_000_000); probes.append({"url":u,"httpStatus":r["status"],"finalUrl":clean(r["final"]),"contentType":r["ctype"],"bytesRead":r["bytes"],"contentSha256":r["sha"],"semanticMarkers":semantic(r["text"]),"referenceStationNameHits":station_name_hits(r["text"])})
  except Exception as e: probes.append({"url":u,"errorType":type(e).__name__,"message":str(e)[:180]})

 public_json=[x for x in probes if x.get("httpStatus")==200 and x.get("contentType")=="application/json"]
 station_hits=[x for x in pages+scripts+probes if x.get("referenceStationNameHits")]
 external=[x for x in candidates if not x["sameVendor"]]
 payload={
  "schemaVersion":"1.0.0","dataset":"vianeo-public-map-stage2","generatedAt":now_iso(),
  "method":{"authenticated":False,"mobilePackageUsed":False,"paymentSubmitted":False,"chargingSessionStarted":False,"persistRawBodies":False,"httpMethods":["GET"]},
  "pages":pages,"sameVendorScriptsInspected":len(scripts),"scripts":scripts[:80],"iframeReferences":refs[:20],
  "candidateEndpoints":candidates[:150],"publicJsonProbes":public_json[:30],"referenceStationEvidenceCount":len(station_hits),
  "externalCandidateHosts":sorted({x["host"] for x in external})[:30],
  "conclusion":{"publicMachineReadableStationDataFound":bool(public_json and station_hits),"publicJsonEndpointFound":bool(public_json),"referenceStationNamesFoundInPublicAssets":bool(station_hits),"nextStep":"inspect confirmed JSON endpoint/linked official map host with real station identifiers" if public_json or station_hits else "no machine-readable exact station data found; keep Vianeo station-specific fees/reference outside ranking"},
  "errors":errors[-30:]}
 out=Path("out/exact-price-stage2/vianeo"); out.mkdir(parents=True,exist_ok=True)
 (out/"vianeo_public_map_stage2.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (out/"SUMMARY.md").write_text("# Vianeo public map stage2\n\n"+f"- Public JSON probes: **{len(public_json)}**\n- Reference-station evidence hits: **{len(station_hits)}**\n- External candidate hosts: **{len(payload['externalCandidateHosts'])}**\n- Next step: {payload['conclusion']['nextStep']}\n",encoding="utf-8")

if __name__=="__main__": main()
