#!/usr/bin/env python3
import json,re,urllib.request,html,hashlib
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(".")
REPORT=ROOT/"reports"/"fixed-tariff-refresh-france-watch-latest.json"
UA="TeslaChargeCompanion/9 fixed-tariff-fr-watch"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*"})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read().decode("utf-8","ignore")
    txt=re.sub(r"<script[^>]*>.*?</script>"," ",raw,flags=re.I|re.S)
    txt=re.sub(r"<style[^>]*>.*?</style>"," ",txt,flags=re.I|re.S)
    txt=re.sub(r"<[^>]+>"," ",txt)
    txt=html.unescape(txt).replace("\xa0"," ")
    return re.sub(r"\s+"," ",txt).strip()

def h(s): return hashlib.sha256(re.sub(r"\s+"," ",s.lower()).strip().encode()).hexdigest()
def find_price(text,pattern,label):
    vals=sorted(set(float(x.replace(",",".")) for x in re.findall(pattern,text,re.I|re.S)))
    if len(vals)!=1: raise ValueError(f"{label}: {vals}")
    return vals[0]

now=datetime.now(timezone.utc).isoformat()
results=[]

# Dream Energy exact refresh
try:
    path=ROOT/"data/operator_direct/dream_energy_promotional_tariff_france_2026.json"
    d=json.loads(path.read_text())
    t=fetch("https://www.dream-energy.fr/support-faq/")
    price=find_price(t,r"recharge\s+co[uû]te\s+([0-9]+[,.][0-9]+)\s*€\s*/?\s*kWh","dream")
    old=d["directTariff"]["eurPerKwh"]
    d["directTariff"]["eurPerKwh"]=price
    d["directTariff"]["source"]="https://www.dream-energy.fr/support-faq/"
    d["refresh"]={"mode":"automatic_official_page_parser","refreshedAt":now,"lastResult":"changed" if old!=price else "unchanged"}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"Dream Energy","status":"changed" if old!=price else "unchanged","eurPerKwh":price})
except Exception as e:
    results.append({"operator":"Dream Energy","status":"failed_keep_last_valid","error":str(e)})

# Sorégies semantic watch
for operator,path,url,terms in [
  ("Sorégies Mobilités","data/operator_direct/soregies_tariff_rules_france_2026.json","https://www.soregies.fr/offre-mobilite-electrique/",["Sorégies Mobilités","0,22€/kWh","0,27€/kWh"]),
  ("Mobive","data/operator_direct/mobive_official_france.json","https://mobive.fr/nos-offres-et-tarifs/",["Mobive","abonné","non abonné"])
]:
    try:
        p=ROOT/path; d=json.loads(p.read_text()); t=fetch(url)
        low=t.lower()
        positions=[low.find(x.lower()) for x in terms if low.find(x.lower())>=0]
        if not positions: raise ValueError("tariff context not found")
        pos=min(positions); ctx=t[max(0,pos-1200):pos+2500]
        sig=h(ctx)
        prev=(d.get("refresh") or {}).get("semanticTariffContextSha256")
        state="baseline_established" if not prev else ("source_context_changed_review_required" if prev!=sig else "unchanged")
        d["refresh"]={"mode":"official_source_semantic_watch_keep_last_valid","source":url,"refreshedAt":now,"semanticTariffContextSha256":sig,"lastResult":state}
        p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
        results.append({"operator":operator,"status":state})
    except Exception as e:
        results.append({"operator":operator,"status":"failed_keep_last_valid","error":str(e)})

REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2))
if any(r["status"]=="failed_keep_last_valid" for r in results): raise SystemExit(2)
