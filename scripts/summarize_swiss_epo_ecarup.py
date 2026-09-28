#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter
p=Path("docs/switzerland-epo-ecarup-targeted-audit-2026-09-28.json")
j=json.loads(p.read_text(encoding="utf-8"))
withcand=withpriced=unique30=within10=0
ops=Counter(); resolvable=[]; ambiguous=[]; none=[]
for r in j.get("rows",[]):
    cands=r.get("candidates") or []
    if cands: withcand+=1
    priced=[]
    for s in cands:
        ops[s.get("operatorName") or ""]+=1
        for c in s.get("connectors") or []:
            if c.get("accessType")==0 and c.get("energyPrice") is not None:
                priced.append((s,c))
    if priced: withpriced+=1
    close=[s for s in cands if s.get("distanceMeters") is not None and s["distanceMeters"]<=30]
    if len(close)==1: unique30+=1
    if close and close[0].get("distanceMeters",999)<=10: within10+=1
    # Safe auto-resolve candidate only if one station within 20m and all public priced connectors on it agree on energy/currency/parking.
    near=[s for s in cands if s.get("distanceMeters") is not None and s["distanceMeters"]<=20]
    if len(near)==1:
        s=near[0]
        pubs=[c for c in s.get("connectors") or [] if c.get("accessType")==0 and c.get("energyPrice") is not None]
        tariffs={(c.get("energyPrice"),str(c.get("currency") or "").upper(),c.get("parkingPrice")) for c in pubs}
        if pubs and len(tariffs)==1:
            resolvable.append({"evseId":r.get("evseId"),"chargingStationId":r.get("chargingStationId"),"nationalAddress":r.get("nationalAddress"),
                               "distanceMeters":s.get("distanceMeters"),"stationId":s.get("stationId"),"stationName":s.get("name"),
                               "operatorName":s.get("operatorName"),"tariff":{"energyPrice":next(iter(tariffs))[0],"currency":next(iter(tariffs))[1],"parkingPrice":next(iter(tariffs))[2]},
                               "publicConnectors":pubs})
            continue
    if cands: ambiguous.append({"evseId":r.get("evseId"),"candidateCount":len(cands),"nearest":cands[:3]})
    else:none.append({"evseId":r.get("evseId"),"address":r.get("nationalAddress"),"geo":r.get("geo")})
out={"nationalEvseCount":j.get("nationalEvseCount"),"uniqueQueryCount":j.get("uniqueQueryCount"),"errorCount":j.get("errorCount"),
     "withCandidateWithin100m":withcand,"withPricedPublicCandidate":withpriced,"uniqueCandidateWithin30m":unique30,"nearestWithin10m":within10,
     "safeResolvableWithin20mCount":len(resolvable),"topOperators":ops.most_common(40),
     "safeResolvable":resolvable,"ambiguousCount":len(ambiguous),"noCandidateCount":len(none),
     "ambiguousSample":ambiguous[:30],"noCandidateSample":none[:30]}
Path("docs/switzerland-epo-ecarup-targeted-summary-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k not in ("safeResolvable","ambiguousSample","noCandidateSample")},ensure_ascii=False,indent=2))
