#!/usr/bin/env python3
import json,re,urllib.request,html,hashlib
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(".")
DATA=ROOT/"data/operator_direct/delmonicos_direct_france_20261001.json"
REPORT=ROOT/"reports/fixed-tariff-refresh-france-delmonicos-latest.json"
UA="TeslaChargeCompanion/9 delmonicos-tariff-watch"
SOURCES=[
  "https://orne-transition.fr/nos-services/collectivites/bornes-de-recharge-irve/",
  "https://yutz.connectandgo.fr/tarifs/"
]

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*"})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read().decode("utf-8","ignore")
    txt=re.sub(r"<script[^>]*>.*?</script>"," ",raw,flags=re.I|re.S)
    txt=re.sub(r"<style[^>]*>.*?</style>"," ",txt,flags=re.I|re.S)
    txt=re.sub(r"<[^>]+>"," ",txt)
    txt=html.unescape(txt).replace("\xa0"," ")
    return re.sub(r"\s+"," ",txt).strip()

def h(s):
    return hashlib.sha256(re.sub(r"\s+"," ",s.lower()).strip().encode()).hexdigest()

now=datetime.now(timezone.utc).isoformat()
d=json.loads(DATA.read_text())
watch=[]
failed=False
previous=(d.get("refresh") or {}).get("sourceHashes",{})
current={}
for url in SOURCES:
    try:
        t=fetch(url)
        # Hash only tariff-relevant context where possible, fallback to page.
        low=t.lower()
        anchors=["tarif","borne","recharge","0,35","0,38","0,29","0,53"]
        pos=[low.find(a) for a in anchors if low.find(a)>=0]
        if pos:
            p=min(pos); t=t[max(0,p-1500):p+5000]
        sig=h(t); current[url]=sig
        state="baseline_established" if url not in previous else ("source_context_changed_review_required" if previous[url]!=sig else "unchanged")
        watch.append({"url":url,"status":state})
    except Exception as e:
        failed=True
        watch.append({"url":url,"status":"fetch_failed_keep_last_valid","error":str(e)})

direct_stations=len((d.get("directMapped") or {}).get("stations") or [])
migrated_stations=len((d.get("migratedFreshmileHomecourt") or {}).get("stations") or [])
residual_stations=int((d.get("residualFailClosed") or {}).get("stations") or 0)
d["refresh"]={
  "mode":"official_source_semantic_watch_keep_last_valid",
  "refreshedAt":now,
  "sourceHashes":current if not failed else previous,
  "lastResult":"fetch_failed_keep_last_valid" if failed else ("source_context_changed_review_required" if any(x["status"]=="source_context_changed_review_required" for x in watch) else "validated"),
  "failClosedResidualStations":residual_stations,
  "coverageAccounting":{"delmonicosOrneStations":direct_stations,"freshmileMigratedHomecourtStations":migrated_stations,
                        "resolvedStations":direct_stations+migrated_stations,"residualStations":residual_stations}
}
DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text(json.dumps({
  "generatedAt":now,
  "operator":"Delmonicos",
  "delmonicosOrneMappedStations":direct_stations,
  "delmonicosOrneTariffEurPerKwh":0.35,
  "freshmileMigratedHomecourtStations":migrated_stations,
  "resolvedStations":direct_stations+migrated_stations,
  "residualFailClosedStations":residual_stations,
  "sources":watch
},ensure_ascii=False,indent=2)+"\n")
print(REPORT.read_text())
if failed: raise SystemExit(2)
