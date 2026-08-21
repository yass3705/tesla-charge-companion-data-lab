#!/usr/bin/env python3
"""Validate current official Connect&go Sel et Vermois tariff rules."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36";HOME="https://seletvermois.connectandgo.fr/";TARIFFS="https://seletvermois.connectandgo.fr/tarifs/"
def fetch(u):
 req=urllib.request.Request(u,headers={"User-Agent":UA,"Accept":"text/html,*/*","Accept-Language":"fr-FR,fr;q=0.9"});
 with urllib.request.urlopen(req,timeout=60) as r:return int(getattr(r,"status",200)),r.read(),r.geturl()
def plain(b):
 s=b.decode("utf-8",errors="replace");s=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",s);s=re.sub(r"(?s)<[^>]+>"," ",s);s=html.unescape(s).replace("\xa0"," ");return re.sub(r"\s+"," ",s).strip()
def norm(s):
 import unicodedata
 s=unicodedata.normalize("NFKD",s or "");s="".join(c for c in s if not unicodedata.combining(c));return re.sub(r"\s+"," ",s.lower().replace("’","'").replace(" "," ")).strip()
def req(t,*xs):
 n=norm(t);m=[x for x in xs if norm(x) not in n]
 if m:raise RuntimeError("Sel et Vermois evidence missing: "+", ".join(m))
def now():return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--out",default="out/connectandgo_sel_vermois");a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
 hs,hr,hf=fetch(HOME);ts,tr,tf=fetch(TARIFFS)
 if hs!=200 or ts!=200:raise RuntimeError(f"HTTP failure home={hs} tariffs={ts}")
 h,t=plain(hr),plain(tr);req(h,"28 bornes","11 communes","22 kW","25 kW","120 kW","Freshmile","100% verte")
 req(t,"0,27 € par kWh entamé et 0,025 € par minute","0,45 € par kWh entamé et 0,025 € par minute","après 3h de branchement, 0,16 € par minute sans consommation","après 1h de branchement, 0,20 € par minute sans consommation","0,25 € par kWh entamé","3€ /mois","0,43 € par kWh entamé et 0,02 € par minute","après 4h de branchement, 0,13 € par minute sans consommation","après 1h30 de branchement, 0,15 € par minute sans consommation","0,20 € par kWh entamé")
 p={"schemaVersion":"1.0.0","dataset":"connectandgo-sel-vermois-official-grandest","generatedAt":now(),"operator":"Connect&go - Sel et Vermois","serviceOperator":"Freshmile","country":"FR","region":"Grand Est","department":"Meurthe-et-Moselle","classification":{"localPublicNetwork":True,"directPublishedTariff":True,"energyAndTimeBased":True,"powerDependent":True,"dayNightDependent":True,"memberTariffAvailable":True,"idleSurcharge":True,"roamingMayDiffer":True},"network":{"publishedPlannedStationCount":28,"publishedMunicipalityCount":11,"publishedConnectorPowerKw":[22,25,120],"freshmileAccess":True,"electricity100PercentGreen":True},"operatorDirect":{"withoutSubscription":{"monthlyEur":0.0,"day":{"window":"08:30-20:00","below30Kw":{"eurPerKwh":0.27,"eurPerMinute":0.025},"above30Kw":{"eurPerKwh":0.45,"eurPerMinute":0.025}},"night":{"window":"20:00-08:30","below30Kw":{"eurPerKwh":0.25,"eurPerMinute":0.0},"above30Kw":{"eurPerKwh":0.45,"eurPerMinute":0.025}},"idle":{"below30Kw":{"afterMinutes":180,"eurPerMinute":0.16,"condition":"without_consumption"},"above30Kw":{"afterMinutes":60,"eurPerMinute":0.20,"condition":"without_consumption"}}},"withSubscription":{"monthlyEur":3.0,"day":{"window":"09:00-20:00","below30Kw":{"eurPerKwh":0.25,"eurPerMinute":0.025},"above30Kw":{"eurPerKwh":0.43,"eurPerMinute":0.02}},"night":{"window":"20:00-09:00","below30Kw":{"eurPerKwh":0.20,"eurPerMinute":0.0},"above30Kw":{"eurPerKwh":0.43,"eurPerMinute":0.02}},"idle":{"below30Kw":{"afterMinutes":240,"eurPerMinute":0.13,"condition":"without_consumption"},"above30Kw":{"afterMinutes":90,"eurPerMinute":0.15,"condition":"without_consumption"}}}},"tccDecision":{"operatorValidated":True,"directTariffClassable":True,"subscriptionSeparateOffer":True,"roamingSeparate":True,"idleFeeMustBeModeled":True},"sourceEvidence":{"officialOnly":True,"homeUrl":hf,"homeHttpStatus":hs,"tariffsUrl":tf,"tariffsHttpStatus":ts,"homeSha256":hashlib.sha256(hr).hexdigest(),"tariffsSha256":hashlib.sha256(tr).hexdigest()},"publicationStatus":"validated_candidate"}
 sig={k:p[k] for k in ("network","operatorDirect","tccDecision")};p["sourceEvidence"]["relevantTariffFingerprintSha256"]=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();(o/"connectandgo_sel_vermois_official_grandest.json").write_text(json.dumps(p,ensure_ascii=False,indent=2)+"\n");(o/"SUMMARY.md").write_text("# Connect&go — Sel et Vermois\n\nOfficial Freshmile-backed local grid validated for public and 3 EUR/month subscriber offers, including day/night, power tiers and idle fees.\n")
if __name__=="__main__":main()
