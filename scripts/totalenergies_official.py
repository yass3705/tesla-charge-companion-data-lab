#!/usr/bin/env python3
"""Extract current TotalEnergies France public EV charging tariff families.

Official-only model:
- TotalEnergies CPO station-service public tariffs + occupation fee,
- Charge+ as eMSP / roaming product,
- Charge+ Zen option,
- Charge+ City Aix-Marseille-Provence local option,
- official Zen station inventory samples.

No authentication, private API, cookies, or user data.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

SOURCES = {
    "stationPricing": "https://chargeplus.totalenergies.com/fr/conseils-recharge-electrique/cout-recharge-voiture-electrique/",
    "stationIdle": "https://services.totalenergies.fr/particuliers/energies-vehicules/electrique-rechargeable/pourquoi-choisir-electrique-totalenergies",
    "chargePlus": "https://chargeplus.totalenergies.com/fr/rechargez-votre-vehicule-electrique-partout-en-france-avec-charge-de-totalenergies/",
    "chargePlusHome": "https://chargeplus.totalenergies.com/fr/",
    "zenPoints": "https://chargeplus.totalenergies.com/fr/point-recharges-totalenergies-avec-remises/",
    "cityAmp": "https://chargeplus.totalenergies.com/fr/option-city-amp/",
    "cpoEmsp": "https://chargeplus.totalenergies.com/fr/faq/oir-emsp/",
}

SAMPLE_STATIONS = {
    "relais_de_silly": ("RELAIS DE SILLY", "BOULOGNE-BILLANCOURT"),
    "relais_de_la_mauldre": ("RELAIS DE LA MAULDRE", "EPONE"),
    "rocade_chartres": ("ROCADE CHARTRES", "CHARTRES"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace")


def text_from_html(raw_html: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw_html, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'").replace("\xa0", " ")
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"):
        s = s.replace(ch, "-")
    return re.sub(r"\s+", " ", s).strip()


def eur(v: str) -> float:
    return float(v.replace(",", "."))


def require(text: str, phrase: str, source: str) -> None:
    if norm(phrase) not in norm(text):
        raise RuntimeError(f"{source}: missing expected phrase: {phrase}")


def parse_station_pricing(text: str) -> dict:
    n = norm(text)
    m_low = re.search(r"0[,.]52\s*€\s*ttc\s*/?\s*kwh.{0,120}?(?:jusqu.?a|jusqu'a)?\s*50\s*kw", n)
    if not m_low:
        m_low = re.search(r"bornes\s+jusqu.?a\s*50\s*kw.{0,120}?0[,.]52\s*€", n)
    m_high = re.search(r"0[,.]62\s*€\s*ttc\s*/?\s*kwh.{0,120}?plus\s+de\s+50\s*kw", n)
    if not m_high:
        m_high = re.search(r"bornes\s+de\s+plus\s+de\s+50\s*kw.{0,120}?0[,.]62\s*€", n)
    if not m_low or not m_high:
        raise RuntimeError("TotalEnergies station-service public kWh tariffs not found")
    if "5 mars 2025" not in n:
        raise RuntimeError("TotalEnergies station-service effective-date marker missing")
    if "nous ne faisons pas de frais de session" not in n:
        raise RuntimeError("TotalEnergies no-session-fee marker missing")
    return {
        "effectiveSince": "2025-03-05",
        "upToAndIncluding50KwEurPerKwh": 0.52,
        "over50KwEurPerKwh": 0.62,
        "sessionFeeEur": 0.0,
        "scope": "TotalEnergies station-service chargers in France",
        "networkCaveat": "Other TotalEnergies concessions/public networks can use different tariff structures.",
    }


def parse_station_idle(text: str) -> dict:
    n = norm(text)
    if "45 minutes" not in n or "0,50" not in n or "/ min" not in n:
        raise RuntimeError("TotalEnergies 45-minute occupation fee evidence missing")
    if "tant que votre vehicule reste branche" not in n:
        raise RuntimeError("TotalEnergies connected-duration billing marker missing")
    return {
        "eurPerMin": 0.50,
        "startsAfterConsecutiveConnectedMinutes": 45,
        "appliesWhileVehicleRemainsConnected": True,
        "classification": "occupation_fee",
        "emspMayChargeDifferentPrice": True,
    }


def parse_chargeplus(text: str, home_text: str) -> dict:
    n = norm(text)
    h = norm(home_text)
    if "160 000" not in n and "160 000" not in h:
        raise RuntimeError("Charge+ coverage marker missing")
    if "3,90" not in n or "15%" not in n:
        raise RuntimeError("Charge+ Zen price/discount markers missing")
    if "50kw" not in n.replace(" ", ""):
        raise RuntimeError("Charge+ Zen >=50kW eligibility marker missing")
    if "hors corse" not in n:
        raise RuntimeError("Charge+ Zen geographic marker missing")
    promo_price = 9.90 if "9,90" in h else None
    regular_price = 19.90 if "19,90" in h or "19,90" in n else None
    promo_end = "2026-08-28" if "28/08/2026" in h else None
    return {
        "classification": "eMSP_roaming",
        "operatorDirect": False,
        "coveragePointsFranceApprox": 160000,
        "card": {
            "regularPurchaseEur": regular_price,
            "currentPromoPurchaseEur": promo_price,
            "promoEnd": promo_end,
        },
        "zen": {
            "monthlyFeeEur": 3.90,
            "discountPercent": 15.0,
            "discountAppliesTo": "public kWh price",
            "eligibleOperatorBrand": "TotalEnergies",
            "minimumPowerKw": 50,
            "geography": "France metropolitan, excluding Corsica",
            "calculatedExamplesFromPublishedStationServiceTariff": {
                "exactly50KwEurPerKwh": 0.442,
                "over50KwEurPerKwh": 0.527,
                "calculatedNotDisplayedTariff": True,
            },
        },
        "partnerNetworkTariff": {
            "stationLevelLookupRequired": True,
            "priceShownInChargePlusApp": True,
            "mustNotBeClassifiedAsCpoDirect": True,
        },
    }


def parse_city_amp(text: str) -> dict:
    n = norm(text)
    markers = ["5€/mois", "0,45", "0,40", "0,54", "0,07", "30 minutes", "8h a 20h", "20h a 8h"]
    for marker in markers:
        if norm(marker) not in n:
            raise RuntimeError(f"TotalEnergies City AMP marker missing: {marker}")
    if "hors station-service" not in n:
        raise RuntimeError("TotalEnergies City AMP scope marker missing")
    return {
        "network": "TotalEnergies roadside network - Métropole Aix-Marseille-Provence",
        "classification": "local_subscription_tariff",
        "monthlyFeeEur": 5.0,
        "scope": "eligible TotalEnergies-operated roadside chargers in Métropole Aix-Marseille-Provence; excludes station-service",
        "ac": {
            "publicEurPerKwh": 0.54,
            "cityDayEurPerKwh": 0.45,
            "cityNightEurPerKwh": 0.40,
            "dayLocalTime": "08:00-20:00",
            "nightLocalTime": "20:00-08:00",
        },
        "dc": {
            "preferentialTariffExists": True,
            "exactMachineValidatedRate": None,
            "status": "official_rate_present_in_image_table; station/app lookup required until machine-validated",
        },
        "idle": {
            "eurPerMin": 0.07,
            "startsMinutesAfterChargeEnd": 30,
            "daytimeOnly": True,
        },
    }


def parse_cpo_emsp(text: str) -> dict:
    n = norm(text)
    if "cpo" not in n or "emsp" not in n:
        raise RuntimeError("TotalEnergies CPO/eMSP distinction marker missing")
    if "tarifs fixes par un emsp peuvent etre differents" not in n:
        raise RuntimeError("TotalEnergies eMSP different-price marker missing")
    return {
        "officialDistinctionConfirmed": True,
        "emspTariffMayDifferFromCpo": True,
    }


def parse_zen_table(raw_html: str) -> list[dict]:
    rows = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", raw_html, flags=re.I | re.S):
        cells = [text_from_html(x).strip() for x in re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)]
        if len(cells) < 7:
            continue
        brand, station, address, postal, city, power_raw, evse = cells[:7]
        if not re.search(r"FR\*HPC\*", evse, flags=re.I):
            continue
        try:
            power = float(power_raw.replace(",", "."))
        except ValueError:
            continue
        rows.append({
            "brand": brand,
            "station": station,
            "address": address,
            "postalCode": postal,
            "city": city,
            "powerKw": power,
            "evseId": evse,
        })
    if len(rows) < 50:
        raise RuntimeError(f"TotalEnergies Zen official station table unexpectedly small: {len(rows)} rows")
    return rows


def sample_stations(rows: list[dict]) -> list[dict]:
    out = []
    for key, (station_name, city_name) in SAMPLE_STATIONS.items():
        matches = [r for r in rows if norm(r["station"]) == norm(station_name) and norm(r["city"]) == norm(city_name)]
        if not matches:
            raise RuntimeError(f"TotalEnergies sample station missing: {station_name} / {city_name}")
        out.append({
            "key": key,
            "station": matches[0]["station"],
            "brand": matches[0]["brand"],
            "address": matches[0]["address"],
            "postalCode": matches[0]["postalCode"],
            "city": matches[0]["city"],
            "powersKwObserved": sorted({m["powerKw"] for m in matches}),
            "evseIdsSample": [m["evseId"] for m in matches[:12]],
            "hasZenEligiblePowerAtOrAbove50Kw": any(m["powerKw"] >= 50 for m in matches),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/totalenergies")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses = {}
    raws = {}
    texts = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: unexpected HTTP status {status}")
        statuses[key] = status
        raws[key] = raw
        texts[key] = text_from_html(raw)

    station_pricing = parse_station_pricing(texts["stationPricing"])
    station_idle = parse_station_idle(texts["stationIdle"])
    chargeplus = parse_chargeplus(texts["chargePlus"], texts["chargePlusHome"])
    city_amp = parse_city_amp(texts["cityAmp"])
    cpo_emsp = parse_cpo_emsp(texts["cpoEmsp"])
    zen_rows = parse_zen_table(raws["zenPoints"])
    samples = sample_stations(zen_rows)

    facts = {
        "stationPricing": station_pricing,
        "stationIdle": station_idle,
        "chargePlus": chargeplus,
        "cityAmp": city_amp,
        "cpoEmsp": cpo_emsp,
        "zenInventoryRowCount": len(zen_rows),
        "samples": samples,
    }
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "totalenergies-official-france",
        "generatedAt": now_iso(),
        "operator": "TotalEnergies",
        "country": "FR",
        "classification": {
            "singleNationalOperatorTariff": False,
            "reason": "Station-service CPO pricing, local concession pricing, and Charge+ eMSP/member pricing are distinct tariff families.",
        },
        "operatorDirect": {
            "stationServiceFrance": {
                **station_pricing,
                "occupationFee": station_idle,
            },
        },
        "mobilityProvider": {
            "chargePlus": chargeplus,
        },
        "localNetworks": {
            "aixMarseilleProvenceCity": city_amp,
        },
        "officialCpoEmspModel": cpo_emsp,
        "zenEligibleInventory": {
            "officialTableRowCount": len(zen_rows),
            "stationLevelEligibilityListAvailable": True,
            "note": "The official list contains all connectors at listed stations; Zen discount still requires >=50 kW eligibility.",
        },
        "stationValidationSamples": samples,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Do not merge Charge+ roaming prices with TotalEnergies CPO-direct prices.",
            "Station-service pricing is a published tariff family, not a guarantee for every TotalEnergies-operated concession.",
            "The 0.50 EUR/min station-service occupation fee starts after 45 consecutive minutes connected and continues while plugged in.",
            "City Aix-Marseille-Provence DC preferential pricing is acknowledged but not numerically machine-validated because the current official rate is embedded in an image table.",
        ],
    }

    (out / "totalenergies_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# TotalEnergies France official tariff check\n\n"
        f"- Station-service <=50 kW: **{station_pricing['upToAndIncluding50KwEurPerKwh']:.2f} EUR/kWh**\n"
        f"- Station-service >50 kW: **{station_pricing['over50KwEurPerKwh']:.2f} EUR/kWh**\n"
        f"- Station-service occupation fee: **{station_idle['eurPerMin']:.2f} EUR/min** after **{station_idle['startsAfterConsecutiveConnectedMinutes']} min connected**\n"
        f"- Charge+ Zen: **{chargeplus['zen']['monthlyFeeEur']:.2f} EUR/month**, **{chargeplus['zen']['discountPercent']:.0f}%** discount on eligible TotalEnergies >=50 kW public kWh price\n"
        f"- City AMP AC: public **{city_amp['ac']['publicEurPerKwh']:.2f}**, City day **{city_amp['ac']['cityDayEurPerKwh']:.2f}**, City night **{city_amp['ac']['cityNightEurPerKwh']:.2f} EUR/kWh**\n"
        f"- City AMP idle: **{city_amp['idle']['eurPerMin']:.2f} EUR/min** starting 30 min after charge end in daytime\n"
        f"- Official Zen inventory rows parsed: **{len(zen_rows)}**\n"
        f"- Validation station samples: **{len(samples)}**\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
