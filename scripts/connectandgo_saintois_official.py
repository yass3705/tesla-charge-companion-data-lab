#!/usr/bin/env python3
"""Validate current official Connect&go Pays du Saintois tariff rules."""
from __future__ import annotations

import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
TARIFFS = "https://paysdusaintois.connectandgo.fr/tarifs/"


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(getattr(r, "status", 200)), r.read(), r.geturl()


def plain(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'").replace(" ", " ")).strip()


def require(text: str, *items: str):
    n = norm(text)
    missing = [x for x in items if norm(x) not in n]
    if missing:
        raise RuntimeError("Connect&go Pays du Saintois official evidence missing: " + ", ".join(missing))


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="out/connectandgo_saintois"); args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    ts, traw, tfinal = fetch(TARIFFS)
    if ts != 200: raise RuntimeError(f"HTTP failure tariffs={ts}")
    ttext = plain(traw)
    require(ttext,
        "SANS ABONNEMENT", "0€ /mois",
        "De 8h30 à 20h : 0,27 € par kWh entamé et 0,025 € par minute",
        "après 3h de branchement, 0,16 € par minute sans consommation",
        "De 20h à 8h30 : 0,25 € par kWh entamé",
        "AVEC ABONNEMENT", "3€ /mois",
        "De 9h à 20h : 0,25 € par kWh entamé et 0,025 € par minute",
        "après 4h de branchement, 0,13 € par minute sans consommation",
        "De 20h à 9h : 0,20 € par kWh entamé",
        "Connect&go - Freshmile")

    payload = {
      "schemaVersion":"1.0.0","dataset":"connectandgo-saintois-official-grandest","generatedAt":now(),
      "operator":"Connect&go - Pays du Saintois","serviceOperator":"Freshmile","country":"FR","region":"Grand Est","department":"Meurthe-et-Moselle",
      "classification":{"localPublicNetwork":True,"directPublishedTariff":True,"energyAndTimeBased":True,"dayNightDependent":True,"memberTariffAvailable":True,"idleSurcharge":True,"roamingMayDiffer":True,"publishedTariffScope":"below30Kw"},
      "operatorDirect":{
        "withoutSubscription":{"monthlyEur":0.0,"day":{"window":"08:30-20:00","below30Kw":{"eurPerKwh":0.27,"eurPerMinute":0.025}},"night":{"window":"20:00-08:30","below30Kw":{"eurPerKwh":0.25,"eurPerMinute":0.0}},"idle":{"below30Kw":{"afterMinutes":180,"eurPerMinute":0.16,"condition":"without_consumption"}}},
        "withSubscription":{"monthlyEur":3.0,"day":{"window":"09:00-20:00","below30Kw":{"eurPerKwh":0.25,"eurPerMinute":0.025}},"night":{"window":"20:00-09:00","below30Kw":{"eurPerKwh":0.20,"eurPerMinute":0.0}},"idle":{"below30Kw":{"afterMinutes":240,"eurPerMinute":0.13,"condition":"without_consumption"}}}
      },
      "rules":{"tariffThresholdLabel":"30 kW","idleSurchargeAppliesWithoutConsumption":True,"lowPowerNightHasNoMinuteComponent":True,"higherPowerTariffNotPublishedOnCurrentPage":True},
      "tccDecision":{"operatorValidated":True,"directTariffClassable":True,"subscriptionSeparateOffer":True,"roamingSeparate":True,"idleFeeMustBeModeled":True,"scopeRestriction":"Only apply this official grid to stations/connectors below 30 kW unless a higher-power tariff is separately verified."},
      "sourceEvidence":{"officialOnly":True,"tariffsUrl":tfinal,"tariffsHttpStatus":ts,"tariffsSha256":hashlib.sha256(traw).hexdigest()},
      "publicationStatus":"validated_candidate"
    }
    sig={k:payload[k] for k in ("operatorDirect","rules","tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"]=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    (out/"connectandgo_saintois_official_grandest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    (out/"SUMMARY.md").write_text("# Connect&go — Pays du Saintois\n\nOfficial tariff validated for the published below-30-kW scope: public and 3 EUR/month subscriber variants, day/night windows and idle surcharges. Freshmile is the service/access partner. Higher-power pricing is not inferred.\n")

if __name__ == "__main__": main()
