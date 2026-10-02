#!/usr/bin/env python3
import json,re,urllib.request,html,hashlib
from pathlib import Path
from datetime import datetime,timezone

UA="TeslaChargeCompanion/9 fixed-tariff-refresh-bfc"
ROOT=Path(".")
REPORT=ROOT/"reports"/"fixed-tariff-refresh-bfc-latest.json"
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

def norm(s):
    return re.sub(r"\s+"," ",s.lower()).strip()

def hash_text(s):
    return hashlib.sha256(norm(s).encode("utf-8")).hexdigest()

def find_context(text,terms,window=800):
    low=text.lower()
    pos=[low.find(t.lower()) for t in terms if low.find(t.lower())>=0]
    if not pos:
        raise ValueError("context terms not found: "+",".join(terms))
    p=min(pos)
    return text[max(0,p-window):p+window]

def parse_sied70(text):
    def one(pattern,label):
        vals=sorted(set(float(x.replace(",",".")) for x in re.findall(pattern,text,re.I|re.S)))
        if len(vals)!=1: raise ValueError(f"{label}: {vals}")
        return vals[0]
    return {
      "accelerated":one(r"puissance\s+inf[ée]rieure\s+[àa]\s+50\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*TTC\s*/\s*kWh","sied70 accelerated"),
      "rapid":one(r"puissance\s+sup[ée]rieure\s+ou\s+[ée]gale\s+[àa]\s+50\s*kW.*?([0-9]+[,.][0-9]+)\s*€\s*TTC\s*/\s*kWh","sied70 rapid"),
      "occupancy":one(r"p[ée]nalit[ée]\s+de\s+([0-9]+[,.][0-9]+)\s*€\s*/\s*minute","sied70 occupancy")
    }

now=datetime.now(timezone.utc).isoformat()
results=[]

bfc=fetch(BFC)
syded=fetch(SYDED)

watch_defs=[
  ("SICECO Côte-d'Or","data/operator_direct/siceco_cotedor_official.json",BFC,find_context(bfc,["SICECO","Côte-d'Or"])),
  ("SIEEEN Nièvre","data/operator_direct/sieeen_nievre_official.json",BFC,find_context(bfc,["SIEEEN","Nièvre"])),
  ("SDEY Yonne","data/operator_direct/sdey_official_yonne.json",BFC,find_context(bfc,["SDEY","Yonne"])),
  ("TDE90 Belfort","data/operator_direct/tde90_belfort_official.json",BFC,find_context(bfc,["Territoire d'Energie 90","Belfort"])),
  ("SYDED Doubs","data/operator_direct/syded_doubs_official.json",SYDED,find_context(syded,["SYDED","22 kW","50 kW","100 kW"]))
]

for operator,path,source,ctx in watch_defs:
    p=ROOT/path
    d=json.loads(p.read_text())
    current_hash=hash_text(ctx)
    refresh=d.get("refresh",{})
    previous_hash=refresh.get("semanticTariffContextSha256")
    refresh.update({
      "mode":"official_source_semantic_watch_keep_last_valid",
      "source":source,
      "refreshedAt":now,
      "semanticTariffContextSha256":current_hash,
      "lastResult":"baseline_established" if not previous_hash else ("source_context_changed_review_required" if previous_hash!=current_hash else "unchanged")
    })
    d["refresh"]=refresh
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({
      "operator":operator,
      "path":path,
      "status":refresh["lastResult"],
      "source":source,
      "note":"Tariff values are not rewritten by this watch. Existing machine-validated grid is preserved unless a source-context change is detected and revalidated."
    })

# SIED70 remains safe enough for exact automatic parsing
try:
    t=fetch(SIED70)
    vals=parse_sied70(t)
    path="data/operator_direct/sied70_official_haute_saone.json"; p=ROOT/path; d=json.loads(p.read_text())
    d["operatorDirect"]["acceleratedBelow50Kw"]["eurPerKwh"]=vals["accelerated"]
    d["operatorDirect"]["acceleratedBelow50Kw"]["postChargeFee"]["eurPerMinute"]=vals["occupancy"]
    d["operatorDirect"]["rapid50KwOrMore"]["eurPerKwh"]=vals["rapid"]
    d["operatorDirect"]["rapid50KwOrMore"]["postChargeFee"]["eurPerMinute"]=vals["occupancy"]
    d["generatedAt"]=now
    d["refresh"]={"mode":"automatic_official_page_parser","source":SIED70,"refreshedAt":now,"lastResult":"validated"}
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"SIED70 Haute-Saône","path":path,"status":"unchanged","values":vals})
except Exception as e:
    results.append({"operator":"SIED70 Haute-Saône","status":"failed_keep_last_valid","error":str(e)})

REPORT.write_text(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2))
if any(r["status"]=="failed_keep_last_valid" for r in results):
    raise SystemExit(2)
