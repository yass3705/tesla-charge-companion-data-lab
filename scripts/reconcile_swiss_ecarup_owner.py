#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
ECAR=Path("data/switzerland/ecarup-public-stations.json")
OUT=Path("data/switzerland/ecarup-owner-direct-tariffs.json")
FINAL=Path("docs/switzerland-ecarup-owner-reconciliation-2026-09-28.json")
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
pub=json.loads(ECAR.read_text(encoding="utf-8"))

current={}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
        eid=x.get("EvseID")
        if owner=="CH*ECU" and isinstance(eid,str): current[eid]=x
        for v in x.values(): walk(v,owner)
    elif isinstance(x,list):
        for v in x: walk(v,owner)
walk(nat)

def norm(s): return "".join(c for c in (s or "").upper() if c.isalnum())

connectors={}
ambiguous={}
for st in pub.get("stations") or []:
    for c in st.get("Connectors") or []:
        hid=(c.get("Hubject") or {}).get("ID")
        if not hid: continue
        k=norm(hid)
        rec={
          "hubjectId":hid,"stationId":st.get("ID"),"stationName":st.get("Name"),
          "operatorName":((st.get("ContactDetails") or {}).get("OperatorName") or "").strip(),
          "address":st.get("Address"),"latitude":st.get("Latitude"),"longitude":st.get("Longitude"),
          "connectorId":c.get("Id"),"connectorName":c.get("Name"),
          "accessType":c.get("AccessType"),"state":c.get("State"),"maxPowerW":c.get("MaxPower"),
          "price":c.get("Price")
        }
        if k in connectors:
            ambiguous.setdefault(k,[connectors[k]]).append(rec)
        else: connectors[k]=rec

rows=[]; priced=0; explicit_no_public=0; unresolved=[]
for eid,rec in sorted(current.items()):
    k=norm(eid)
    if k in ambiguous:
        unresolved.append({"evseId":eid,"reason":"ambiguous_multiple_ecarup_connectors","candidates":ambiguous[k]})
        continue
    c=connectors.get(k)
    if c:
        price=c.get("price")
        if c.get("accessType")==0 and isinstance(price,dict):
            rows.append({"evseId":eid,"classification":"priced_public_direct","nationalRecord":rec,"ecarup":c})
            priced+=1
        elif c.get("accessType")!=0:
            rows.append({"evseId":eid,"classification":"restricted_or_nonpublic_connector","nationalRecord":rec,"ecarup":c})
            explicit_no_public+=1
        else:
            unresolved.append({"evseId":eid,"reason":"public_connector_without_price","nationalRecord":rec,"ecarup":c})
        continue
    if rec.get("Accessibility")=="Restricted access" and not (rec.get("AuthenticationModes") or []):
        rows.append({"evseId":eid,"classification":"restricted_no_public_direct_tariff","nationalRecord":rec})
        explicit_no_public+=1
    else:
        unresolved.append({"evseId":eid,"reason":"no_exact_ecarup_hubject_match","nationalRecord":rec})

now=datetime.now(timezone.utc).isoformat()
payload={
 "schemaVersion":1,"country":"CH","cpo":"eCarUp","operatorId":"CH*ECU","generatedAt":now,
 "source":{"national":NATIONAL,"ecarup":"data/switzerland/ecarup-public-stations.json"},
 "counts":{"nationalEvseCount":len(current),"exactConnectorKeyCount":sum(1 for e in current if norm(e) in connectors and norm(e) not in ambiguous),
           "pricedEvseCount":priced,"classifiedNoPublicDirectTariffCount":explicit_no_public,
           "unresolvedEvseCount":len(unresolved),"ambiguousNormalizedConnectorKeyCount":len(ambiguous)},
 "policy":"Exact current CH*ECU owner scope. eCarUp public connector Hubject ID matched by punctuation-insensitive 1:1 normalization only. Public direct price requires accessType=0 and explicit Price object. Restricted/no-auth records are no-public-direct. No coordinate tariff extrapolation.",
 "evses":rows,"unresolved":unresolved
}
OUT.parent.mkdir(parents=True,exist_ok=True);FINAL.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
final={"schemaVersion":1,"country":"CH","cpo":"eCarUp","operatorId":"CH*ECU","status":"complete" if not unresolved else "partial",
       "updatedAt":now,**payload["counts"],"method":"Swiss national CH*ECU owner scope + exact eCarUp public Android API connector IDs and prices",
       "policy":payload["policy"],"productionSource":str(OUT)}
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
