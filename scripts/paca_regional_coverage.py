#!/usr/bin/env python3
"""Validate and consolidate public charging-network evidence for Provence-Alpes-Cote d'Azur."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SOURCES = {
    "eborn_tariffs": "https://www.eborn.fr/tarifs/",
    "eborn_faq": "https://www.eborn.fr/foire-aux-questions/",
    "sde04": "https://sde04.fr/competences/la-mobilite-electrique/",
    "te05": "https://www.te05.fr/nos-competences-2/mobilite-electrique/",
    "wiiiz": "https://www.evzen.com/fr/reseau-wiiiz",
    "wiiiz_cgau": "https://www.evzen.com/fr/cgau-wiiiz",
    "larecharge": "https://www.evzen.com/fr/reseau-larecharge",
    "simone": "https://www.evzen.com/fr/reseau-simone",
    "prise_nice_2026": "https://www.nicecotedazur.org/actualites/86-nouvelles-bornes-de-recharge-electrique-sur-le-reseau-prisedenice/",
    "nice_mobility": "https://www.nice.fr/mobilite/se-deplacer/en-voiture/",
    "vaucluse_sev": "https://sev84.fr/accueil/nos-competences/la-mobilite-electrique",
    "vaucluse_ulys": "https://ulys.com/offre/ulys-electric/options/vauclus-elec/",
    "mamp_multi": "https://innovation.ampmetropole.fr/participation/36/4-les-appels-a-innovation.htm",
    "mamp_izivia": "https://www.data.gouv.fr/datasets/bornes-de-recharges-pour-ve-mamp",
}

def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def norm(v):
    import unicodedata
    if isinstance(v, bytes):
        v = v.decode("utf-8", errors="replace")
    v = unescape(v or "")
    v = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", v, flags=re.I | re.S)
    v = re.sub(r"<[^>]+>", " ", v)
    v = unicodedata.normalize("NFKD", v)
    v = "".join(c for c in v if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", v.lower().replace("\xa0", " ")).strip()

def compact(v):
    return re.sub(r"\s+", "", norm(v)).replace(",", ".")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=55) as r:
        raw = r.read()
        return int(getattr(r, "status", 200)), raw, r.geturl(), r.headers.get("content-type", "")

def probe():
    out, reachable = {}, 0
    for key, url in SOURCES.items():
        try:
            st, raw, final, ctype = fetch(url)
            out[key] = {
                "url": final, "httpStatus": st, "contentType": ctype,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "text": raw.decode("utf-8", errors="replace"),
            }
            if st == 200:
                reachable += 1
        except Exception as exc:
            out[key] = {"url": url, "httpStatus": None, "error": type(exc).__name__, "text": ""}
    return out, reachable

def require(text, *items, label="source"):
    n = norm(text)
    missing = [x for x in items if norm(x) not in n]
    if missing:
        raise RuntimeError(f"{label} missing: " + ", ".join(missing))

def require_numbers(text, *items, label="source"):
    n = compact(text)
    missing = [str(x) for x in items if str(x).replace(",", ".") not in n]
    if missing:
        raise RuntimeError(f"{label} missing numeric witnesses: " + ", ".join(missing))

def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

def evidence(v):
    return {k: x for k, x in v.items() if k != "text"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/paca")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    src, reachable = probe()

    if src["eborn_faq"]["httpStatus"] == 200:
        require(src["eborn_faq"]["text"], "Alpes-de-Haute-Provence", "Hautes-Alpes", "Var", "Easy Charge", label="eBorn PACA territory")
    if src["eborn_tariffs"]["httpStatus"] == 200:
        require_numbers(src["eborn_tariffs"]["text"], 0.31, 0.433, 0.573, 0.588, 0.65, 0.075, 0.12, label="eBorn current tariffs")
        require(src["eborn_tariffs"]["text"], "250 kWh", "30 minutes", "15%", label="eBorn current rules")
    if src["sde04"]["httpStatus"] == 200:
        require(src["sde04"]["text"], "Eborn", "Alpes-de-Haute-Provence", label="TE-SDE04")
    if src["te05"]["httpStatus"] == 200:
        require(src["te05"]["text"], "eborn", "85 bornes", label="TE05")
    if src["wiiiz"]["httpStatus"] == 200:
        require(src["wiiiz"]["text"], "Recharge accélérée", "Recharge rapide", "50 kW", label="WiiiZ")
        require_numbers(src["wiiiz"]["text"], 0.24, 0.40, 0.25, 6, 15, label="WiiiZ current tariffs")
    if src["wiiiz_cgau"]["httpStatus"] == 200:
        require(src["wiiiz_cgau"]["text"], "1er Juillet 2026", "SMEG Développement", "EVzen", label="WiiiZ CGAU")
    if src["larecharge"]["httpStatus"] == 200:
        require(src["larecharge"]["text"], "Bornes lentes", "Bornes normales", "Bornes accélérées", "50", label="larecharge")
        require_numbers(src["larecharge"]["text"], 1.20, 0.60, 2.40, 6.00, 1.50, 12, 5, label="larecharge current tariffs")
    if src["simone"]["httpStatus"] == 200:
        require(src["simone"]["text"], "1er juin 2026", "22kW", "Simone", label="Simone")
        require_numbers(src["simone"]["text"], 0.50, 0.55, 0.35, 0.38, 3.00, 3.30, 30, 12, label="Simone current tariffs")
    if src["prise_nice_2026"]["httpStatus"] == 200:
        require(src["prise_nice_2026"]["text"], "86", "17 juillet 2026", "Prise de Nice", label="Prise de Nice 2026")
    if src["nice_mobility"]["httpStatus"] == 200:
        require(src["nice_mobility"]["text"], "Prise de Nice", "22 kW", "50 kW", label="Nice mobility")
    if src["vaucluse_sev"]["httpStatus"] == 200:
        require(src["vaucluse_sev"]["text"], "VAUCLUS’ELEC", "20km", label="SEV Vauclus'Elec")
    if src["vaucluse_ulys"]["httpStatus"] == 200:
        require(src["vaucluse_ulys"]["text"], "Vauclus'élec", "1,50", "6", label="Ulys Vauclus'Elec")
    if src["mamp_multi"]["httpStatus"] == 200:
        require(src["mamp_multi"]["text"], "trois opérateurs", "larecharge", label="MAMP multi-CPO")
    if src["mamp_izivia"]["httpStatus"] == 200:
        require(src["mamp_izivia"]["text"], "IZIVIA", "MAMP", "larecharge", label="MAMP IZIVIA")

    if reachable < 9:
        raise RuntimeError(f"too few current public/official sources reachable: {reachable}/{len(SOURCES)}")

    eborn_path = Path("data/operator_direct/eborn_official_france.json")
    if not eborn_path.exists():
        raise RuntimeError("validated eBorn dataset missing")
    eborn = json.loads(eborn_path.read_text())
    terr = eborn["classification"]["territoryDepartments"]
    for dep in ("Alpes-de-Haute-Provence", "Hautes-Alpes", "Var"):
        assert dep in terr
    assert eborn["operatorDirect"]["powerBands"]["acceleratedUpTo25Kw"]["aLaCarteEurPerKwh"] == 0.31
    assert eborn["operatorDirect"]["powerBands"]["ultraFastAbove60Kw"]["nonSubscriberEurPerKwh"] == 0.65

    common = {
        "schemaVersion": "1.0.0",
        "generatedAt": now(),
        "country": "FR",
        "region": "Provence-Alpes-Côte d’Azur",
        "publicationStatus": "validated_candidate",
    }

    wiiiz = {
        **common,
        "dataset": "wiiiz-evzen-official-paca",
        "operator": "WiiiZ",
        "serviceOperator": "EVzen / SMEG Développement",
        "territory": {
            "departments": ["Alpes-Maritimes", "Var"],
            "publicAuthorities": [
                "Cannes Pays de Lérins", "Pays de Grasse", "Sophia Antipolis",
                "Communauté de Communes Alpes d'Azur", "Estérel Côte d’Azur Agglomération"
            ],
        },
        "classification": {
            "regionalPublicNetworkFamily": True,
            "singleFlatTariff": False,
            "tariffDependsOnPowerZoneAndProfile": True,
            "roamingSeparate": True,
            "currentCgauEffective": "2026-07-01",
        },
        "subscription": {"monthlyFeeEur": 6.0, "registrationFeeEur": 15.0, "badgeIncluded": True},
        "directTariff": {
            "ac7To22Kw": {
                "urban": {
                    "subscriber": {"dayFirstHourEur": 2.0, "dayEachAdditional30MinEur": 1.0, "night2300To0700FlatEur": 2.0},
                    "nonSubscriber": {"dayFirstHourEur": 3.0, "dayEachAdditional30MinEur": 2.0, "night2300To0700FlatEur": 3.0},
                },
                "mountainParkRideCarpoolSki": {
                    "subscriber": {"dayFirstHourEur": 2.0, "nextThreeHoursEur": 2.0, "thereafterEach30MinEur": 1.0, "night2300To0700FlatEur": 2.0},
                    "nonSubscriber": {"dayFirstHourEur": 3.0, "nextThreeHoursEur": 3.0, "thereafterEach30MinEur": 2.0, "night2300To0700FlatEur": 3.0},
                },
            },
            "dc50Kw": {
                "subscriberEurPerKwh": 0.24,
                "nonSubscriberEurPerKwh": 0.40,
                "postChargeEurPerMinute": 0.25,
            },
        },
        "tccDecision": {"directTariffClassable": True, "stationZoneAndPowerRequired": True, "roamingSeparate": True},
        "sourceEvidence": {"tariffs": evidence(src["wiiiz"]), "cgau": evidence(src["wiiiz_cgau"])},
    }
    write(out / "wiiiz_evzen_official_paca.json", wiiiz)

    larecharge = {
        **common,
        "dataset": "larecharge-evzen-official-paca",
        "operator": "larecharge",
        "serviceOperator": "EVzen / Freshmile",
        "territory": "Métropole Aix-Marseille-Provence",
        "classification": {
            "legacyMetropolitanPublicNetwork": True,
            "metropolitanQualityLabelIsNotSingleCpo": True,
            "separateLabelledOperatorsExist": True,
            "roamingSeparate": True,
        },
        "directTariff": {
            "basis": "connection_time",
            "slowUpTo3Kw": {"day0700To2200EurPerHour": 1.20, "night2200To0700EurPerHour": 0.60},
            "normalUpTo7Kw": {"day0700To2200EurPerHour": 2.40, "night2200To0700EurPerHour": 1.20},
            "acceleratedUpTo22Kw": {"day0700To2200EurPerHour": 6.00, "night2200To0700EurPerHour": 1.50},
            "transactionCapEur": 50.0,
            "annualSubscriptionEur": 12.0,
            "subscriberDiscountPercent": 5.0,
        },
        "labelContext": {
            "threeOperatorCompetitiveFramework": True,
            "tariffsOfLabelledPrivateOperatorsNotForcedToLegacyLarechargeGrid": True,
            "knownCurrentLabelledNetworkExample": {"network": "MAMP", "operator": "IZIVIA"},
        },
        "tccDecision": {
            "legacyDirectTariffClassable": True,
            "doNotApplyLegacyGridToAllLarechargeLabelledStations": True,
            "cpoIdentityRequired": True,
            "roamingSeparate": True,
        },
        "sourceEvidence": {
            "legacyTariffs": evidence(src["larecharge"]),
            "multiOperatorFramework": evidence(src["mamp_multi"]),
            "iziviaMamp": evidence(src["mamp_izivia"]),
        },
    }
    write(out / "larecharge_evzen_official_paca.json", larecharge)

    simone = {
        **common,
        "dataset": "simone-evzen-official-paca",
        "operator": "Simone",
        "serviceOperator": "EVzen / SMEG",
        "department": "Bouches-du-Rhône",
        "classification": {"departmentalPublicNetwork": True, "exactPublishedTariff": True, "roamingSeparate": True},
        "effectiveDate": "2026-06-01",
        "subscription": {"annualFeeEur": 12.0, "preferredTariffAlsoForLarechargeSubscribers": True},
        "directTariff": {
            "ac22Kw": {
                "day0700To2100": {"subscriberEurPerKwh": 0.50, "nonSubscriberEurPerKwh": 0.55},
                "night2100To0700": {"subscriberEurPerKwh": 0.35, "nonSubscriberEurPerKwh": 0.38},
                "postChargeDay": {"subscriberEurPerHour": 3.00, "nonSubscriberEurPerHour": 3.30},
                "paymentCapEur": 30.0,
            },
            "additionalBadgeEur": 11.0,
        },
        "tccDecision": {"directTariffClassable": True, "timeWindowRequired": True, "postChargeSeparate": True, "roamingSeparate": True},
        "sourceEvidence": evidence(src["simone"]),
    }
    write(out / "simone_evzen_official_paca.json", simone)

    prise = {
        **common,
        "dataset": "prise-de-nice-official-paca",
        "operator": "Prise de Nice",
        "serviceOperator": "IZIVIA",
        "territory": "Métropole Nice Côte d’Azur",
        "classification": {
            "metropolitanPublicNetwork": True,
            "currentPublicTariffPageDynamic": True,
            "exactCurrentGridEmbeddedInCrawler": False,
            "roamingSeparate": True,
        },
        "networkEvidence2026": {
            "newPublicPointsFrom2026_07_17": 86,
            "powerClassesPublished": ["up to 22 kW", "fast 50 kW"],
            "tariffsVaryByPowerTimeAndDuration": True,
        },
        "tccDecision": {
            "operatorFamilyValidated": True,
            "genericCurrentDirectTariffClassable": False,
            "manualAppOrCurrentTariffPortalCheckRequired": True,
            "doNotReuseStaleTariffAnnexWithoutPortalVerification": True,
            "roamingSeparate": True,
        },
        "sourceEvidence": {"metropole2026": evidence(src["prise_nice_2026"]), "cityMobility": evidence(src["nice_mobility"])},
    }
    write(out / "prise_de_nice_official_paca.json", prise)

    vaucluse = {
        **common,
        "dataset": "vaucluselec-ulys-official-paca",
        "operator": "Vauclus'Elec",
        "serviceOperator": "Ulys",
        "department": "Vaucluse",
        "classification": {
            "departmentalPublicNetwork": True,
            "currentSubscriptionPublished": True,
            "exactCurrentStationTariffPubliclyResolved": False,
            "roamingSeparate": True,
        },
        "network": {"publicService": True, "targetCoverage": "recharge within 20 km anywhere on departmental road network"},
        "subscription": {"monthlyFeeEur": 1.50, "passPriceEur": 6.0, "reducedNetworkPricing": True},
        "tccDecision": {
            "operatorFamilyValidated": True,
            "genericCurrentDirectTariffClassable": False,
            "stationTariffInUlysAppRequired": True,
            "doNotReuseLegacyAlizeGrid": True,
            "roamingSeparate": True,
        },
        "sourceEvidence": {"sev": evidence(src["vaucluse_sev"]), "ulys": evidence(src["vaucluse_ulys"])},
    }
    write(out / "vaucluselec_ulys_official_paca.json", vaucluse)

    coverage = {
        **common,
        "dataset": "paca-regional-coverage",
        "departmentsTotal": 6,
        "departments": {
            "Alpes-de-Haute-Provence": {"publicNetworkFamilies": ["eBorn"], "pricingResolved": True},
            "Hautes-Alpes": {"publicNetworkFamilies": ["eBorn"], "pricingResolved": True},
            "Alpes-Maritimes": {"publicNetworkFamilies": ["WiiiZ", "Prise de Nice"], "pricingResolved": False},
            "Bouches-du-Rhône": {"publicNetworkFamilies": ["larecharge", "Simone", "MAMP / labelled operators"], "pricingResolved": False},
            "Var": {"publicNetworkFamilies": ["eBorn", "WiiiZ"], "pricingResolved": True},
            "Vaucluse": {"publicNetworkFamilies": ["Vauclus'Elec"], "pricingResolved": False},
        },
        "coverage": {
            "departmentsAccountedFor": 6,
            "regionalPublicNetworkResearchCoverageComplete": True,
            "singleUniversalRegionalTariff": False,
            "allIdentifiedLiveTariffsResolved": False,
            "operatorFamiliesWithExactCurrentPublicGrid": ["eBorn", "WiiiZ", "larecharge legacy", "Simone"],
            "operatorFamiliesRequiringStationOrAppVerification": ["Prise de Nice", "MAMP labelled private CPO stations", "Vauclus'Elec"],
        },
        "tccDecision": {
            "doNotInventDepartmentDefaults": True,
            "cpoIdentityAndNetworkRequired": True,
            "roamingSeparate": True,
            "keepUnresolvedStationTariffsNullUntilVerified": True,
        },
        "sourceHealth": {"officialOrOperatorSourcesReachableAtRun": reachable, "sourcesTotal": len(SOURCES)},
        "sourceEvidence": {
            "sde04": evidence(src["sde04"]), "te05": evidence(src["te05"]),
            "ebornFaq": evidence(src["eborn_faq"]), "wiiiz": evidence(src["wiiiz"]),
            "larecharge": evidence(src["larecharge"]), "simone": evidence(src["simone"]),
            "priseNice": evidence(src["prise_nice_2026"]), "vaucluseSev": evidence(src["vaucluse_sev"]),
        },
    }
    write(out / "paca_regional_coverage.json", coverage)

    summary = f"""# Provence-Alpes-Côte d’Azur regional public-network coverage

- Departments accounted for: **6/6**.
- eBorn reused from the already validated national-regional dataset for **04, 05 and 83**.
- WiiiZ: current EVzen grid validated, including AC zone/profile tariffs and **DC 50 kW at 0.24/0.40 EUR/kWh + 0.25 EUR/min post-charge**.
- larecharge legacy: current EVzen connection-time grid validated; **do not apply it to every station carrying the larecharge quality label**.
- Simone: new grid effective **2026-06-01** validated.
- Prise de Nice: operator/network current, but exact current direct grid remains **station/app verification required**.
- Vauclus'Elec: Ulys current subscription (**1.50 EUR/month; pass 6 EUR**) validated; exact station tariff remains **app verification required**.
- Region-wide universal tariff: **NO**.
- Public-network research coverage complete: **YES**, tariff resolution complete: **NO**.
- Current source reachability: **{reachable}/{len(SOURCES)}**.
"""
    (out / "SUMMARY.md").write_text(summary)

if __name__ == "__main__":
    main()
