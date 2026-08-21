#!/usr/bin/env python3
"""Validate current official Connect&go Yutz tariff rules without correcting source ambiguities."""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"; HOME="https://yutz.connectandgo.fr/"; TARIFFS="https://yutz.connectandgo.fr/tarifs/"
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*","Accept-Language":"fr-FR,fr;q=0.9"});
 with urllib.request.urlopen(req,timeout=60) as r:return int(getattr(r,"status",200)),r.read(),r.geturl()
def plain(raw):
 s=raw.decode("utf-8",errors="replace");s=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",s);s=re.sub(r"(?s)<[^>]+>"," ",s);s=html.unescape(s).replace("\xa0"," ");return re.sub(r"\s+"," ",s).strip()
def norm(s):
 import unicodedata
 s=unicodedata.normalize("NFKD",s or "");s="".join(c for c in s if not unicodedata.combining(c));return re.sub(r"\s+"," ",s.lower().replace("’","'").replace(" "," ")).strip()
def require(text,*items):
 n=norm(text);m=[x for x in items if norm(x) not in n]
 if m:raise RuntimeError("Connect&go Yutz official evidence missing: "+", ".join(m))
def now():return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--out",default="out/connectandgo_yutz");args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 hs,hraw,hfinal=fetch(HOME);ts,traw,tfinal=fetch(TARIFFS)
 if hs!=200 or ts!=200:raise RuntimeError(f"HTTP failure home={hs} tariffs={ts}")
 htext,ttext=plain(hraw),plain(traw)
 require(htext,"Six bornes","22 kW","25 kW","50 kW","Delmonicos")
 require(ttext,"Connect&go - Delmonicos","SANS ABONNEMENT","0€ /mois","0,38 €/kWh","0,53 €/kWh","15 min après la fin de la charge complète","0,10 € la minute","0,20 € la minute","0,29 €/kWh","14h consécutives de connexion","10 €TTC/heure","au-delà de 1h30","AVEC ABONNEMENT","4€ /mois","0,33 €/kWh","0,51 €/kWh","30 minutes après la fin de la charge complète","0,10 cts la minute","0,20 cts la minute","0,25 €/kWh")
 payload={"schemaVersion":"1.0.0","dataset":"connectandgo-yutz-official-grandest","generatedAt":now(),"operator":"Connect&go - Yutz","serviceOperator":"Delmonicos","country":"FR","region":"Grand Est","department":"Moselle",
 "classification":{"localPublicNetwork":True,"directPublishedTariff":True,"energyBased":True,"dayNightDependent":True,"memberTariffAvailable":True,"idleSurcharge":True,"roamingMayDiffer":True},
 "network":{"publishedStationCount":6,"publishedConnectorPowerKw":[22,25,50],"delmonicosAccess":True},
 "operatorDirect":{
  "withoutSubscription":{"monthlyEur":0.0,"day":{"upTo25Kw":{"eurPerKwh":0.38},"from50Kw":{"eurPerKwh":0.53},"postFullChargeIdle":{"graceMinutes":15,"upTo25KwEurPerMinute":0.10,"at50KwEurPerMinute":0.20}},"night":{"upTo25Kw":{"eurPerKwh":0.29},"from50Kw":{"eurPerKwh":0.53},"idle":{"upTo25Kw":{"afterConnectionMinutes":840,"eurPerHour":10.0},"at50Kw":{"afterConnectionMinutes":90,"eurPerMinute":0.20,"afterConnectionMinutesSecondTier":180,"secondTierEurPerHour":10.0}}}},
  "withSubscription":{"monthlyEur":4.0,"day":{"upTo25Kw":{"eurPerKwh":0.33},"upTo50Kw":{"eurPerKwh":0.51},"postFullChargeIdle":{"graceMinutes":30,"sourceTextUpTo25Kw":"0.10 cts/min","sourceText50Kw":"0.20 cts/min","unitAmbiguous":True}},"night":{"upTo25Kw":{"eurPerKwh":0.25},"upTo50Kw":{"eurPerKwh":0.51},"idle":{"upTo25Kw":{"afterConnectionMinutes":840,"eurPerHour":10.0},"at50Kw":{"afterConnectionMinutes":90,"eurPerMinute":0.20,"afterConnectionMinutesSecondTier":180,"secondTierEurPerHour":10.0}}}}
 },
 "rules":{"dayNightClockWindowsNotPublishedOnCurrentTariffPage":True,"subscriberDayIdleUnitAnomaly":True,"subscriberDayIdleUnitNote":"The official page says 0.10 cts/min and 0.20 cts/min. Preserve the source wording; do not assume EUR/min until verified."},
 "tccDecision":{"operatorValidated":True,"energyTariffsValidated":True,"publicIdleTariffsValidated":True,"automaticDayNightClassification":False,"subscriberDayIdleFullyClassable":False,"manualChecksNeeded":["Exact day/night clock windows","Subscriber daytime idle units written as cts/min"],"roamingSeparate":True},
 "sourceEvidence":{"officialOnly":True,"homeUrl":hfinal,"homeHttpStatus":hs,"tariffsUrl":tfinal,"tariffsHttpStatus":ts,"homeSha256":hashlib.sha256(hraw).hexdigest(),"tariffsSha256":hashlib.sha256(traw).hexdigest()},"publicationStatus":"validated_candidate_with_source_ambiguities"}
 sig={k:payload[k] for k in ("network","operatorDirect","rules","tccDecision")};payload["sourceEvidence"]["relevantTariffFingerprintSha256"]=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 (out/"connectandgo_yutz_official_grandest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n");(out/"SUMMARY.md").write_text("# Connect&go — Yutz\n\nOfficial energy prices and public idle rules validated for the 22/25/50 kW network operated with Delmonicos. Two source ambiguities remain deliberately uncorrected: the tariff page does not state the exact clock windows for day/night, and the subscriber daytime idle fee is written in cts/min.\n")
if __name__=="__main__":main()
