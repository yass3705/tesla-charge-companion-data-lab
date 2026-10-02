#!/usr/bin/env python3
import json,re,urllib.request,html
from pathlib import Path
from datetime import datetime,timezone

UA="TeslaChargeCompanion/9 fixed-tariff-refresh-fr"
ROOT=Path(".")
HIST=ROOT/"data"/"tariff_history"
REPORT=ROOT/"reports"/"fixed-tariff-refresh-france-core-latest.json"
HIST.mkdir(parents=True,exist_ok=True)
REPORT.parent.mkdir(parents=True,exist_ok=True)

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*"})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read().decode("utf-8","ignore")
    txt=re.sub(r"<script[^>]*>.*?</script>"," ",raw,flags=re.I|re.S)
    txt=re.sub(r"<style[^>]*>.*?</style>"," ",txt,flags=re.I|re.S)
    txt=re.sub(r"<[^>]+>"," ",txt)
    txt=html.unescape(txt).replace("\xa0"," ")
    txt=re.sub(r"\s+"," ",txt).strip()
    return txt

def num(s):
    return float(s.replace(",", "."))

def find_one(text,patterns,label):
    vals=[]
    for p in patterns:
        for m in re.finditer(p,text,re.I|re.S):
            try: vals.append(num(m.group(1)))
            except: pass
    vals=sorted(set(round(x,4) for x in vals))
    if len(vals)!=1:
        raise ValueError(f"{label}: expected one value, got {vals}")
    return vals[0]

def sanity(v,lo=0.01,hi=5.0):
    if not (lo<=v<=hi): raise ValueError(f"value out of range: {v}")
    return v

def archive_if_changed(path,before,after,now):
    if before==after: return False
    hist=HIST/(path.stem+".jsonl")
    with hist.open("a",encoding="utf-8") as h:
        h.write(json.dumps({"archivedAt":now,"previous":before},ensure_ascii=False)+"\n")
    return True

now=datetime.now(timezone.utc).isoformat()
results=[]

# Lidl
try:
    url="https://www.lidl.fr/c/tarifs-bornes/s10027299"
    t=fetch(url)
    ac=sanity(find_one(t,[r"AC\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€\s*par\s*kWh",r"AC\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€.*?kWh"],"lidl AC"))
    dc=sanity(find_one(t,[r"DC\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€\s*par\s*kWh",r"DC\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€.*?kWh"],"lidl DC"))
    for rel,mode in [
      ("data/operator_direct/lidl_tariff_rules_france.json","rules"),
      ("data/operator_direct/lidl_official_france.json","official")
    ]:
        p=ROOT/rel; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
        if mode=="rules":
            d["directPayment"]["AC"]["eurPerKwh"]=ac; d["directPayment"]["DC"]["eurPerKwh"]=dc
            d["refresh"]={"mode":"automatic_official_page_parser","source":url,"refreshedAt":now,"lastResult":"validated"}
        else:
            d["operatorDirect"]["standard"]["AC"]["eurPerKwh"]=ac; d["operatorDirect"]["standard"]["DC"]["eurPerKwh"]=dc
            d["generatedAt"]=now
            d["refresh"]={"mode":"automatic_official_page_parser","source":url,"refreshedAt":now,"lastResult":"validated"}
        changed=archive_if_changed(p,before,d,now)
        p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
        results.append({"operator":"Lidl France","path":rel,"status":"changed" if changed else "unchanged","values":{"AC":ac,"DC":dc}})
except Exception as e:
    results.append({"operator":"Lidl France","status":"failed_keep_last_valid","error":str(e)})

# STATIONS-E
try:
    url="https://stations-e.com/fr"
    t=fetch(url)
    # Read values from the official pricing table in row order.
    direct22=sanity(find_one(t,[r"Bornes\s+22AC\s+ou\s+24DC\s+([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"stations-e direct 22/24"))
    direct50=sanity(find_one(t,[r"Bornes\s+50DC\s+([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"stations-e direct 50"))
    p=ROOT/"data/operator_direct/stations_e_tariff_rules_france.json"; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    # The direct-payment values are first in each row. Badge/offer values remain validated separately and unchanged here.
    d["directPayment"]["ac22OrDc24EurPerKwh"]=direct22
    d["directPayment"]["dc50EurPerKwh"]=direct50
    d["retrievedAt"]=now
    d["refresh"]={"mode":"automatic_official_page_parser","source":url,"refreshedAt":now,"lastResult":"validated"}
    changed=archive_if_changed(p,before,d,now)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"STATIONS-E","path":str(p),"status":"changed" if changed else "unchanged","values":{"22AC_or_24DC":direct22,"50DC":direct50}})
except Exception as e:
    results.append({"operator":"STATIONS-E","status":"failed_keep_last_valid","error":str(e)})

# eborn
try:
    url="https://www.eborn.fr/tarifs/"
    t=fetch(url)
    vals={
      "aLaCarteAnnualFeeEur":sanity(find_one(t,[r"Abonn[ée]\s+[àa]\s+la\s+carte.*?([0-9]+(?:[,.][0-9]+)?)\s*€\s*TTC\s*Abonnement\s+annuel"],"eborn annual"),0,100),
      "monthlyBundleFeeEur":sanity(find_one(t,[r"Abonn[ée]\s+au\s+forfait.*?([0-9]+(?:[,.][0-9]+)?)\s*€\s*TTC\s*Abonnement\s+mensuel"],"eborn monthly"),0,200),
      "acceleratedCarte":sanity(find_one(t,[r"Charge\s+acc[ée]l[ée]r[ée]e.*?Abonn[ée]\s+[àa]\s+la\s+carte.*?([0-9]+[,.][0-9]+)\s*€\s*TTC\s*/\s*kWh"],"eborn accelerated carte")),
      "acceleratedNonSub":sanity(find_one(t,[r"Charge\s+acc[ée]l[ée]r[ée]e.*?Non\s+abonn[ée].*?([0-9]+[,.][0-9]+)\s*€\s*TTC\s*/\s*kWh"],"eborn accelerated non-sub")),
      "fastCarte":sanity(find_one(t,[r"Charge\s+rapide.*?Abonn[ée]\s+[àa]\s+la\s+carte.*?([0-9]+[,.][0-9]+)\s*€\s*TTC\s*/\s*kWh"],"eborn fast carte")),
      "fastNonSub":sanity(find_one(t,[r"Charge\s+rapide.*?Non\s+abonn[ée].*?([0-9]+[,.][0-9]+)\s*€\s*TTC\s*/\s*kWh"],"eborn fast non-sub")),
      "ultraCarte":sanity(find_one(t,[r"Charge\s+ultra-?rapide.*?Abonn[ée]\s+[àa]\s+la\s+carte.*?([0-9]+[,.][0-9]+)\s*(?:TTC\s*)?€\s*/\s*kWh"],"eborn ultra carte")),
      "ultraNonSub":sanity(find_one(t,[r"Charge\s+ultra-?rapide.*?Non\s+abonn[ée].*?([0-9]+[,.][0-9]+)\s*€\s*TTC\s*/\s*kWh"],"eborn ultra non-sub"))
    }
    p=ROOT/"data/operator_direct/eborn_easycharge_official_france.json"; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    d["subscription"]["aLaCarteAnnualFeeEur"]=vals["aLaCarteAnnualFeeEur"]
    d["subscription"]["monthlyBundleFeeEur"]=vals["monthlyBundleFeeEur"]
    m={x["class"]:x for x in d["powerClasses"]}
    m["accelerated"]["aLaCarteEurPerKwh"]=vals["acceleratedCarte"]; m["accelerated"]["nonSubscriberEurPerKwh"]=vals["acceleratedNonSub"]
    m["fast"]["aLaCarteEurPerKwh"]=vals["fastCarte"]; m["fast"]["nonSubscriberEurPerKwh"]=vals["fastNonSub"]
    m["ultra_fast"]["aLaCarteEurPerKwh"]=vals["ultraCarte"]; m["ultra_fast"]["nonSubscriberEurPerKwh"]=vals["ultraNonSub"]
    d["generatedAt"]=now
    d["refresh"]={"mode":"automatic_official_page_parser","source":url,"refreshedAt":now,"lastResult":"validated"}
    changed=archive_if_changed(p,before,d,now)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"eborn","path":str(p),"status":"changed" if changed else "unchanged","values":vals})
except Exception as e:
    results.append({"operator":"eborn","status":"failed_keep_last_valid","error":str(e)})

REPORT.write_text(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2))
if any(r["status"]=="failed_keep_last_valid" for r in results):
    raise SystemExit(2)
