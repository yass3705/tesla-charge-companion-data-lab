#!/usr/bin/env python3
"""Discover TotalEnergies / Charge+ public station-price surfaces.

Safety: unauthenticated public GET requests only; no login, payment, QR decode or charging/session actions.
Raw bodies are never persisted.
"""
from __future__ import annotations
import hashlib, html, json, re, ssl, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SEEDS=[
 "https://chargeplus.totalenergies.com/fr/map/",
 "https://chargeplus.totalenergies.com/fr/point-recharges-totalenergies-avec-remises/",
 "https://chargeplus.totalenergies.com/fr/rechargez-votre-vehicule-electrique-partout-en-france-avec-charge-de-totalenergies/",
 "https://services.totalenergies.fr/particuliers/energies-vehicules/electrique-rechargeable/pourquoi-choisir-electrique-totalenergies",
]
ALLOWED_ROOTS=("chargeplus.totalenergies.com","services.totalenergies.fr")
URL_RE=re.compile(r"https?://[^\s\"'<>]+",re.I)
SCRIPT_RE=re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']",re.I)
IFRAME_RE=re.compile(r"<iframe\b[^>]*\bsrc=[\"']([^\"']+)[\"']",re.I)
REL_RE=re.compile(r"[\"'](/[^\"'<>\s]{2,260})[\"']")
EVSE_RE=re.compile(r"\bFR\*[A-Z0-9]{2,}\*[A-Z0-9*]{5,}\b",re.I)
KEYWORDS=("map","carte","station","borne","charge","evse","connector","api","json","tarif","price","pricing","recharge")
BLOCK=("login","logout","signin","signup","register","account","user","payment","pay","start","stop","session","token","callback","checkout")

def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def clean(url):
 p=urllib.parse.urlsplit(url); return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",""))
def allowed(host):
 h=(host or "").lower().split(":",1)[0]; return any(h==r or h.endswith("."+r) for r in ALLOWED_ROOTS)
def fetch(url,limit=6_000_000):
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/javascript,application/json,*/*;q=0.8","Cache-Control":"no-cache"},method="GET")
 with urllib.request.urlopen(req,timeout=35,context=ssl.create_default_context()) as r:
  raw=r.read(limit); cs=r.headers.get_content_charset() or "utf-8"
  return {"status":int(getattr(r,"status",200)),"final":r.geturl(),"ctype":r.headers.get("Content-Type","").split(";",1)[0].strip().lower(),"bytes":len(raw),"sha":hashlib.sha256(raw).hexdigest(),"text":raw.decode(cs,errors="replace")}
def meta(url,r): return {"url":clean(url),"finalUrl":clean(r["final"]),"httpStatus":r["status"],"contentType":r["ctype"],"bytesRead":r["bytes"],"contentSha256":r["sha"]}
def semantic(text):
 low=text.lower(); return [k for k in ("station","borne","evse","connector","tarif","price","pricing","map","api","json","iframe") if k in low]
def evses(text): return sorted(set(x.upper() for x in EVSE_RE.findall(text)))[:100]
def price_hints(text):
 out=[]
 for m in re.findall(r"(?i)(?:tarif|price|prix)[^\n]{0,100}?\b(0[\.,]\d{2,3}|\d{1,2}[\.,]\d{2})\b",text):
  v=m.replace(",",".")
  if v not in out: out.append(v)
 return out[:30]
def interesting(s): return any(k in s.lower() for k in KEYWORDS)
def discover(base,text):
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
def scripts(base,text):
 out=[]; seen=set()
 for src in SCRIPT_RE.findall(text):
  u=clean(urllib.parse.urljoin(base,html.unescape(src)))
  if allowed(urllib.parse.urlsplit(u).netloc) and u not in seen: seen.add(u); out.append(u)
 return out[:80]

def main():
 pages=[]; script_meta=[]; found=set(); iframe_refs=[]; seen=set(); errors=[]; all_evses=set(); all_prices=[]
 for seed in SEEDS:
  try:r=fetch(seed)
  except Exception as e: errors.append({"url":clean(seed),"errorType":type(e).__name__,"message":str(e)[:180]}); continue
  m=meta(seed,r); m["semanticMarkers"]=semantic(r["text"]); m["evseIdHits"]=evses(r["text"]); m["numericPriceHints"]=price_hints(r["text"]); pages.append(m)
  all_evses.update(m["evseIdHits"]); all_prices.extend(x for x in m["numericPriceHints"] if x not in all_prices); found.update(discover(r["final"],r["text"]))
  for src in IFRAME_RE.findall(r["text"]):
   u=urllib.parse.urljoin(r["final"],html.unescape(src)); p=urllib.parse.urlsplit(u)
   if p.scheme in ("http","https"): iframe_refs.append({"url":clean(u),"host":p.netloc.lower(),"sameVendor":allowed(p.netloc)})
  for jsu in scripts(r["final"],r["text"]):
   if jsu in seen: continue
   seen.add(jsu)
   try:j=fetch(jsu,8_000_000)
   except Exception as e: errors.append({"url":jsu,"errorType":type(e).__name__,"message":str(e)[:180]}); continue
   sm={"url":jsu,"httpStatus":j["status"],"bytesRead":j["bytes"],"contentSha256":j["sha"],"semanticMarkers":semantic(j["text"]),"evseIdHits":evses(j["text"]),"numericPriceHints":price_hints(j["text"])}
   script_meta.append(sm); all_evses.update(sm["evseIdHits"]); all_prices.extend(x for x in sm["numericPriceHints"] if x not in all_prices); found.update(discover(jsu,j["text"]))

 candidates=[]
 for u in sorted(found):
  p=urllib.parse.urlsplit(u)
  if re.search(r"\.(?:css|png|jpe?g|svg|ico|woff2?|ttf|webp)$",p.path.lower()): continue
  candidates.append({"url":u,"host":p.netloc.lower(),"sameVendor":allowed(p.netloc)})
 probes=[]
 for x in [c for c in candidates if c["sameVendor"]][:60]:
  u=x["url"]; low=u.lower()
  if any(b in low for b in BLOCK): continue
  try:r=fetch(u,1_200_000); probes.append({"url":u,"httpStatus":r["status"],"finalUrl":clean(r["final"]),"contentType":r["ctype"],"bytesRead":r["bytes"],"contentSha256":r["sha"],"semanticMarkers":semantic(r["text"]),"evseIdHits":evses(r["text"]),"numericPriceHints":price_hints(r["text"])})
  except Exception as e: probes.append({"url":u,"errorType":type(e).__name__,"message":str(e)[:180]})
 public_json=[x for x in probes if x.get("httpStatus")==200 and x.get("contentType")=="application/json"]
 exact_candidates=[x for x in probes if x.get("evseIdHits") and x.get("numericPriceHints")]
 payload={
  "schemaVersion":"1.0.0","dataset":"totalenergies-public-map-exact-price-discovery","generatedAt":now_iso(),
  "method":{"authenticated":False,"mobilePackageUsed":False,"qrImageDecoded":False,"paymentSubmitted":False,"chargingSessionStarted":False,"persistRawBodies":False,"httpMethods":["GET"]},
  "pages":pages,"sameVendorScriptsInspected":len(script_meta),"scripts":script_meta[:80],"iframeReferences":iframe_refs[:30],
  "publicEvseIdsObserved":sorted(all_evses)[:100],"numericPriceHintsObserved":all_prices[:30],"candidateEndpoints":candidates[:150],"probes":probes,"publicJsonProbes":public_json[:30],
  "conclusion":{"publicMapConfirmed":any("/fr/map" in p["url"] and p["httpStatus"]==200 for p in pages),"publicEvseIdsFound":bool(all_evses),"publicJsonEndpointFound":bool(public_json),"stationPriceCandidateFound":bool(exact_candidates),"nextStep":"inspect exact EVSE/price candidate semantics before TCC integration" if exact_candidates else "no exact station price pair confirmed from public Charge+ web assets; keep TotalEnergies station-specific reference outside ranking"},
  "errors":errors[-30:]}
 out=Path("out/exact-price/totalenergies"); out.mkdir(parents=True,exist_ok=True)
 (out/"totalenergies_public_map_probe.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (out/"SUMMARY.md").write_text("# TotalEnergies / Charge+ public exact-price discovery\n\n"+f"- Public EVSE IDs observed: **{len(all_evses)}**\n- First-party scripts inspected: **{len(script_meta)}**\n- Public JSON probes: **{len(public_json)}**\n- Exact EVSE+price candidates: **{len(exact_candidates)}**\n- Next step: {payload['conclusion']['nextStep']}\n",encoding="utf-8")

if __name__=="__main__": main()
