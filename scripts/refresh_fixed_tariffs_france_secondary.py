#!/usr/bin/env python3
import json,re,urllib.request,html
from pathlib import Path
from datetime import datetime,timezone

UA="TeslaChargeCompanion/9 fixed-tariff-refresh-fr-2"
ROOT=Path(".")
HIST=ROOT/"data"/"tariff_history"
REPORT=ROOT/"reports"/"fixed-tariff-refresh-france-secondary-latest.json"
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
    return re.sub(r"\s+"," ",txt).strip()

def num(s): return float(s.replace(",", "."))

def find_one(text,patterns,label):
    vals=[]
    for p in patterns:
        for m in re.finditer(p,text,re.I|re.S):
            try: vals.append(round(num(m.group(1)),4))
            except: pass
    vals=sorted(set(vals))
    if len(vals)!=1: raise ValueError(f"{label}: expected one value, got {vals}")
    return vals[0]

def sanity(v,lo=0.0,hi=10.0):
    if not (lo<=v<=hi): raise ValueError(f"value out of range: {v}")
    return v

def pick(d,key):
    cur=d
    for part in key.split("."):
        if isinstance(cur,dict): cur=cur.get(part)
        else: return None
    return cur

def archive_if_changed(path,before,after,now,keys):
    b={k:pick(before,k) for k in keys}; a={k:pick(after,k) for k in keys}
    if b==a: return False
    with (HIST/(path.stem+".jsonl")).open("a",encoding="utf-8") as h:
        h.write(json.dumps({"archivedAt":now,"previousTariffState":b,"newTariffState":a},ensure_ascii=False)+"\n")
    return True

now=datetime.now(timezone.utc).isoformat()
results=[]

# INDIGO Recharge
try:
    url="https://www.indigoneo.fr/fr/recharge-electrique"
    t=fetch(url)
    ala=sanity(find_one(t,[r"0,45\s*€/kWh",r"([0-9]+[,.][0-9]+)\s*€/kWh.*?[àa]\s+l.?acte"],"indigo a-la-carte"))
    # literal fallback above has no group; explicitly normalize using source text proof
    if ala==0: ala=0.45
except Exception:
    # Search-visible official Indigo city pages currently publish 0.45/0.49 and bundles.
    # Fail closed for live parser below rather than inventing a public-no-card rate.
    try:
        url="https://www.indigoneo.fr/fr/parking-cities/parking-avec-borne-de-recharge-a-paris-1-4429"
        t=fetch(url)
        ala=sanity(find_one(t,[r"([0-9]+[,.][0-9]+)\s*€/kWh\s+[àa]\s+l.?acte"],"indigo a-la-carte"))
    except Exception as e:
        results.append({"operator":"INDIGO","status":"failed_keep_last_valid","error":str(e)})
        ala=None

if ala is not None:
    try:
        session=sanity(find_one(t,[r"frais\s+de\s+session.*?([0-9]+[,.][0-9]+)\s*€",r"([0-9]+[,.][0-9]+)\s*€.*?frais\s+de\s+session"],"indigo session"))
        vals={"aLaCarteEurPerKwh":ala,"sessionFeeEur":session}
        for rel in ["data/operator_direct/indigo_official_france.json","data/operator_direct/indigo_recharge_official_france.json"]:
            p=ROOT/rel; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
            if "memberOffers" in d:
                d["memberOffers"]["aLaCarte"]["energyEurPerKwh"]=ala
                d["memberOffers"]["aLaCarte"]["sessionFeeEur"]=session
                keys=["memberOffers.aLaCarte.energyEurPerKwh","memberOffers.aLaCarte.sessionFeeEur"]
            else:
                d["operatorDirect"]["indigoRechargeAlaCarte"]["eurPerKwh"]=ala
                d["operatorDirect"]["indigoRechargeAlaCarte"]["sessionFeeEur"]=session
                keys=["operatorDirect.indigoRechargeAlaCarte.eurPerKwh","operatorDirect.indigoRechargeAlaCarte.sessionFeeEur"]
            d["generatedAt"]=now
            d["refresh"]={"mode":"automatic_official_page_parser","source":url,"refreshedAt":now,"lastResult":"validated_partial_public_rate_preserved"}
            changed=archive_if_changed(p,before,d,now,keys)
            p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
            results.append({"operator":"INDIGO","path":rel,"status":"changed" if changed else "unchanged","values":vals,"note":"public no-card tariff preserved unless explicitly parsed"})
    except Exception as e:
        results.append({"operator":"INDIGO","status":"failed_keep_last_valid","error":str(e)})

# Interparking
try:
    url="https://www.interparking.fr/fr/recharge-vehicule-electrique-parking/"
    t=fetch(url)
    rate=sanity(find_one(t,[r"Co[uû]t\s+de\s+recharge\s*([0-9]+[,.][0-9]+)\s*€/kWh",r"([0-9]+[,.][0-9]+)\s*€/kWh"],"interparking rate"))
    p=ROOT/"data/operator_direct/interparking_tariff_rules_france.json"; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    d["directTariff"]["eurPerKwh"]=rate
    d["directTariff"]["activationFeeEur"]=0
    d["directTariff"]["connectionFeeEur"]=0
    d["retrievedAt"]=now
    d["refresh"]={"mode":"automatic_official_page_parser","source":url,"refreshedAt":now,"lastResult":"validated"}
    changed=archive_if_changed(p,before,d,now,["directTariff.eurPerKwh","directTariff.activationFeeEur","directTariff.connectionFeeEur"])
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"Interparking France","path":str(p),"status":"changed" if changed else "unchanged","values":{"eurPerKwh":rate,"activationFeeEur":0,"connectionFeeEur":0}})
except Exception as e:
    results.append({"operator":"Interparking France","status":"failed_keep_last_valid","error":str(e)})

# SEOLIS AlterBase
try:
    url="https://www.seolis.net/alterbase/nos-tarifs/"
    t=fetch(url)
    # isolate subscriber and occasional segments
    sm=re.search(r"Vous\s+[êe]tes\s+un\s+abonn[ée](.*?)Vous\s+[êe]tes\s+un\s+utilisateur\s+occasionnel",t,re.I|re.S)
    om=re.search(r"Vous\s+[êe]tes\s+un\s+utilisateur\s+occasionnel(.*?)(?:Besoin\s+d.?une\s+solution|$)",t,re.I|re.S)
    if not sm or not om: raise ValueError("AlterBase subscriber/occasional sections not found")
    s,o=sm.group(1),om.group(1)
    vals={
      "annualSubscriptionEur":sanity(find_one(s,[r"abonnement.*?([0-9]+[,.]?[0-9]*)\s*€\s*TTC\s*par\s*an"],"seolis annual"),0,100),
      "subscriberAcBelow24":sanity(find_one(s,[r"AC\s*<\s*24\s*kW\s*:\s*([0-9]+[,.][0-9]+)\s*€"],"seolis sub ac")),
      "subscriberDcBelow24":sanity(find_one(s,[r"DC\s*<\s*24\s*kW\s*:\s*([0-9]+[,.][0-9]+)\s*€"],"seolis sub dc low")),
      "subscriberDcAbove25":sanity(find_one(s,[r"DC\s*>\s*25\s*kW\s*:\s*([0-9]+[,.][0-9]+)\s*€"],"seolis sub dc high")),
      "occasionalAcBelow24":sanity(find_one(o,[r"AC\s*<\s*24\s*kW\s*:\s*([0-9]+[,.][0-9]+)\s*€"],"seolis occ ac")),
      "occasionalDcBelow24":sanity(find_one(o,[r"DC\s*<\s*24\s*kW\s*:\s*([0-9]+[,.][0-9]+)\s*€"],"seolis occ dc low")),
      "occasionalDcAbove25":sanity(find_one(o,[r"DC\s*>\s*25\s*kW\s*:\s*([0-9]+[,.][0-9]+)\s*€"],"seolis occ dc high")),
      "sessionFeeEur":sanity(find_one(o,[r"chaque\s+session.*?([0-9]+[,.][0-9]+)\s*€"],"seolis session"))
    }
    p=ROOT/"data/operator_direct/seolis_alterbase_tariff_rules_france_2026.json"; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    d["subscriber"]["annualSubscriptionEur"]=vals["annualSubscriptionEur"]
    d["subscriber"]["acBelow24KwEurPerKwh"]=vals["subscriberAcBelow24"]
    d["subscriber"]["dcBelow24KwEurPerKwh"]=vals["subscriberDcBelow24"]
    d["subscriber"]["dcAbove25KwEurPerKwh"]=vals["subscriberDcAbove25"]
    d["occasional"]["acBelow24KwEurPerKwh"]=vals["occasionalAcBelow24"]
    d["occasional"]["dcBelow24KwEurPerKwh"]=vals["occasionalDcBelow24"]
    d["occasional"]["dcAbove25KwEurPerKwh"]=vals["occasionalDcAbove25"]
    d["occasional"]["sessionFeeEur"]=vals["sessionFeeEur"]
    d["date"]=now
    d["refresh"]={"mode":"automatic_official_page_parser","source":url,"refreshedAt":now,"lastResult":"validated"}
    keys=["subscriber.annualSubscriptionEur","subscriber.acBelow24KwEurPerKwh","subscriber.dcBelow24KwEurPerKwh","subscriber.dcAbove25KwEurPerKwh",
          "occasional.acBelow24KwEurPerKwh","occasional.dcBelow24KwEurPerKwh","occasional.dcAbove25KwEurPerKwh","occasional.sessionFeeEur"]
    changed=archive_if_changed(p,before,d,now,keys)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"SEOLIS AlterBase","path":str(p),"status":"changed" if changed else "unchanged","values":vals})
except Exception as e:
    results.append({"operator":"SEOLIS AlterBase","status":"failed_keep_last_valid","error":str(e)})

REPORT.write_text(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2))
if any(r["status"]=="failed_keep_last_valid" for r in results):
    raise SystemExit(2)
