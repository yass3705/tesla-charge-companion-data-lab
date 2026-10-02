#!/usr/bin/env python3
"""Second-pass audit of France IRVE restricted-access stations.

Input: reports/france/irve-public-access-audit.json
Goal: collapse duplicate station identifiers into physical sites and rank only
closed-group candidates (staff/residents/fleet/customer-only/internal sites).

This remains non-destructive. It does not alter production datasets.
"""
from __future__ import annotations
import json, re, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports/france/irve-public-access-audit.json"
OUT = ROOT / "reports/france/irve-closed-group-second-pass.json"

def norm(v):
    s = unicodedata.normalize("NFKC", str(v or "")).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def slug(v):
    s = norm(v)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode()
    s = re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def site_key(r):
    name = slug(r.get("stationName"))
    addr = slug(r.get("address"))
    if name or addr:
        return f"{name}|{addr}"
    return r.get("stationId","")

HIGH = {
    "staff_only": [
        r"personnel", r"salarie", r"employe", r"collaborateur", r"agent(?:s)?\b",
    ],
    "fleet_only": [
        r"flotte", r"vehicule(?:s)? de service", r"vehicule(?:s)? d entreprise",
        r"parc automobile", r"vehicule(?:s)? societe",
    ],
    "residents_only": [
        r"resident", r"coproprietaire", r"copropriete", r"residence",
    ],
    "internal_corporate_site": [
        r"data valley", r"site industriel", r"usine", r"entrepot", r"depot",
        r"siege social", r"campus", r"centre logistique",
    ],
}

MEDIUM = {
    "customers_only": [
        r"clients? uniquement", r"clientele uniquement", r"reserve(?:e|es)? aux clients",
    ],
    "access_control": [
        r"badge", r"portail", r"digicode", r"autorisation", r"sur demande",
    ],
}

PUBLIC_COUNTER = [
    r"acces libre", r"parking prive a usage public", r"station dediee a la recharge rapide",
    r"24/7", r"aire de service", r"autoroute", r"carrefour", r"lidl", r"aldi",
    r"leclerc", r"auchan", r"intermarche", r"hotel", r"restaurant",
]

def find_matches(text, groups):
    out=[]
    for label, pats in groups.items():
        if any(re.search(p, text) for p in pats):
            out.append(label)
    return out

def main():
    data=json.loads(SRC.read_text(encoding="utf-8"))
    rows=data.get("restrictedOrConditionalStations",[])
    grouped=defaultdict(list)
    for r in rows:
        grouped[site_key(r)].append(r)

    sites=[]
    for key, members in grouped.items():
        first=members[0]
        text=" | ".join(slug(m.get(k)) for m in members for k in
            ["stationName","address","operator","brand","developer","conditionAccess","implantation","observations"])
        high=find_matches(text,HIGH)
        medium=find_matches(text,MEDIUM)
        public_hits=[p for p in PUBLIC_COUNTER if re.search(p,text)]
        reserved=any("reserve" in slug(m.get("conditionAccess")) for m in members)

        score=0
        if reserved: score += 2
        score += 3*len(high)
        score += len(medium)
        # explicit public-use wording reduces confidence but does not erase strong closed-group evidence
        if "parking prive a usage public" in text: score -= 2
        if "acces libre" in text: score -= 2
        if any(re.search(p,text) for p in [r"autoroute",r"aire de service"]): score -= 3

        if high and reserved and score >= 4:
            cls="high_priority_closed_group_candidate"
        elif high and score >= 2:
            cls="medium_priority_closed_group_candidate"
        elif reserved and medium:
            cls="review_reserved_access"
        else:
            cls="restricted_but_no_closed_group_signal"

        sites.append({
            "siteKey": key,
            "stationIds": sorted({m.get("stationId","") for m in members}),
            "stationName": first.get("stationName",""),
            "address": first.get("address",""),
            "operator": first.get("operator",""),
            "brand": first.get("brand",""),
            "developer": first.get("developer",""),
            "conditionAccessValues": sorted({m.get("conditionAccess","") for m in members}),
            "implantationValues": sorted({m.get("implantation","") for m in members}),
            "hoursValues": sorted({m.get("hours","") for m in members}),
            "sourceStationRows": len(members),
            "pdcRowsObserved": sum(int(m.get("pdcCountObserved",0) or 0) for m in members),
            "highSignals": high,
            "mediumSignals": medium,
            "publicCounterSignals": public_hits[:10],
            "score": score,
            "classification": cls,
        })

    priority={"high_priority_closed_group_candidate":3,"medium_priority_closed_group_candidate":2,
              "review_reserved_access":1,"restricted_but_no_closed_group_signal":0}
    sites.sort(key=lambda x:(-priority[x["classification"]],-x["score"],-x["sourceStationRows"],x["operator"].casefold(),x["stationName"].casefold()))

    counts=Counter(x["classification"] for x in sites)
    byop=defaultdict(lambda: Counter())
    for x in sites:
        byop[x["operator"]][x["classification"]]+=1
    ranking=[]
    for op,c in byop.items():
        candidate=c["high_priority_closed_group_candidate"]+c["medium_priority_closed_group_candidate"]
        if candidate or c["review_reserved_access"]:
            ranking.append({
                "operator":op,
                "highPrioritySites":c["high_priority_closed_group_candidate"],
                "mediumPrioritySites":c["medium_priority_closed_group_candidate"],
                "reservedReviewSites":c["review_reserved_access"],
                "candidateSites":candidate,
            })
    ranking.sort(key=lambda x:(-x["highPrioritySites"],-x["candidateSites"],-x["reservedReviewSites"],x["operator"].casefold()))

    out={
        "schemaVersion":"1.0.0",
        "dataset":"france-irve-closed-group-second-pass",
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "source":"reports/france/irve-public-access-audit.json",
        "policy":{
            "nonDestructive":True,
            "physicalSiteClustering":True,
            "automaticProductionExclusion":False,
            "closedGroupSignalsOnly":True,
        },
        "counts":{
            "restrictedStationRowsInput":len(rows),
            "uniquePhysicalSites":len(sites),
            "byClassification":dict(counts),
            "candidateSites":counts["high_priority_closed_group_candidate"]+counts["medium_priority_closed_group_candidate"],
        },
        "operatorRanking":ranking,
        "candidateSites":[x for x in sites if x["classification"]!="restricted_but_no_closed_group_signal"],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out["counts"],ensure_ascii=False,indent=2))
    for x in ranking[:30]:
        print(json.dumps(x,ensure_ascii=False))

if __name__=="__main__":
    main()
