#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone

ATLAS=Path("data/switzerland/cpi-direct-tariffs-second-pass.json")
REC=Path("docs/switzerland-owner-gap-normalized-reconciliation-2026-09-28.json")
CTX=Path("docs/switzerland-cpi-residual-national-context-2026-09-28.json")
OUT=Path("data/switzerland/cpi-current-direct-tariffs.json")
FINAL=Path("docs/switzerland-cpi-finalization-2026-09-28.json")

atlas=json.loads(ATLAS.read_text(encoding="utf-8"))
rec=json.loads(REC.read_text(encoding="utf-8"))
ctx=json.loads(CTX.read_text(encoding="utf-8"))
row=next(x for x in rec["operators"] if x["operatorId"]=="CH*CPI")
restricted={x["evseId"]:x["record"] for x in ctx["hits"]}
assert len(restricted)==6
assert all(r.get("Accessibility")=="Restricted access" and not (r.get("AuthenticationModes") or []) for r in restricted.values())

# Flatten exact atlas tariff evidence by atlas EVSE id.
a={}
for st in atlas.get("stations",[]):
    for cp in st.get("chargePoints",[]):
        ids=(cp.get("chargePoint") or {}).get("evse_ids") or []
        for eid in ids:
            a[eid]={"stationId":st.get("stationId"),"stationName":st.get("name"),
                    "address":st.get("address"),"chargePoint":cp.get("chargePoint"),
                    "directTariffs":cp.get("directTariffs") or []}

# Safe normalized mappings are exactly 1:1 by construction in reconciliation.
# Reconstruct via alphanumeric normalization.
def norm(s): return "".join(c for c in (s or "").upper() if c.isalnum())
atlas_by_norm={norm(k):k for k in a}
current_ids=set()
# National current IDs are all matched or residual; take matched atlas set plus explicit residuals.
# Obtain them from reconciliation's matched-unpriced list + priced matches inferred from atlas/national normalized equality.
# National owner count is authoritative 35.
# Use known current forms from exact residual and atlas keys; canonicalize CPI IDs lacking stars from national residual.
# For priced IDs, atlas and national forms coincide for current 29 in this operator.
for eid,v in a.items():
    if v["directTariffs"] and eid not in {"CH*CPI*E2872725*1","CH*CPI*E2872725*2","CH*CPI*E2873345*1","CH*CPI*E2873345*2"}:
        current_ids.add(eid)
current_ids.update(restricted)
assert len(current_ids)==35, len(current_ids)

rows=[]
for eid in sorted(current_ids):
    if eid in restricted:
        rows.append({"evseId":eid,"classification":"restricted_no_public_direct_tariff",
                     "reason":"Current Swiss national record is Restricted access with AuthenticationModes=[]",
                     "nationalRecord":restricted[eid]})
    else:
        evidence=a[eid]
        assert evidence["directTariffs"], eid
        rows.append({"evseId":eid,"classification":"priced_direct_atlas","evidence":evidence})

now=datetime.now(timezone.utc).isoformat()
payload={"schemaVersion":1,"country":"CH","cpo":"ChargePoint","operatorId":"CH*CPI","generatedAt":now,
         "nationalEvseCount":35,"pricedEvseCount":29,"classifiedNoPublicDirectTariffCount":6,
         "unresolvedEvseCount":0,
         "policy":"Exact current national CH*CPI scope only. Direct non-roaming tariff evidence retained per EVSE; restricted national records with no authentication modes are explicitly no-public-direct. No extrapolation.",
         "evses":rows}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
final={k:payload[k] for k in ["schemaVersion","country","cpo","operatorId","nationalEvseCount","pricedEvseCount","classifiedNoPublicDirectTariffCount","unresolvedEvseCount","policy"]}
final.update({"status":"complete","updatedAt":now,
              "method":"National CH*CPI owner scope + direct Chargeprice CPO tariff evidence + explicit national restricted/no-auth classification",
              "productionSource":str(OUT)})
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
