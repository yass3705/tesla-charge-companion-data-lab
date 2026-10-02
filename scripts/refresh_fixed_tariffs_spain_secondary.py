#!/usr/bin/env python3
import json,re,urllib.request,html,hashlib
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(".")
REPORT=ROOT/"reports/fixed-tariff-refresh-spain-secondary-latest.json"
UA="TeslaChargeCompanion/9 fixed-tariff-spain-secondary"

def fetch(url,binary=False):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"*/*"})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read()
    if binary: return raw
    txt=raw.decode("utf-8","ignore")
    txt=re.sub(r"<script[^>]*>.*?</script>"," ",txt,flags=re.I|re.S)
    txt=re.sub(r"<style[^>]*>.*?</style>"," ",txt,flags=re.I|re.S)
    txt=re.sub(r"<[^>]+>"," ",txt)
    txt=html.unescape(txt).replace("\xa0"," ")
    return re.sub(r"\s+"," ",txt).strip()

def h_bytes(b): return hashlib.sha256(b).hexdigest()
def h_text(s): return hashlib.sha256(re.sub(r"\s+"," ",s.lower()).strip().encode()).hexdigest()

now=datetime.now(timezone.utc).isoformat()
results=[]

# EMT Madrid: legal tariff page semantic watch
try:
    path=ROOT/"data/operator_direct/emt_madrid_official_spain.json"
    d=json.loads(path.read_text())
    url=d["source"]
    t=fetch(url)
    low=t.lower()
    anchors=["colón","reserva","retirada","pitis","fuente de la mora","metropolitano"]
    pos=[low.find(a) for a in anchors if low.find(a)>=0]
    if not pos: raise ValueError("EMT tariff context not found")
    p=min(pos); ctx=t[max(0,p-1500):p+7000]
    sig=h_text(ctx)
    prev=(d.get("refresh") or {}).get("semanticTariffContextSha256")
    state="baseline_established" if not prev else ("source_context_changed_review_required" if prev!=sig else "unchanged")
    d["refresh"]={"mode":"official_legal_tariff_semantic_watch_keep_last_valid","source":url,"refreshedAt":now,"semanticTariffContextSha256":sig,"lastResult":state}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"EMT Madrid","status":state})
except Exception as e:
    results.append({"operator":"EMT Madrid","status":"failed_keep_last_valid","error":str(e)})

# Endesa: official tariff PDF raw hash watch
try:
    path=ROOT/"data/operator_direct/endesa_official_spain.json"
    d=json.loads(path.read_text())
    url=d["source"]
    raw=fetch(url,binary=True)
    sig=h_bytes(raw)
    prev=(d.get("refresh") or {}).get("sourceSha256")
    state="baseline_established" if not prev else ("source_pdf_changed_review_required" if prev!=sig else "unchanged")
    d["refresh"]={"mode":"official_tariff_pdf_hash_watch_keep_last_valid","source":url,"refreshedAt":now,"sourceSha256":sig,"lastResult":state}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"Endesa","status":state,"bytes":len(raw)})
except Exception as e:
    results.append({"operator":"Endesa","status":"failed_keep_last_valid","error":str(e)})

# Plenergy: exact station page parser
try:
    path=ROOT/"data/operator_direct/plenergy_official_spain.json"
    d=json.loads(path.read_text())
    failures=[]; changed=[]; checked=[]
    for st in d["stationTariffs"]:
        url=st["source"]
        try:
            t=fetch(url)
            vals=sorted(set(float(x.replace(",",".")) for x in re.findall(
                r"(?:Precio|Price|Preu|Preço|Prezioa)[^0-9]{0,40}(?:per\s*)?K[Ww][^0-9]{0,40}([0-9]+[,.][0-9]+)\s*€",
                t,re.I
            )))
            if len(vals)!=1:
                raise ValueError(f"expected one exact price, got {vals}")
            price=vals[0]
            old=float(st["eurPerKwh"])
            if abs(old-price)>1e-9:
                st["eurPerKwh"]=price; changed.append({"station":st["station"],"old":old,"new":price})
            checked.append({"station":st["station"],"eurPerKwh":price})
        except Exception as e:
            failures.append({"station":st["station"],"error":str(e)})
    state="failed_keep_last_valid" if failures else ("changed" if changed else "unchanged")
    d["verifiedAt"]=now
    d["refresh"]={"mode":"automatic_exact_station_page_parser","refreshedAt":now,"lastResult":state,"checkedStations":len(checked),"failedStations":len(failures)}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    results.append({"operator":"Plenergy","status":state,"checked":checked,"changed":changed,"failures":failures})
except Exception as e:
    results.append({"operator":"Plenergy","status":"failed_keep_last_valid","error":str(e)})

REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2)+"\n")
print(REPORT.read_text())
if any(r["status"]=="failed_keep_last_valid" for r in results):
    raise SystemExit(2)
