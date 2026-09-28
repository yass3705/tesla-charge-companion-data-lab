#!/usr/bin/env python3
import json,gzip,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NAT="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
ROOT=Path(".")
OUT=Path("data/tcc_v9/switzerland.json")
REPORT=Path("docs/switzerland-v9-integration-2026-09-28.json")
OUT.parent.mkdir(parents=True,exist_ok=True)

req=urllib.request.Request(NAT,headers={"User-Agent":"TCC-V9-Switzerland/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r: raw=r.read()
if len(raw)>=2 and raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))

evses={}
def walk(x,owner=None,owner_name=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str):
            owner=x.get("OperatorID"); owner_name=x.get("OperatorName")
        eid=x.get("EvseID")
        if isinstance(eid,str):
            evses[eid]={
              "evseId":eid,"operatorId":owner,"operatorName":owner_name,
              "stationId":x.get("ChargingStationId"),"names":x.get("ChargingStationNames"),
              "address":x.get("Address"),"coordinates":x.get("GeoCoordinates"),
              "plugs":x.get("Plugs"),"chargingFacilities":x.get("ChargingFacilities"),
              "accessibility":x.get("Accessibility"),"authenticationModes":x.get("AuthenticationModes"),
              "paymentOptions":x.get("PaymentOptions"),"isOpen24Hours":x.get("IsOpen24Hours"),
              "directTariffs":[],"directTariffStatus":"unresolved"
            }
        for v in x.values(): walk(v,owner,owner_name)
    elif isinstance(x,list):
        for v in x: walk(v,owner,owner_name)
walk(nat)

# Curated production artifacts only. Generic atlas first/second-pass files are deliberately excluded.
sources=[
("IONITY","data/switzerland/ionity-official-national-direct-tariffs.json"),
("Migrol","data/switzerland/migrol-official-direct-tariffs.json"),
("Shell evpass","data/switzerland/shell-evpass-official-direct-tariffs.json"),
("Lidl","data/switzerland/lidl-official-direct-tariffs.json"),
("Plenitude","data/switzerland/plenitude-official-direct-tariffs.json"),
("PowerUp","data/switzerland/powerup-monta-direct-tariffs.json"),
("AGROLA","data/switzerland/agr-monta-direct-tariffs.json"),
("AIL emoti","data/switzerland/ail-emoti-official-direct-tariffs.json"),
("autoSense AMAG","data/switzerland/autosense-amag-direct-tariffs.json"),
("Saascharge","data/switzerland/saascharge-official-direct-tariffs.json"),
("Fastned","data/switzerland/fastned-official-direct-tariffs.json"),
("EWD","data/switzerland/ewd-official-direct-tariffs.json"),
("EWO eCarUp","data/switzerland/ewo-ecarup-direct-tariffs.json"),
("EBS eCarUp","data/switzerland/ebs-ecarup-direct-tariffs.json"),
("CHEVP evpass","data/switzerland/chevp-evpass-official-direct-tariffs.json"),
("TAE Matterhorn","data/switzerland/tae-matterhorn-terminal-direct-tariffs.json"),
("IWB Basel official","data/switzerland/iwb-official-basel-overlay.json"),
("CPI","data/switzerland/cpi-current-direct-tariffs.json"),
("CCI MOVE","data/switzerland/cci-move-cpo-tariffs-national.json"),
("SOC MOVE","data/switzerland/soc-move-cpo-tariffs-national.json"),
("MMN MOVE","data/switzerland/mmn-move-cpo-tariffs.json"),
("eCarUp exact","data/switzerland/ecarup-owner-direct-tariffs.json"),
("eCarUp coordinate safe","data/switzerland/ecarup-owner-coordinate-safe-overlay.json"),
]
classifications=[
("Partino restricted","data/switzerland/par-partino-restricted-direct-classification.json"),
("50five restricted","data/switzerland/505-restricted-direct-classification.json"),
("Porsche restricted","data/switzerland/911-restricted-direct-classification.json"),
("BCK restricted","data/switzerland/bck-restricted-direct-classification.json"),
]

def ids_from(obj):
    out=[]
    if isinstance(obj,dict):
        eid=obj.get("evseId") or obj.get("EvseID") or obj.get("evse_id")
        if isinstance(eid,str): out.append((eid,obj))
        for k,v in obj.items():
            if k in ("nationalRecord","evse","record"): continue
            if isinstance(v,(dict,list)): out.extend(ids_from(v))
    elif isinstance(obj,list):
        for v in obj: out.extend(ids_from(v))
    return out

source_stats=[]
for label,fp in sources:
    p=Path(fp)
    if not p.exists() or p.stat().st_size==0:
        source_stats.append({"label":label,"file":fp,"status":"missing_or_empty","matchedEvseCount":0}); continue
    try: obj=json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        source_stats.append({"label":label,"file":fp,"status":"invalid_json","matchedEvseCount":0}); continue
    seen=set()
    for eid,node in ids_from(obj):
        if eid not in evses: continue
        # Keep the source-native tariff node to avoid lossy schema guesses.
        # Skip nodes that are clearly only unresolved/classification evidence.
        low=json.dumps(node,ensure_ascii=False).lower()
        if not any(tok in low for tok in ("price","tariff","cost","energy","currency","chf","free","fee")): continue
        evses[eid]["directTariffs"].append({"sourceLabel":label,"sourceFile":fp,"data":node})
        evses[eid]["directTariffStatus"]="resolved"
        seen.add(eid)
    source_stats.append({"label":label,"file":fp,"status":"loaded","matchedEvseCount":len(seen)})

classified=set()
for label,fp in classifications:
    p=Path(fp)
    if not p.exists() or p.stat().st_size==0: continue
    try: obj=json.loads(p.read_text(encoding="utf-8"))
    except Exception: continue
    for eid,node in ids_from(obj):
        if eid in evses and evses[eid]["directTariffStatus"]!="resolved":
            evses[eid]["directTariffStatus"]="no_public_direct_tariff"
            evses[eid]["directTariffClassification"]={"sourceLabel":label,"sourceFile":fp}
            classified.add(eid)

# Canonical CPO status is metadata only: never filter EVSE visibility based on it.
progress={}
pp=Path("docs/switzerland-cpo-progress-2026-09.json")
if pp.exists():
    pj=json.loads(pp.read_text(encoding="utf-8"))
    progress={x.get("operatorId"):x for x in pj.get("operators",[]) if x.get("operatorId")}

now=datetime.now(timezone.utc).isoformat()
rows=list(evses.values())
payload={
 "schemaVersion":1,"dataset":"tcc-v9-switzerland","generatedAt":now,
 "country":"CH","nationalSource":NAT,
 "policy":{
   "stationVisibility":"Every EVSE from the current Swiss national source remains in the bundle regardless of CPO complete/blocked/partial status.",
   "tariffOverlay":"Only validated deterministic direct-tariff production artifacts are overlaid. Missing tariff never removes an EVSE.",
   "blockedCpoHandling":"Blocked/partial is CPO-level research metadata only; resolved EVSE prices inside such CPOs remain publishable.",
   "otherPriceLayers":"Electra, Electroverse and subscription-adjusted prices are intentionally separate runtime overlays and are not replaced by this direct-CPO bundle."
 },
 "counts":{
   "nationalEvseCount":len(rows),
   "directTariffResolvedEvseCount":sum(x["directTariffStatus"]=="resolved" for x in rows),
   "noPublicDirectTariffEvseCount":sum(x["directTariffStatus"]=="no_public_direct_tariff" for x in rows),
   "directTariffUnresolvedEvseCount":sum(x["directTariffStatus"]=="unresolved" for x in rows),
 },
 "sourceStats":source_stats,
 "cpoResearchStatus":progress,
 "evses":rows
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
report={k:v for k,v in payload.items() if k!="evses"}
report["output"]=str(OUT)
report["outputBytes"]=OUT.stat().st_size
REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))

# trigger
