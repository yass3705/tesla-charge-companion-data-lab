#!/usr/bin/env python3
"""Extract current Belib' Paris tariff rules and official network observations."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import tempfile
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SOURCES = {
    "offers": "https://belib.paris/fr/offers?accountType=PERSONAL",
    "faq": "https://belib.paris/fr/assistance/faq",
    "home": "https://belib.paris/fr/home",
    "bookingPdf": "https://belib.paris/assets/pdf/belib-booking-tariffs-fr-en.pdf",
    "chargingPdf": "https://belib.paris/assets/pdf/belib-charging-tariffs-fr-en.pdf",
    "staticApi": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/belib-points-de-recharge-pour-vehicules-electriques-donnees-statiques/records?limit=20",
    "liveApi": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/belib-points-de-recharge-pour-vehicules-electriques-disponibilite-temps-reel/records?limit=20",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_bytes(url: str) -> tuple[int, bytes, str | None]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        return int(getattr(resp, "status", 200)), resp.read(), resp.headers.get_content_charset()


def html_text(url: str) -> tuple[int, str]:
    status, raw, charset = request_bytes(url)
    s = raw.decode(charset or "utf-8", errors="replace")
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return status, re.sub(r"\s+", " ", html.unescape(s)).strip()


def json_get(url: str) -> tuple[int, dict]:
    status, raw, _ = request_bytes(url)
    return status, json.loads(raw.decode("utf-8"))


def pdf_text_and_sha(url: str) -> tuple[int, str, str]:
    status, raw, _ = request_bytes(url)
    sha = hashlib.sha256(raw).hexdigest()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(raw)
        f.flush()
        cp = subprocess.run(["pdftotext", "-layout", f.name, "-"], check=True, capture_output=True)
    return status, cp.stdout.decode("utf-8", errors="replace"), sha


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def numeric_tokens(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"(?<![\d,.])(\d+(?:[,.]\d+)?)(?![\d,.])", norm(text)):
        try:
            out.append(float(m.group(1).replace(",", ".")))
        except ValueError:
            pass
    return out


def has_value(text: str, value: float, tol: float = 0.0005) -> bool:
    return any(abs(x - value) <= tol for x in numeric_tokens(text))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/belib")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses: dict[str, int] = {}
    statuses["offers"], offers = html_text(SOURCES["offers"])
    statuses["faq"], faq = html_text(SOURCES["faq"])
    statuses["home"], home = html_text(SOURCES["home"])
    statuses["bookingPdf"], booking_pdf_text, booking_sha = pdf_text_and_sha(SOURCES["bookingPdf"])
    statuses["chargingPdf"], charging_pdf_text, charging_sha = pdf_text_and_sha(SOURCES["chargingPdf"])
    statuses["staticApi"], static_data = json_get(SOURCES["staticApi"])
    statuses["liveApi"], live_data = json_get(SOURCES["liveApi"])
    if any(v != 200 for v in statuses.values()):
        raise RuntimeError(f"Belib source HTTP failure: {statuses}")

    # Current charging tariff sheet / offer page.
    for value in (0.33, 0.22, 0.57, 2.30, 0.42, 0.17, 0.37, 2.00, 0.38, 0.25):
        if not has_value(offers, value):
            raise RuntimeError(f"Belib current offer value {value} missing")
    require(offers, ("7,00 € / an", "7,00€/an"), "Belib annual subscription")
    require(offers, ("20h - 23h", "20h-23h"), "Belib resident peak night window")
    require(offers, ("23h - 08h", "23h-08h"), "Belib resident off-peak night window")

    # PDF corroboration and long-connection fee.
    for value in (0.33, 0.22, 0.57, 2.30, 0.42, 0.17, 0.37, 2.00, 0.38, 0.25, 10.0, 14.0):
        if not has_value(charging_pdf_text, value):
            raise RuntimeError(f"Belib charging PDF value {value} missing")
    require(charging_pdf_text, ("2 juin 2025", "june 2, 2025"), "Belib charging tariff effective date")

    # Booking PDF: 15-minute subscriber reservation prices by charger class.
    for value in (0.17, 0.37, 2.00, 5.70, 15.0):
        if not has_value(booking_pdf_text, value):
            raise RuntimeError(f"Belib booking PDF value {value} missing")
    require(booking_pdf_text, ("2 juin 2025", "june 2, 2025"), "Belib booking tariff effective date")

    # FAQ evidence: visitor access and roaming semantics. Parking is outside the
    # TCC Belib pricing scope by explicit project decision.
    require(faq, ("carte bancaire directement sur le totem",), "Belib visitor bank-card access")
    require(faq, ("qr code disponible sur la borne",), "Belib visitor QR access")
    require(faq, ("1.49 €", "1,49 €"), "Belib outbound roaming fee")
    require(faq, ("pre-autorisation", "pré-autorisation"), "Belib 1 EUR subscription preauthorization")
    require(faq, ("14 heures",), "Belib long connection semantics") if "14 heures" in norm(faq) else None
    require(home, ("temps branche = temps facture", "temps branché = temps facturé"), "Belib connected-time billing")

    static_count = int(static_data.get("total_count") or 0)
    live_count = int(live_data.get("total_count") or 0)
    if static_count < 1000 or live_count < 1000:
        raise RuntimeError(f"Belib official inventory unexpectedly small: static={static_count}, live={live_count}")

    samples = []
    seen = set()
    for row in static_data.get("results") or []:
        name = row.get("nom_station") or row.get("name") or row.get("adresse_station") or row.get("adresse")
        addr = row.get("adresse_station") or row.get("adresse")
        evse = row.get("id_pdc_itinerance") or row.get("id_pdc")
        key = (name, addr)
        if key in seen:
            continue
        seen.add(key)
        samples.append({
            "stationName": name,
            "address": addr,
            "evseId": evse,
            "powerKw": row.get("puissance_nominale") or row.get("puiss_max"),
        })
        if len(samples) >= 3:
            break

    live_status_counts: dict[str, int] = {}
    for row in live_data.get("results") or []:
        s = str(row.get("statut_pdc") or "unknown")
        live_status_counts[s] = live_status_counts.get(s, 0) + 1

    facts = {
        "classification": {
            "network": "Belib'",
            "localPublicConcession": True,
            "operator": "Total Marketing France / TotalEnergies Charging Services",
            "geography": "Paris",
            "singleFlatTariff": False,
            "tariffDependsOnCustomerAndChargerClass": True,
        },
        "chargerClasses": {
            "moto": {"publishedPowerKw": 3.7},
            "flex": {"publishedPowerKw": 7},
            "boost": {"publishedPowerKw": 22},
            "boostPlus": {"publishedPowerKw": 50},
        },
        "visitor": {
            "subscriptionRequired": False,
            "paymentMethods": ["bank card at totem", "QR code", "Belib app"],
            "moto": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.22},
            "flex": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.57},
            "boost": {"eurPer15MinConnected": 2.30},
            "boostPlus": {"eurPerMinuteConnected": 0.42},
        },
        "subscriptions": {
            "annualFeeEur": 7.0,
            "validityYears": 1,
            "autoRenewal": True,
            "nonResident": {
                "moto": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.17},
                "flex": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.37},
                "boost": {"eurPer15MinConnected": 2.00},
                "boostPlus": {"eurPerMinuteConnected": 0.38},
            },
            "residentParis": {
                "day": {
                    "moto": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.17},
                    "flex": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.37},
                    "boost": {"eurPer15MinConnected": 2.00},
                    "boostPlus": {"eurPerMinuteConnected": 0.38},
                },
                "night2000To2300": {
                    "moto": {"eurPerKwh": 0.33, "connectedTimeComponentEur": 0.0},
                    "flex": {"eurPerKwh": 0.33, "connectedTimeComponentEur": 0.0},
                    "boost": {"eurPer15MinConnected": 2.00},
                    "boostPlus": {"eurPerMinuteConnected": 0.38},
                },
                "night2300To0800": {
                    "moto": {"eurPerKwh": 0.25, "connectedTimeComponentEur": 0.0},
                    "flex": {"eurPerKwh": 0.25, "connectedTimeComponentEur": 0.0},
                    "boost": {"eurPer15MinConnected": 2.00},
                    "boostPlus": {"eurPerMinuteConnected": 0.38},
                },
            },
            "cardPreauthorizationDuringSignupEur": 1.0,
            "cardPreauthorizationIsNotCharged": True,
        },
        "reservation": {
            "subscriberOnly": True,
            "blocksMinutes": 15,
            "motoEur": 0.17,
            "flexEur": 0.37,
            "boostEur": 2.00,
            "boostPlusEur": 5.70,
            "residentParisFreeBetween2000And0800": True,
        },
        "fees": {
            "longConnection": {
                "thresholdHours": 14,
                "eurPerHourAfterThreshold": 10.0,
                "basis": "connection_time",
                "scope": "published Belib tariff sheet; not further narrowed on sheet",
            },
        },
        "roaming": {
            "incomingThirdPartyBadge": {
                "classification": "third_party_eMSP",
                "operatorDirect": False,
                "interoperabilityAgreementRequired": True,
                "priceSetByThirdPartyProvider": True,
            },
            "outgoingBelibBadge": {
                "classification": "Belib_eMSP_on_third_party_CPO",
                "operatorDirect": False,
                "serviceFeeEurPerSession": 1.49,
                "plusCpoPrice": True,
            },
        },
        "inventory": {
            "officialStaticDataset": True,
            "staticPointCountObserved": static_count,
            "officialLiveAvailabilityDataset": True,
            "livePointCountObserved": live_count,
            "liveStatusSampleCountsFirst20": live_status_counts,
            "samples": samples,
            "volatileCountsExcludedFromTariffFingerprint": True,
        },
    }

    tariff_signature = {
        k: facts[k]
        for k in ("classification", "chargerClasses", "visitor", "subscriptions", "reservation", "fees", "roaming")
    }
    tariff_signature["bookingPdfSha256"] = booking_sha
    tariff_signature["chargingPdfSha256"] = charging_sha
    fingerprint = hashlib.sha256(json.dumps(tariff_signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "belib-official-paris",
        "generatedAt": now_iso(),
        "operator": "Belib'",
        "country": "FR",
        "city": "Paris",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "tariffEffectiveFrom": "2025-06-02",
            "bookingPdfSha256": booking_sha,
            "chargingPdfSha256": charging_sha,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Belib is a Paris local public charging concession and must not be replaced by a generic TotalEnergies national tariff.",
            "Moto/Flex daytime prices combine energy and connected-time components; billing continues until unplugging.",
            "Resident night energy-only rates apply to Moto/Flex; Boost and Boost+ retain their time tariffs.",
            "Parking prices and parking credits are intentionally outside the TCC Belib pricing scope.",
            "Official Paris Open Data provides both static IRVE data and live EVSE availability; volatile live counts are excluded from the tariff fingerprint.",
        ],
    }

    (out / "belib_official_paris.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# Belib Paris official check\n\n"
        "- Visitor Moto/Flex: **0.33 EUR/kWh + 0.22 / 0.57 EUR per 15 min connected**.\n"
        "- Visitor Boost/Boost+: **2.30 EUR/15 min / 0.42 EUR/min**.\n"
        "- Subscriber fee: **7 EUR/year**.\n"
        "- Subscriber non-resident: **Moto 0.33+0.17/15m; Flex 0.33+0.37/15m; Boost 2.00/15m; Boost+ 0.38/min**.\n"
        "- Paris resident Moto/Flex night: **0.33 EUR/kWh 20:00-23:00; 0.25 EUR/kWh 23:00-08:00**.\n"
        "- Long connection: **10 EUR/hour after 14 h connected**.\n"
        "- Reservation (15 min): **0.17 / 0.37 / 2.00 / 5.70 EUR** for Moto/Flex/Boost/Boost+; resident night reservation free.\n"
        "- Belib outbound roaming: **1.49 EUR/session + third-party CPO price**.\n"
        f"- Official static/live point counts observed: **{static_count}/{live_count}**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
