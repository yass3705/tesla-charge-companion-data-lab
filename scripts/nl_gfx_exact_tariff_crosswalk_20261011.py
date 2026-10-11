#!/usr/bin/env python3
"""Check 738 unpriced GFX EVSEs for precise re-exports elsewhere in DOT-NL.

Never adopt an eMSP or wrong CPO price. This only audits exact EVSE,
connector standard, <= 5m GPS and power, with proof of original tariff
presence and an unambiguous calculated result in another national CPO source.
No in-place dataset mutation or inferred station/area pricing.
"""
from __future__ import annotations
import collections,csv,datetime as dt,gzip,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dotnl_netherlands_runtime as eng
SNAP=ROOT/"data/national/netherlands_dotnl/normalized.json.gz"
BASE=ROOT/"reports/netherlands/dotnl-active-type2-ccs-unpriced-connectors-latest.csv"
REPORT=ROOT/"reports/netherlands/nl-gfx-exact-crossparty-pricing-audit-latest.json"
DETAIL=ROOT/"reports/netherlands/nl-gfx-exact-crossparty-pricing-candidates-latest.csv"

def distance(lat1,lon1,lat2,lon2):
    r=6371000.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    a=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 2*r*math.asin(min(1,math.sqrt(a)))

def main():
    with BASE.open(newline="",encoding="utf8") as f:rows=[r for r in csv.DictReader(f) if r["partyId"]=="GFX" and r["gapType"]=="NO_TARIFF_IN_DOTNL"]
    assert len(rows)==738,len(rows)
    wanted={r["evseId"] for r in rows}
    with gzip.open(SNAP,"rt",encoding="utf8") as f:d=json.load(f)
    tariffs=d.get("tariffs") or {}
    current=eng.date_of(d.get("generatedAt")) or dt.datetime.now(dt.timezone.utc).date()
    matches=collections.defaultdict(list)
    for site in d.get("stations") or []:
        lat=eng.fnum((site.get("coordinates") or {}).get("latitude"))
        lon=eng.fnum((site.get("coordinates") or {}).get("longitude"))
        if lat is None or lon is None:continue
        party=str(site.get("partyId") or "")
        for e in site.get("evses") or []:
            evse_id=str(e.get("evseId") or "")
            if evse_id not in wanted:continue
            for c in e.get("connectors") or []:
                matches[evse_id].append({"partyId":party,"stationId":site.get("stationId"),"connectorId":str(c.get("id") or ""),
                   "standard":str(c.get("standard") or ""),"powerKw":eng.fnum(c.get("powerKw")),
                   "status":str(e.get("status") or ""),"latitude":lat,"longitude":lon,"tariffKeys":c.get("tariffKeys") or []})
    computed=[];counts=collections.Counter()
    cache={};select={};choose_stats={"unsupportedReasons":collections.Counter(),"ambiguousTariffConnectors":0}
    for row in rows:
        origin=(row["partyId"],row["stationId"],row["connectorId"])
        lat=float(row["latitude"]);lon=float(row["longitude"]);power=eng.fnum(row["powerKw"])
        cross=[e for e in matches[row["evseId"]] if e["partyId"]!="GFX"]
        if not cross:
            counts["not_reexported_to_other_party"]+=1
            continue
        counts["has_crossparty_evse_id"]+=1
        plausible=[]
        for e in cross:
            dist=distance(lat,lon,e["latitude"],e["longitude"])
            p=e["powerKw"]
            power_ok=(power is None or p is None or (abs(power-p)<=max(power,p)*.1))
            plug_ok=(row["standard"]==e["standard"])
            if not (dist<=5 and power_ok and plug_ok):
                continue
            key,_,reason=eng.choose_tariff(e["tariffKeys"],tariffs,current,choose_stats,cache,select)
            plausible.append((e,dist,key,reason))
        if len(plausible)!=1:
            counts["zero_or_multiple_exact_crossparty_candidates"]+=1
            continue
        candidate,dist,key,reason=plausible[0]
        if not key:
            counts["exact_crossparty_but_unpriced_or_ambiguous"]+=1
        else:
            counts["exact_crossparty_price_candidate"]+=1
        computed.append({"gfxStation":row["stationId"],"gfxEvseId":row["evseId"],"gfxConnectorId":row["connectorId"],
          "gfxName":row["stationName"],"gfxCity":row["city"],"plug":row["standard"],
          "crossPartyId":candidate["partyId"],"crossStationId":candidate["stationId"],
          "crossConnectorId":candidate["connectorId"],"distanceMeters":round(dist,2),
          "crossTariffKey":key or "", "crossTariffStatus":"compiled" if key else str(reason),
          "cpoSourceIdentityMustBeVerified":True,"autoPricePromotion":False})
    with DETAIL.open("w",newline="",encoding="utf8") as f:
        fieldnames=list(computed[0]) if computed else ["gfxEvseId"]
        w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader();w.writerows(computed)
    report={"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "sourceSnapshotAt":d.get("generatedAt"),"targetCpoPartyId":"GFX",
            "unpricedGfxConnectors":len(rows),"targetEvseIds":len(wanted),
            "countByExactCrossPartyMatch":dict(counts),
            "candidateRows":len(computed),
            "candidateSamples":computed[:25],
            "conditions":"Exact physical EVSE ID AND same connector standard AND <=5m AND max 10% power difference; one other-party candidate only. Price would require confirming actual direct CPO identity; no eMSP.",
            "noTariffPromoted":True,"detail":"reports/netherlands/nl-gfx-exact-crossparty-pricing-candidates-latest.csv"}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"totals":dict(counts),"unpriced":len(rows),"crossCandidates":len(computed),"sample":computed[:4]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
