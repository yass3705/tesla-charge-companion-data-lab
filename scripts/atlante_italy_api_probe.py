#!/usr/bin/env python3
"""Read-only probe of myAtlante public app backend for Atlante-operated Italy locations.

The API subscription key is supplied only at runtime through GitHub Actions and is
never printed or persisted. No account/authentication/session endpoint is called.
"""
from __future__ import annotations

import json, math, os, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE="https://pdefweushaapiam01.azure-api.net/app-backend/v1"
TENANT="390c3ff9-b41c-42dc-aa48-1dd51ad6ce39"
MAP=f"{BASE}/tenants/{TENANT}/map-locations"
DETAIL=f"{BASE}/tenants/{TENANT}/locations/{{location_id}}"
TARIFF=f"{DETAIL}/tariffs"
APP_VERSION="2.1.0"
OUT=Path("data/reports/atlante_italy_api_probe.json")
CPO_CANDIDATES=("ITATL","ITATE","ATL","ATE")


def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def req(url,key):
    h={"Ocp-Apim-Subscription-Key":key,"Accept":"application/json","Accept-Language":"it-IT","X-App-Version":APP_VERSION,"X-App-Platform":"android","User-Agent":f"myAtlante/{APP_VERSION} (Android; TCC Italy research)"}
    r=urllib.request.Request(url,headers=h,method="GET")
    with urllib.request.urlopen(r,timeout=45) as x:
        return json.loads(x.read().decode("utf-8"))

def map_url(cpo):
    q=urllib.parse.urlencode({"latLongBottomLeft":"35,6","latLongTopRight":"48,19","evseTypes":"AC,DC,HPC","locationStatus":"ALL","connectorTypes":"CCS,CHADEMO,TYPE2","includeCpos":cpo})
    return f"{MAP}?{q}"

def fnum(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None

def summarize_tariffs(rows):
    out=[]
    for t in rows if isinstance(rows,list) else []:
        ids=t.get("identifiers") or {}
        pcs=[]
        for p in t.get("priceComponents") or []:
            price=p.get("price") or {}
            pcs.append({
                "dimension":p.get("priceDimension"),
                "currency":p.get("currency"),
                "inclVat":fnum(price.get("incl_vat")),
                "conditionsPresent":bool(p.get("conditions")),
                "surchargeName":p.get("surchargeName"),
                "validity":p.get("validity"),
            })
        out.append({"evseId":ids.get("evseId"),"connectorId":ids.get("connectorId"),"priceComponents":pcs})
    return out

def main():
    key=os.environ.get("ATLANTE_API_SUBSCRIPTION_KEY","").strip()
    if not key: raise SystemExit("ATLANTE_API_SUBSCRIPTION_KEY missing")
    probes=[]; chosen=None; chosen_rows=[]
    for cpo in CPO_CANDIDATES:
        try:
            p=req(map_url(cpo),key)
            rows=p.get("locations") or []
            it=[x for x in rows if str(x.get("countryCode") or "").upper()=="IT"]
            counts=Counter((str(x.get("partyId") or "UNKNOWN").upper(),str(x.get("operatorName") or x.get("name") or "UNKNOWN")) for x in it)
            probes.append({"cpo":cpo,"httpOk":True,"locations":len(rows),"italyLocations":len(it),"partyOperatorCounts":[{"partyId":k[0],"operator":k[1],"count":v} for k,v in counts.most_common(20)]})
            atl=[x for x in it if str(x.get("partyId") or "").upper() in {"ATL","ATE"} or "ATLANTE" in str(x.get("operatorName") or "").upper()]
            if atl and chosen is None:
                chosen=cpo; chosen_rows=atl
        except Exception as e:
            probes.append({"cpo":cpo,"httpOk":False,"errorType":type(e).__name__})
    if not chosen_rows:
        raise RuntimeError("No Atlante-operated Italy locations found for candidate CPO codes")
    samples=[]
    for s in chosen_rows[:8]:
        lid=str(s.get("id") or "")
        if not lid: continue
        d=req(DETAIL.format(location_id=urllib.parse.quote(lid,safe='')),key)
        t=req(TARIFF.format(location_id=urllib.parse.quote(lid,safe='')),key)
        evses=[]
        for e in d.get("evses") or []:
            evses.append({"evseId":e.get("evseId"),"status":e.get("evseStatus"),"connectors":[{"connectorId":c.get("evseConnectorId"),"externalConnectorId":c.get("externalConnectorId"),"type":c.get("evseCommonConnectorType"),"powerType":c.get("evsePowerType"),"maxPowerKw":fnum(c.get("max_electric_power"))} for c in e.get("connectors") or []]})
        samples.append({"summary":{"id":lid,"countryCode":s.get("countryCode"),"partyId":s.get("partyId"),"operatorName":s.get("operatorName"),"displayName":s.get("displayName"),"coordinates":s.get("coordinates")},"detail":{"id":d.get("id"),"countryCode":d.get("countryCode"),"partyId":d.get("partyId"),"operatorName":d.get("operatorName"),"coordinates":d.get("coordinates"),"evses":evses},"tariffs":summarize_tariffs(t)})
    payload={"generatedAt":now(),"security":{"accountCredentialsUsed":False,"subscriptionKeyPersisted":False,"authOrChargingEndpointsCalled":False},"source":{"backend":BASE,"tenantId":TENANT,"appVersion":APP_VERSION},"candidateCpoProbes":probes,"selectedCpo":chosen,"selectedItalyAtlanteLocationCount":len(chosen_rows),"samples":samples}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"selectedCpo":chosen,"selectedItalyAtlanteLocationCount":len(chosen_rows),"probes":probes,"sampleCount":len(samples)},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
