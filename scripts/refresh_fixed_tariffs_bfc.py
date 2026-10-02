#!/usr/bin/env python3
import json,re,urllib.request,html
from pathlib import Path
from datetime import datetime,timezone

UA="TeslaChargeCompanion/9 fixed-tariff-refresh-bfc"
ROOT=Path(".")
HIST=ROOT/"data"/"tariff_history"
REPORT=ROOT/"reports"/"fixed-tariff-refresh-bfc-latest.json"
HIST.mkdir(parents=True,exist_ok=True)
REPORT.parent.mkdir(parents=True,exist_ok=True)

BFC="https://www.territoiredenergie-bourgogne-franche-comte.com/nos-offres-et-tarifs/"
SYDED="https://www.syded.fr/bornes-de-recharge-pour-vehicules-electriques/"
SIED70="https://www.sied70.fr/irve"

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

def one(text,patterns,label):
    vals=[]
    for p in patterns:
        for m in re.finditer(p,text,re.I|re.S):
            try: vals.append(round(num(m.group(1)),4))
            except: pass
    vals=sorted(set(vals))
    if len(vals)!=1: raise ValueError(f"{label}: expected one value, got {vals}")
    return vals[0]

def section(text,start,end,label):
    m=re.search(start+r"(.*?)"+end,text,re.I|re.S)
    if not m: raise ValueError(f"{label}: section not found")
    return m.group(1)

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

def save(path,d,before,keys,source,now,results,operator,values):
    p=ROOT/path
    d["generatedAt"]=now
    d["refresh"]={"mode":"automatic_official_page_parser","source":source,"refreshedAt":now,"lastResult":"validated"}
    changed=archive_if_changed(p,before,d,now,keys)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":operator,"path":path,"status":"changed" if changed else "unchanged","values":values})

now=datetime.now(timezone.utc).isoformat()
results=[]
bfc=fetch(BFC)

# SICECO Côte-d'Or
try:
    s=section(bfc,r"SICECO\s+Territoire\s+d.?Energie\s+Côte-d.?Or",r"SYDED\s*\(Doubs\)","SICECO")
    vals={
      "normalFixed":one(s,[r"Charge\s+lente.*?([0-9]+[,.][0-9]+)\s*€\s*par\s*p[ée]riode"],"siceco slow fixed"),
      "normalKwh":one(s,[r"Charge\s+lente.*?\+\s*([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"siceco slow kwh"),
      "normalMin":one(s,[r"Charge\s+lente.*?\+\s*[0-9]+[,.][0-9]+\s*€\s*/\s*kWh\s*\+\s*([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"siceco slow min"),
      "rapidFixed":one(s,[r"Charge\s+rapide.*?([0-9]+[,.]?[0-9]*)\s*€\s*par\s*p[ée]riode"],"siceco rapid fixed"),
      "rapidKwh":one(s,[r"Charge\s+rapide.*?\+\s*([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"siceco rapid kwh"),
      "rapidMin":one(s,[r"Charge\s+rapide.*?\+\s*[0-9]+[,.][0-9]+\s*€\s*/\s*kWh\s*\+\s*([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"siceco rapid min")
    }
    path="data/operator_direct/siceco_cotedor_official.json"; p=ROOT/path; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    n=d["operatorDirect"]["normalUpTo22Kva"]; r=d["operatorDirect"]["rapidUpTo50Kva"]
    n["fixedFeeEurPer12Hours"]=vals["normalFixed"]; n["eurPerKwh"]=vals["normalKwh"]; n["eurPerMinute"]=vals["normalMin"]
    r["fixedFeeEurPer12Hours"]=vals["rapidFixed"]; r["eurPerKwh"]=vals["rapidKwh"]; r["eurPerMinute"]=vals["rapidMin"]
    save(path,d,before,[
      "operatorDirect.normalUpTo22Kva.fixedFeeEurPer12Hours","operatorDirect.normalUpTo22Kva.eurPerKwh","operatorDirect.normalUpTo22Kva.eurPerMinute",
      "operatorDirect.rapidUpTo50Kva.fixedFeeEurPer12Hours","operatorDirect.rapidUpTo50Kva.eurPerKwh","operatorDirect.rapidUpTo50Kva.eurPerMinute"
    ],BFC,now,results,"SICECO Côte-d'Or",vals)
except Exception as e:
    results.append({"operator":"SICECO Côte-d'Or","status":"failed_keep_last_valid","error":str(e)})

# SYDED Doubs
try:
    try:
        t=fetch(SYDED)
        s=t
    except Exception:
        s=section(bfc,r"SYDED\s*\(Doubs\)",r"SIEEEN\s*\(Nièvre\)","SYDED")
    vals={
      "22kwh":one(s,[r"22\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"syded 22 kwh"),
      "22min":one(s,[r"22\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"syded 22 min"),
      "50kwh":one(s,[r"50\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"syded 50 kwh"),
      "50min":one(s,[r"50\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"syded 50 min"),
      "100kwh":one(s,[r"100\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"syded 100 kwh"),
      "100min":one(s,[r"100\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"syded 100 min")
    }
    path="data/operator_direct/syded_doubs_official.json"; p=ROOT/path; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    for key,kwh,mn in [("accelerated22Kw","22kwh","22min"),("rapid50Kw","50kwh","50min"),("rapid100Kw","100kwh","100min")]:
        d["operatorDirect"][key]["eurPerKwh"]=vals[kwh]
        d["operatorDirect"][key]["connectionDurationFee"]["eurPerMinute"]=vals[mn]
    save(path,d,before,[
      "operatorDirect.accelerated22Kw.eurPerKwh","operatorDirect.accelerated22Kw.connectionDurationFee.eurPerMinute",
      "operatorDirect.rapid50Kw.eurPerKwh","operatorDirect.rapid50Kw.connectionDurationFee.eurPerMinute",
      "operatorDirect.rapid100Kw.eurPerKwh","operatorDirect.rapid100Kw.connectionDurationFee.eurPerMinute"
    ],SYDED,now,results,"SYDED Doubs",vals)
except Exception as e:
    results.append({"operator":"SYDED Doubs","status":"failed_keep_last_valid","error":str(e)})

# SIEEEN Nièvre
try:
    s=section(bfc,r"SIEEEN\s*\(Nièvre\)",r"SIED70\s*\(Haute-Saône\)","SIEEEN")
    vals={
      "22day":one(s,[r"22\s*kW.*?6h\s+[àa]\s+minuit\s*:\s*([0-9]+[,.][0-9]+)\s*€\s*/?\s*kWh"],"sieeen 22 day"),
      "22night":one(s,[r"22\s*kW.*?minuit\s+[àa]\s+6h\s*:\s*([0-9]+[,.][0-9]+)\s*€\s*/?\s*kWh"],"sieeen 22 night"),
      "50day":one(s,[r"50\s*kW.*?6h\s+[àa]\s+minuit\s*:\s*([0-9]+[,.][0-9]+)\s*€.*?kWh"],"sieeen 50 day"),
      "50night":one(s,[r"50\s*kW.*?minuit\s+[àa]\s+6h\s*:\s*([0-9]+[,.][0-9]+)\s*€.*?kWh"],"sieeen 50 night")
    }
    path="data/operator_direct/sieeen_nievre_official.json"; p=ROOT/path; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    d["operatorDirect"]["accelerated22Kw"]["day"]["eurPerStartedKwh"]=vals["22day"]
    d["operatorDirect"]["accelerated22Kw"]["night"]["eurPerStartedKwh"]=vals["22night"]
    d["operatorDirect"]["rapid50Kw"]["day"]["eurPerStartedKwh"]=vals["50day"]
    d["operatorDirect"]["rapid50Kw"]["night"]["eurPerStartedKwh"]=vals["50night"]
    save(path,d,before,[
      "operatorDirect.accelerated22Kw.day.eurPerStartedKwh","operatorDirect.accelerated22Kw.night.eurPerStartedKwh",
      "operatorDirect.rapid50Kw.day.eurPerStartedKwh","operatorDirect.rapid50Kw.night.eurPerStartedKwh"
    ],BFC,now,results,"SIEEEN Nièvre",vals)
except Exception as e:
    results.append({"operator":"SIEEEN Nièvre","status":"failed_keep_last_valid","error":str(e)})

# SIED70 Haute-Saône
try:
    t=fetch(SIED70)
    vals={
      "accelerated":one(t,[r"(?:<\s*50\s*kW|22\s*kW).*?([0-9]+[,.][0-9]+)\s*€\s*/?\s*kWh"],"sied70 accelerated"),
      "rapid":one(t,[r"(?:>=?\s*50\s*kW|150\s*kW).*?([0-9]+[,.][0-9]+)\s*€\s*/?\s*kWh"],"sied70 rapid"),
      "occupancy":one(t,[r"([0-9]+[,.][0-9]+)\s*€\s*/\s*min"],"sied70 occupancy")
    }
    path="data/operator_direct/sied70_official_haute_saone.json"; p=ROOT/path; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    d["operatorDirect"]["acceleratedBelow50Kw"]["eurPerKwh"]=vals["accelerated"]
    d["operatorDirect"]["acceleratedBelow50Kw"]["postChargeFee"]["eurPerMinute"]=vals["occupancy"]
    d["operatorDirect"]["rapid50KwOrMore"]["eurPerKwh"]=vals["rapid"]
    d["operatorDirect"]["rapid50KwOrMore"]["postChargeFee"]["eurPerMinute"]=vals["occupancy"]
    save(path,d,before,[
      "operatorDirect.acceleratedBelow50Kw.eurPerKwh","operatorDirect.acceleratedBelow50Kw.postChargeFee.eurPerMinute",
      "operatorDirect.rapid50KwOrMore.eurPerKwh","operatorDirect.rapid50KwOrMore.postChargeFee.eurPerMinute"
    ],SIED70,now,results,"SIED70 Haute-Saône",vals)
except Exception as e:
    results.append({"operator":"SIED70 Haute-Saône","status":"failed_keep_last_valid","error":str(e)})

# SDEY Yonne
try:
    s=section(bfc,r"SDEY\s*\(Yonne\)",r"Territoire\s+d.?Energie\s+90","SDEY")
    vals={
      "normal":one(s,[r"normale.*?<\s*25\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"sdey normal"),
      "rapid":one(s,[r"rapide.*?>\s*25\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"sdey rapid"),
      "ultra":one(s,[r"ultra-?rapide.*?>\s*100\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"sdey ultra"),
      "normalSub":one(s,[r"normale.*?Tarif\s+abonn[ée]\s*:\s*([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"sdey normal sub"),
      "rapidSub":one(s,[r"rapide.*?>\s*25\s*kW.*?Tarif\s+abonn[ée]\s*:\s*([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"sdey rapid sub"),
      "ultraSub":one(s,[r"ultra-?rapide.*?>\s*100\s*kW.*?Tarif\s+abonn[ée]\s*:\s*([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"sdey ultra sub")
    }
    path="data/operator_direct/sdey_official_yonne.json"; p=ROOT/path; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    d["operatorDirect"]["normalBelow25Kw"]["eurPerKwh"]=vals["normal"]
    d["operatorDirect"]["rapidAbove25Kw"]["eurPerKwh"]=vals["rapid"]
    d["operatorDirect"]["ultraRapidAbove100Kw"]["eurPerKwh"]=vals["ultra"]
    m=d["membership"]["departmentalSubscription"]
    m["normalBelow25KwEurPerKwh"]=vals["normalSub"]; m["rapidAbove25KwEurPerKwh"]=vals["rapidSub"]; m["ultraRapidAbove100KwEurPerKwh"]=vals["ultraSub"]
    save(path,d,before,[
      "operatorDirect.normalBelow25Kw.eurPerKwh","operatorDirect.rapidAbove25Kw.eurPerKwh","operatorDirect.ultraRapidAbove100Kw.eurPerKwh",
      "membership.departmentalSubscription.normalBelow25KwEurPerKwh","membership.departmentalSubscription.rapidAbove25KwEurPerKwh","membership.departmentalSubscription.ultraRapidAbove100KwEurPerKwh"
    ],BFC,now,results,"SDEY Yonne",vals)
except Exception as e:
    results.append({"operator":"SDEY Yonne","status":"failed_keep_last_valid","error":str(e)})

# TDE90 Belfort
try:
    s=section(bfc,r"Territoire\s+d.?Energie\s+90",r"Op[ée]rateur\s+tiers","TDE90")
    vals={
      "22kwh":one(s,[r"22\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"tde90 22"),
      "22min":one(s,[r"22\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"tde90 22 min"),
      "50kwh":one(s,[r"50\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"tde90 50"),
      "50min":one(s,[r"50\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"tde90 50 min"),
      "100kwh":one(s,[r"100\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*kWh"],"tde90 100"),
      "100min":one(s,[r"100\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*/\s*minute"],"tde90 100 min")
    }
    path="data/operator_direct/tde90_belfort_official.json"; p=ROOT/path; d=json.loads(p.read_text()); before=json.loads(json.dumps(d))
    for key,kwh,mn in [("accelerated22Kw","22kwh","22min"),("rapid50Kw","50kwh","50min"),("ultraRapid100Kw","100kwh","100min")]:
        d["operatorDirect"][key]["eurPerKwh"]=vals[kwh]
        d["operatorDirect"][key]["connectionTimeFee"]["eurPerMinuteAfter"]=vals[mn]
    save(path,d,before,[
      "operatorDirect.accelerated22Kw.eurPerKwh","operatorDirect.accelerated22Kw.connectionTimeFee.eurPerMinuteAfter",
      "operatorDirect.rapid50Kw.eurPerKwh","operatorDirect.rapid50Kw.connectionTimeFee.eurPerMinuteAfter",
      "operatorDirect.ultraRapid100Kw.eurPerKwh","operatorDirect.ultraRapid100Kw.connectionTimeFee.eurPerMinuteAfter"
    ],BFC,now,results,"TDE90 Belfort",vals)
except Exception as e:
    results.append({"operator":"TDE90 Belfort","status":"failed_keep_last_valid","error":str(e)})

REPORT.write_text(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2))
if any(r["status"]=="failed_keep_last_valid" for r in results):
    raise SystemExit(2)
