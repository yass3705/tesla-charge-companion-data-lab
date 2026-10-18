#!/usr/bin/env python3
from __future__ import annotations
import gzip,hashlib,html,json,re,time,unicodedata,urllib.error,urllib.parse,urllib.request,xml.etree.ElementTree as ET,zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SITEMAPS=("https://www.fastnedcharging.com/sitemap.xml","https://www.fastnedcharging.com/sitemap-index.xml","https://www.fastnedcharging.com/sitemap_index.xml")
PREFIX="/en/locations/"
TARIFF_URL="https://www.fastnedcharging.com/en-gb/charging/tariffs"
OUT=Path("data/national/fastned_direct_stations_uk.json.gz")

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def norm(s):
 s=unicodedata.normalize("NFKD",s); s="".join(c for c in s if not unicodedata.combining(c)); s=s.lower().replace("’","'")
 return re.sub(r"\s+"," ",s).strip()
def dec(s): return float(s.replace(",","."))
def fetch(url,tries=4):
 last=None
 for i in range(tries):
  try:
   q=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"en-GB,en;q=0.9","Accept-Encoding":"gzip, deflate","Cache-Control":"no-cache"})
   with urllib.request.urlopen(q,timeout=40) as r:
    raw=r.read(); enc=(r.headers.get("Content-Encoding") or "").lower()
    if enc=="gzip" or raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
    elif enc=="deflate": raw=zlib.decompress(raw)
    return raw.decode(r.headers.get_content_charset() or "utf-8","replace")
  except Exception as e:
   last=e
   if i+1<tries: time.sleep(.8*(2**i))
 raise RuntimeError(f"GET failed {url}: {last}")
def text_html(s):
 s=re.sub(r"<script\b[^>]*>.*?</script>"," ",s,flags=re.I|re.S); s=re.sub(r"<style\b[^>]*>.*?</style>"," ",s,flags=re.I|re.S)
 return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",s))).strip()
def first(p,s,flags=re.I|re.S):
 m=re.search(p,s,flags); return m.group(1).strip() if m else None
def xml_locs(x):
 root=ET.fromstring(x); kind=root.tag.rsplit("}",1)[-1].lower(); locs=[]
 for e in root.iter():
  if e.tag.rsplit("}",1)[-1].lower()=="loc" and e.text: locs.append(e.text.strip())
 return kind,locs
def canonical(u):
 p=urllib.parse.urlparse(u); path=p.path.rstrip("/")
 if p.netloc.lower() not in ("www.fastnedcharging.com","fastnedcharging.com") or not path.startswith(PREFIX) or path==PREFIX.rstrip("/"): return None
 return urllib.parse.urlunparse(("https","www.fastnedcharging.com",path,"","",""))
def discover():
 root=None; initial=None; errs=[]
 for u in SITEMAPS:
  try: initial=fetch(u); xml_locs(initial); root=u; break
  except Exception as e: errs.append(str(e))
 if not root: raise RuntimeError("no sitemap: "+" | ".join(errs))
 q=[(root,initial)]; seen=set(); pages=set(); n=0
 while q:
  u,cached=q.pop(0)
  if u in seen: continue
  seen.add(u); kind,locs=xml_locs(cached if cached is not None else fetch(u)); n+=1
  if n>100: raise RuntimeError("sitemap guard")
  if kind=="sitemapindex":
   q += [(v,None) for v in locs if v not in seen]
  else:
   for v in locs:
    z=canonical(v)
    if z: pages.add(z)
 if len(pages)<300: raise RuntimeError(f"location page inventory too small {len(pages)}")
 return root,sorted(pages),n
def tariff():
 t=norm(text_html(fetch(TARIFF_URL)))
 sm=re.search(r"£\s*(\d+(?:[.,]\d+)?)\s*in the united kingdom",t)
 gm=re.search(r"£\s*(\d+(?:[.,]\d+)?)\s*\(£\s*\1\s*per kwh in the united kingdom\)",t)
 if not sm or not gm: raise RuntimeError("UK tariff not found")
 std=dec(sm.group(1)); gold=dec(gm.group(1))
 if "get 10% off" not in t and "get 10 % off" not in t: raise RuntimeError("10% app rule missing")
 if "save 30%" not in t and "save 30 %" not in t: raise RuntimeError("30% gold rule missing")
 fm=re.search(r"£\s*(\d+(?:[.,]\d+)?)\s*per month until\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})",t)
 months={"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
 fee=end=None
 if fm and fm.group(3) in months:
  fee=dec(fm.group(1)); end=f"{int(fm.group(4)):04d}-{months[fm.group(3)]:02d}-{int(fm.group(2)):02d}"
 return {"standardGbpPerKwh":std,"appDiscountPercent":10.0,"appGbpPerKwh":round(std*.9,3),"goldGbpPerKwh":gold,"goldDiscountPercent":30.0,"goldMonthlyFeeGbp":fee,"goldMonthlyFeePromotionEnd":end}
def coords(raw):
 d=urllib.parse.unquote(html.unescape(raw)); m=re.search(r"[?&]destination=([-+]?\d{1,2}(?:\.\d+)?),([-+]?\d{1,3}(?:\.\d+)?)",d,re.I)
 if not m:return None
 lat,lon=map(float,m.groups())
 if 49.5<=lat<=61.2 and -8.8<=lon<=2.2:return lat,lon
 return None
def parse(url,raw,t):
 tx=text_html(raw); n=norm(tx)
 addr=first(r"\bAddress\s+(.*?)\s+Opening times\b",tx)
 if not addr or not re.search(r"(?:,\s*|\b)(?:United Kingdom|Great Britain)\b",addr,re.I): return None
 title=first(r"<h1\b[^>]*>(.*?)</h1>",raw)
 title=text_html(title or "")
 if not title:return None
 c=coords(raw)
 if not c: raise ValueError(f"no coords {url}")
 pm=re.search(r"(?:gbp|£)\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh.{0,260}?standard rate\s*:\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh",n)
 if not pm:
  pm=re.search(r"starting from\s+(?:gbp|£)\s*(\d+(?:[.,]\d+)?)\s*/?kwh.{0,260}?standard rate\s*:\s*(\d+(?:[.,]\d+)?)\s*/?kwh",n)
 if not pm: raise ValueError(f"no station price {url}")
 gold,std=dec(pm.group(1)),dec(pm.group(2))
 if abs(std-t["standardGbpPerKwh"])>.001 or abs(gold-t["goldGbpPerKwh"])>.001: raise ValueError(f"tariff mismatch {url}: {std}/{gold}")
 m=re.search(r"number of charging spots\s+(\d+)",n) or re.search(r"chargers\s+(\d+)\s+charging spots",n)
 if not m: raise ValueError(f"no spot count {url}")
 spots=int(m.group(1))
 if spots==0:return None
 pw=re.search(r"maximum power\s+up to\s*(\d{2,4})\s*kw",n)
 if not pw: raise ValueError(f"no power {url}")
 con=first(r"Type of Connectors\s+(.*?)\s+Maximum power",tx)
 types=[]
 for v in (con or "").split(","):
  v=v.strip().upper()
  if v and v not in types:types.append(v)
 if not types: raise ValueError(f"no connector types {url}")
 slug=urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]; lat,lon=c
 return {"stationId":"fastned:"+slug,"slug":slug,"name":title,"address":addr,"country":"GB","latitude":lat,"longitude":lon,"chargingPoints":spots,"maxPowerKw":int(pw.group(1)),"connectorTypes":types,"stationPageUrl":url,"stationStandardGbpPerKwh":std,"stationGoldGbpPerKwh":gold,"tariffProfileIds":["fastned-app-direct","fastned-standard","fastned-gold"]}
def main():
 t=tariff(); sitemap,pages,sc=discover(); loc=[]; errors=[]
 with ThreadPoolExecutor(max_workers=18) as pool:
  fs={pool.submit(fetch,u):u for u in pages}
  for f in as_completed(fs):
   u=fs[f]
   try:
    x=parse(u,f.result(),t)
    if x:loc.append(x)
   except Exception as e:
    # Only UK pages can legitimately be parsing candidates; preserve errors and fail if any.
    raw=None
    try: raw=f.result()
    except: pass
    if raw:
     tx=text_html(raw); addr=first(r"\bAddress\s+(.*?)\s+Opening times\b",tx)
     if addr and re.search(r"(?:United Kingdom|Great Britain)",addr,re.I): errors.append({"url":u,"error":str(e)})
 if errors: raise RuntimeError("UK page parse failures: "+json.dumps(errors[:20]))
 loc=sorted(loc,key=lambda x:(x["name"].lower(),x["stationId"]))
 if len(loc)<10: raise RuntimeError(f"UK station count unexpectedly small: {len(loc)}")
 if len({x["stationId"] for x in loc})!=len(loc): raise RuntimeError("duplicate ids")
 profiles=[
  {"id":"fastned-app-direct","subscriptionRequired":False,"pricePerKwhGbp":t["appGbpPerKwh"],"discountPercent":10.0,"monthlyFeeGbp":0.0},
  {"id":"fastned-standard","subscriptionRequired":False,"pricePerKwhGbp":t["standardGbpPerKwh"],"monthlyFeeGbp":0.0},
  {"id":"fastned-gold","subscriptionRequired":True,"subscriptionId":"fastned-gold","pricePerKwhGbp":t["goldGbpPerKwh"],"discountPercent":30.0,"monthlyFeeGbp":t["goldMonthlyFeeGbp"],"monthlyFeePromotionEnd":t["goldMonthlyFeePromotionEnd"]}
 ]
 fingerprint=hashlib.sha256(json.dumps({"tariff":t,"locations":loc},sort_keys=True,separators=(",",":")).encode()).hexdigest()
 out={"schemaVersion":"1.0.0","dataset":"fastned-direct-operated-stations-uk","generatedAt":now(),"operator":"Fastned","country":"GB","scope":{"officialFastnedLocationPagesOnly":True,"onlyFastnedCpoLocations":True,"partnerOperatorLocationsIncluded":False,"liveStatusIncluded":False,"nationalTariff":True,"freeAppDiscountIncluded":True,"subscriptionTariffIncluded":True,"roamingTariffsIncluded":False},"pricingProfiles":profiles,"counts":{"sitemapCount":sc,"candidateLocationPageCount":len(pages),"ukLocationCount":len(loc),"ukChargingPointCount":sum(x["chargingPoints"] for x in loc),"maxPowerCounts":dict(sorted(Counter(str(x["maxPowerKw"]) for x in loc).items(),key=lambda kv:int(kv[0])))},"source":{"sitemapUrl":sitemap,"locationPathPrefix":PREFIX,"tariffUrl":TARIFF_URL,"fingerprintSha256":fingerprint},"locations":loc}
 OUT.parent.mkdir(parents=True,exist_ok=True); rendered=json.dumps(out,ensure_ascii=False,indent=2)+"\n"; OUT.write_bytes(gzip.compress(rendered.encode(),compresslevel=9,mtime=0))
 Path("reports/uk").mkdir(parents=True,exist_ok=True)
 Path("reports/uk/fastned-direct-uk-latest.json").write_text(json.dumps({"generatedAt":out["generatedAt"],"counts":out["counts"],"pricingProfiles":profiles,"status":"complete"},indent=2)+"\n")
 print(json.dumps({"counts":out["counts"],"pricingProfiles":profiles},indent=2))
if __name__=="__main__": main()
