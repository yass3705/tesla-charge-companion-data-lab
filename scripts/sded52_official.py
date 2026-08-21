#!/usr/bin/env python3
"""Validate current official SDED52 (Haute-Marne) EV charging tariffs."""
from __future__ import annotations

import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
HOME = "https://www.sded52.fr/bornes-de-recharge"
TARIFFS = "https://www.sded52.fr/tarifs-en-vigueur"


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
        raise RuntimeError("SDED52 official evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="out/sded52"); args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    hs, hraw, hfinal = fetch(HOME); ts, traw, tfinal = fetch(TARIFFS)
    if hs != 200 or ts != 200:
        raise RuntimeError(f"HTTP failure home={hs} tariffs={ts}")
    htext, ttext = plain(hraw), plain(traw)
    require(htext, "SDED 52 organise le service public de recharge", "L'accès au service est géré par Freshmile", "22kVA", "24 KVA", "tarifs ont évolué au 1er août 2026")
    require(ttext,
        "publié le jeudi 6 août 2026", "À compter du 1er août 2026",
        "Haut-Marnais", "badge Freshmile uniquement",
        "Bornes AC", "0,39 € par kWh entamé", "après 2 heures 30 de branchement, 2€ toutes les 15 minutes sans consommation d'énergie",
        "Bornes DC", "0,49 € par kWh entamé", "après 1 heure de branchement, 2€ toutes les 15 minutes sans consommation d'énergie",
        "Pour tout autre opérateur de recharge", "0,49 € par kWh entamé", "0,59 € par kWh entamé",
        "De 8h à 21h", "La tarification de stationnement continue tant que le véhicule reste branché")

    idle_ac = {"window":"08:00-21:00","afterConnectionMinutes":150,"condition":"without_energy_consumption","eurPerBillingBlock":2.0,"billingBlockMinutes":15,"continuesWhileConnected":True}
    idle_dc = {"window":"08:00-21:00","afterConnectionMinutes":60,"condition":"without_energy_consumption","eurPerBillingBlock":2.0,"billingBlockMinutes":15,"continuesWhileConnected":True}
    payload = {
      "schemaVersion":"1.0.0","dataset":"sded52-official-grandest","generatedAt":now(),
      "operator":"SDED 52","serviceOperator":"Freshmile","country":"FR","region":"Grand Est","department":"Haute-Marne",
      "effectiveFrom":"2026-08-01",
      "classification":{"localPublicNetwork":True,"directPublishedTariff":True,"energyBased":True,"localResidentBadgeOffer":True,"roamingPublishedPriceTier":True,"idleSurcharge":True,"idleBillingByBlock":True},
      "technical":{"normalChargeKva":3,"acceleratedChargeKva":22,"acceleratedSimultaneousKva":18,"rapidChargeFromKva":24},
      "operatorDirect":{
        "hautMarnaisFreshmileBadge":{"eligibility":"Haut-Marnais; Freshmile badge required","ac":{"eurPerKwh":0.39,"idle":idle_ac},"dc":{"eurPerKwh":0.49,"idle":idle_dc}},
        "otherChargingOperator":{"scope":"published SDED52 price tier for any other charging operator","ac":{"eurPerKwh":0.49,"idle":idle_ac},"dc":{"eurPerKwh":0.59,"idle":idle_dc}}
      },
      "billingNotes":{"idleFeeIsDiscreteBlock":True,"doNotSilentlyNormalizeToPerMinute":True,"equivalentAverageEurPerMinute":round(2/15,6),"note":"Official wording is 2 EUR every 15 minutes; preserve the 15-minute billing block in TCC rather than assuming continuous minute billing."},
      "tccDecision":{"operatorValidated":True,"localBadgeEnergyTariffClassable":True,"otherOperatorEnergyTierPublished":True,"roamingMustRemainSeparate":True,"idleFeeMustBeModeledAs15MinuteBlocks":True,"manualStationTestDeferred":True},
      "sourceEvidence":{"officialOnly":True,"homeUrl":hfinal,"homeHttpStatus":hs,"tariffsUrl":tfinal,"tariffsHttpStatus":ts,"homeSha256":hashlib.sha256(hraw).hexdigest(),"tariffsSha256":hashlib.sha256(traw).hexdigest()},
      "publicationStatus":"validated_candidate"
    }
    sig={k:payload[k] for k in ("effectiveFrom","technical","operatorDirect","billingNotes","tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (out/"sded52_official_grandest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n")
    (out/"SUMMARY.md").write_text("# SDED 52 — Haute-Marne\n\nOfficial tariffs effective 1 August 2026 validated. Haut-Marnais using a Freshmile badge pay 0.39 EUR/kWh AC and 0.49 EUR/kWh DC; the SDED52 page publishes 0.49/0.59 EUR/kWh for other charging operators. Between 08:00 and 21:00, an idle fee of 2 EUR per 15-minute block applies without energy consumption after 2h30 AC or 1h DC and continues while connected. The block billing is preserved exactly.\n")

if __name__ == "__main__": main()
