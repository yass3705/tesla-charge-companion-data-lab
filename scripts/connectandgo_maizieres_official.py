#!/usr/bin/env python3
"""Validate current official Connect&go Maizières-lès-Metz tariff rules conservatively."""
from __future__ import annotations

import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
HOME="https://maizieres-les-metz.connectandgo.fr/"
TARIFFS="https://maizieres-les-metz.connectandgo.fr/tarifs/"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*","Accept-Language":"fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req,timeout=60) as r: return int(getattr(r,"status",200)),r.read(),r.geturl()

def plain(raw):
    s=raw.decode("utf-8",errors="replace"); s=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",s); s=re.sub(r"(?s)<[^>]+>"," ",s); s=html.unescape(s).replace("\xa0"," "); return re.sub(r"\s+"," ",s).strip()

def norm(s):
    import unicodedata
    s=unicodedata.normalize("NFKD",s or ""); s="".join(c for c in s if not unicodedata.combining(c)); return re.sub(r"\s+"," ",s.lower().replace("’","'").replace(" "," ")).strip()

def require(text,*items):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError("Connect&go Maizieres official evidence missing: "+", ".join(missing))

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default="out/connectandgo_maizieres"); args=ap.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    hs,hraw,hfinal=fetch(HOME); ts,traw,tfinal=fetch(TARIFFS)
    if hs!=200 or ts!=200: raise RuntimeError(f"HTTP failure home={hs} tariffs={ts}")
    htext,ttext=plain(hraw),plain(traw)
    require(htext,"Neuf bornes de recharge","22 kW","25 kW","50 kW","Freshmile")
    require(ttext,
      "SANS ABONNEMENT","0€ /mois","De 8h30 à 20h : 0,25 € par kWh entamé et 0,025 € par minute","Après 3h de branchement, 0,16 € par minute sans consommation","De 20h à 8h30 : 0,24 € par kWh entamé",
      "AVEC ABONNEMENT","3€ /mois","De 9h à 20h : 0,24 € par kWh entamé et 0,02 € par minute","Après 4h de branchement, 0,13 € par heure sans consommation","De 20h à 9h : 0,2 € par kWh entamé","La tarification continue tant que le véhicule est branché")
    payload={
      "schemaVersion":"1.0.0","dataset":"connectandgo-maizieres-official-grandest","generatedAt":now(),"operator":"Connect&go - Maizières-lès-Metz","serviceOperator":"Freshmile","country":"FR","region":"Grand Est","department":"Moselle",
      "classification":{"localPublicNetwork":True,"directPublishedTariff":True,"energyAndTimeBased":True,"dayNightDependent":True,"memberTariffAvailable":True,"idleSurcharge":True,"roamingMayDiffer":True,"publishedTariffScope":"below30Kw"},
      "network":{"homepagePublishedStationCount":9,"publishedConnectorPowerKw":[22,25,50],"freshmileAccess":True},
      "operatorDirect":{
        "withoutSubscription":{"monthlyEur":0.0,"day":{"window":"08:30-20:00","below30Kw":{"eurPerKwh":0.25,"eurPerMinute":0.025}},"night":{"window":"20:00-08:30","below30Kw":{"eurPerKwh":0.24,"eurPerMinute":0.0}},"idle":{"below30Kw":{"afterMinutes":180,"eurPerMinute":0.16,"condition":"without_consumption"}}},
        "withSubscription":{"monthlyEur":3.0,"day":{"window":"09:00-20:00","below30Kw":{"eurPerKwh":0.24,"eurPerMinute":0.02}},"night":{"window":"20:00-09:00","below30Kw":{"eurPerKwh":0.20,"eurPerMinute":0.0}},"idle":{"below30Kw":{"afterMinutes":240,"eurPerHourAsPublished":0.13,"condition":"without_consumption","sourceUnit":"hour"}}}
      },
      "rules":{"billingContinuesWhileConnected":True,"higherPowerTariffNotPublishedOnCurrentPage":True,"subscriptionIdleUnitAnomaly":True,"subscriptionIdleUnitNote":"Official page explicitly says 0.13 EUR per hour after 4h; sibling Connect&go networks usually publish per-minute idle fees. Do not silently normalize."},
      "tccDecision":{"operatorValidated":True,"publicTariffClassableBelow30Kw":True,"subscriptionEnergyTimeClassableBelow30Kw":True,"subscriptionFullyClassableForLongIdleSessions":False,"manualCheckNeeded":"Confirm the published 0.13 EUR/hour subscriber idle unit before ranking long sessions; do not convert it to per-minute without evidence.","roamingSeparate":True},
      "sourceEvidence":{"officialOnly":True,"homeUrl":hfinal,"homeHttpStatus":hs,"tariffsUrl":tfinal,"tariffsHttpStatus":ts,"homeSha256":hashlib.sha256(hraw).hexdigest(),"tariffsSha256":hashlib.sha256(traw).hexdigest()},"publicationStatus":"validated_candidate_with_unit_anomaly"}
    sig={k:payload[k] for k in ("network","operatorDirect","rules","tccDecision")}; payload["sourceEvidence"]["relevantTariffFingerprintSha256"]=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    (out/"connectandgo_maizieres_official_grandest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    (out/"SUMMARY.md").write_text("# Connect&go — Maizières-lès-Metz\n\nOfficial below-30-kW public tariff is validated. The 3 EUR/month subscriber energy/time tariff is also explicit, but its idle surcharge is published as 0.13 EUR per hour after 4h, unlike the per-minute wording used by sibling Connect&go networks. This unit is preserved exactly and flagged for manual verification; no silent correction is made.\n")

if __name__=="__main__": main()
