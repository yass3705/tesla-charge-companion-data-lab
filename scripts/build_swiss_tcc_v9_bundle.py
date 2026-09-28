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
("Swisscharge","data/swisscharge/swisscharge-tariffs.json"),
("ewz","data/switzerland/ewz-direct-tariffs.json"),
("Energie 360","data/switzerland/energie360-direct-tariffs.json"),
("Electra","data/switzerland/electra-direct-tariffs.json"),
("MOVE","data/switzerland/move-direct-tariffs.json"),
("Energiedienst CH","data/switzerland/edh-direct-tariffs.json"),
("Energiedienst DE","data/switzerland/de-edh-direct-tariffs.json"),
("ewz second pass","data/switzerland/ewz-direct-tariffs-second-pass.json"),
("Energie 360 second pass","data/switzerland/energie360-direct-tariffs-second-pass.json"),
("Electra second pass","data/switzerland/electra-direct-tariffs-second-pass.json"),
("MOVE second pass","data/switzerland/move-direct-tariffs-second-pass.json"),
("IWB second pass","data/switzerland/iwb-direct-tariffs-second-pass.json"),
]
classifications=[
("Partino restricted","data/switzerland/par-partino-restricted-direct-classification.json"),
("50five restricted","data/switzerland/505-restricted-direct-classification.json"),
("Porsche restricted","data/switzerland/911-restricted-direct-classification.json"),
("BCK restricted","data/switzerland/bck-restricted-direct-classification.json"),
("IWB restricted","docs/switzerland-iwb-owner-reconciliation-2026-09-28.json"),
("Swisscharge restricted","docs/switzerland-swisscharge-prefix-closeout-2026-09-28.json"),
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

def source_rows(obj):
    """Return only production-priced rows; never recurse through unresolved evidence when a source has explicit evses/stations."""
    if isinstance(obj,dict) and isinstance(obj.get("evses"),list):
        rows=[]
        for x in obj["evses"]:
            if not isinstance(x,dict): continue
            eid=x.get("evseId") or x.get("EvseID")
            if not isinstance(eid,str) and isinstance(x.get("physicalReference"),(str,int)):
                # Swisscharge production collector stores the physical reference separately.
                eid="CH*SUI*E"+str(x.get("physicalReference"))
            if isinstance(eid,str): rows.append((eid,x))
        return rows
    if isinstance(obj,dict) and isinstance(obj.get("stations"),list):
        rows=[]
        for st in obj["stations"]:
            if not isinstance(st,dict): continue
            for cpwrap in st.get("chargePoints") or []:
                if not isinstance(cpwrap,dict): continue
                cp=cpwrap.get("chargePoint") or {}
                tariffs=cpwrap.get("directTariffs") or []
                if not tariffs: continue
                for eid in cp.get("evse_ids") or []:
                    if isinstance(eid,str):
                        rows.append((eid,{
                            "evseId":eid,
                            "stationId":st.get("stationId"),
                            "stationName":st.get("name"),
                            "directTariffs":tariffs,
                        }))
        if rows: return rows
    # Swisscharge and legacy normalized files: recurse only as fallback.
    return ids_from(obj)

def node_has_real_tariff(node):
    """Reject unresolved rows that merely contain null/empty price fields or nested evidence."""
    if not isinstance(node,dict): return False
    if node.get("classification") in ("no_public_direct_tariff","no-public-direct-tariff"):
        return False
    numeric_keys=("pricePerKwh","chfPerKwh","energyPrice","EnergyPrice","EnergyPricePerKwh","pricePerMinute","startFee","sessionFee","ParkingPrice","parkingPrice")
    for k in numeric_keys:
        if isinstance(node.get(k),(int,float)):
            return True
    p=node.get("price")
    if isinstance(p,dict):
        for k in ("EnergyPrice","EnergyPricePerKwh","ParkingPrice","ParkingPricePerHour","Price"):
            if isinstance(p.get(k),(int,float)):
                return True
    if isinstance(node.get("directTariffs"),list) and node["directTariffs"]:
        return True
    if isinstance(node.get("tariffs"),list) and node["tariffs"]:
        return True
    if isinstance(node.get("restricted_segments"),list) and node["restricted_segments"]:
        return True
    if isinstance(node.get("priceTuple"),list) and any(v is not None for v in node["priceTuple"]):
        return True
    # Explicit free tariff is still a deterministic price.
    if node.get("tariff") == 0 or node.get("directPrice") == 0:
        return True
    return False

source_stats=[]
for label,fp in sources:
    p=Path(fp)
    if not p.exists() or p.stat().st_size==0:
        source_stats.append({"label":label,"file":fp,"status":"missing_or_empty","matchedEvseCount":0}); continue
    try: obj=json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        source_stats.append({"label":label,"file":fp,"status":"invalid_json","matchedEvseCount":0}); continue
    seen=set()
    trusted_top_level_evses=isinstance(obj,dict) and isinstance(obj.get("evses"),list)
    for eid,node in source_rows(obj):
        if not isinstance(eid,str) or eid not in evses: continue
        if not trusted_top_level_evses and not node_has_real_tariff(node): continue
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
    rows=[]
    if isinstance(obj,dict) and isinstance(obj.get("evses"),list):
        rows=[x for x in obj["evses"] if isinstance(x,dict) and x.get("classification")=="no_public_direct_tariff"]
    elif label=="IWB restricted":
        rows=((obj.get("classes") or {}).get("restricted_no_auth") or [])
    elif label=="Swisscharge restricted":
        rows=obj.get("classified") or []
    else:
        rows=[node for _,node in ids_from(obj) if isinstance(node,dict) and node.get("classification")=="no_public_direct_tariff"]
    for node in rows:
        eid=node.get("evseId") or node.get("EvseID")
        if not isinstance(eid,str): continue
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
