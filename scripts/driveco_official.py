#!/usr/bin/env python3
"""Extract DRIVECO France charging rules from official public sources."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

SOURCES = {
    "pricing": "https://driveco.com/borne-recharge-voiture-electrique/",
    "drivers": "https://driveco.com/conducteurs/",
    "howTo": "https://driveco.com/comment-recharger-borne-de-recharge-driveco/",
    "terms": "https://driveco.com/cgvu/",
    "inventoryDataset": "https://www.data.gouv.fr/datasets/liste-des-bornes-de-recharge-ouvertes-au-public",
    "inventoryCsv": "https://www.data.gouv.fr/api/1/datasets/r/775dd5a9-c0e4-4bb7-8995-f4b5a4148836",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,text/csv,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=50) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw, charset


def text_from_html(raw: bytes, charset: str) -> str:
    s = raw.decode(charset, errors="replace")
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require_any(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def find_price(text: str, value: str) -> bool:
    # Accept comma/dot decimal and arbitrary spacing around EUR/kWh rendering.
    major, minor = value.split(".")
    return bool(re.search(rf"(?<!\d){major}[,.]{minor}(?!\d)\s*€?\s*/?\s*kwh", norm(text), flags=re.I))


def first_matching(row: dict[str, str], names: tuple[str, ...]) -> str | None:
    lowered = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k is not None}
    for name in names:
        v = lowered.get(name.lower())
        if v:
            return v
    return None


def parse_float(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"-?\d+(?:[,.]\d+)?", value)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_inventory(raw: bytes) -> dict:
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    except csv.Error:
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if len(rows) < 1000:
        raise RuntimeError(f"DRIVECO inventory unexpectedly small: {len(rows)} rows")

    def station(row: dict[str, str]) -> dict:
        address = first_matching(row, ("adresse_station", "adresse", "address"))
        postal = first_matching(row, ("code_postal", "code_postal_station", "postal_code"))
        city = first_matching(row, ("consolidated_commune", "nom_commune", "commune", "ville"))
        return {
            "stationName": first_matching(row, ("nom_station", "n_station", "nom_enseigne", "station_name")),
            "address": address,
            "postalCode": postal,
            "city": city,
            "powerKwObserved": parse_float(first_matching(row, ("puissance_nominale", "puissance_nominale_kw", "power"))),
            "evseId": first_matching(row, ("id_pdc_itinerance", "id_pdc_local", "id_pdc")),
            "stationId": first_matching(row, ("id_station_itinerance", "id_station_local", "id_station")),
        }

    preferred: list[dict] = []
    used: set[str] = set()
    for dept in ("78", "91", "77"):
        for row in rows:
            item = station(row)
            hay = " ".join(x for x in (item.get("address"), item.get("postalCode"), item.get("city")) if x)
            if re.search(rf"\b{dept}\d{{3}}\b", hay):
                key = item.get("evseId") or item.get("stationId") or json.dumps(item, sort_keys=True)
                if key not in used:
                    used.add(key)
                    item["targetDepartment"] = dept
                    preferred.append(item)
                break
    if len(preferred) < 3:
        for row in rows:
            item = station(row)
            key = item.get("evseId") or item.get("stationId") or json.dumps(item, sort_keys=True)
            if key in used:
                continue
            used.add(key)
            item["targetDepartment"] = None
            preferred.append(item)
            if len(preferred) >= 3:
                break

    return {
        "rowCount": len(rows),
        "publisher": "DRIVECO",
        "publisherLastUpdateKnown": "2026-07-21",
        "freshnessStatus": "official_static_inventory_recent_not_live_availability",
        "samples": preferred[:3],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/driveco")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    texts: dict[str, str] = {}
    statuses: dict[str, int] = {}
    inventory_raw: bytes | None = None
    for key, url in SOURCES.items():
        status, raw, charset = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        if key == "inventoryCsv":
            inventory_raw = raw
        else:
            texts[key] = text_from_html(raw, charset)

    pricing = texts["pricing"]
    drivers = texts["drivers"]
    how_to = texts["howTo"]
    terms = texts["terms"]

    for value in ("0.39", "0.51", "0.55", "0.59"):
        if not find_price(pricing, value):
            raise RuntimeError(f"DRIVECO published reference price {value} EUR/kWh not found")

    require_any(drivers, ("chaque borne possede sa propre grille tarifaire",), "DRIVECO station-specific tariff")
    require_any(drivers, ("affiches avant le demarrage de la recharge", "affiche avant le demarrage de la recharge"), "DRIVECO pre-charge price display")
    require_any(drivers, ("n'a pas le controle sur le prix", "operateur de mobilite"), "DRIVECO roaming price separation")
    require_any(how_to, ("via l'application",), "DRIVECO app payment")
    require_any(how_to, ("via le qr code",), "DRIVECO QR payment")
    require_any(how_to, ("par carte bancaire",), "DRIVECO bank-card payment")
    require_any(how_to, ("badge d'interoperabilite",), "DRIVECO interoperability badge")

    require_any(terms, ("tarification applicable", "application driveco ou sur le portail web"), "DRIVECO exact tariff source")
    require_any(terms, ("demande de pre-autorisation",), "DRIVECO preauthorization")
    require_any(terms, ("montant de la demande de pre-autorisation figure sur l'application driveco ou sur le portail web",), "DRIVECO variable preauthorization")
    require_any(terms, ("indemnite forfaitaire de stationnement prolongee",), "DRIVECO prolonged-parking fee")
    require_any(terms, ("penalites de stationnement",), "DRIVECO local parking penalties")
    require_any(terms, ("service de recharge tiers", "badge tiers"), "DRIVECO third-party roaming")
    require_any(terms, ("depasse 0,1 kwh",), "DRIVECO billing threshold")

    if inventory_raw is None:
        raise RuntimeError("DRIVECO inventory CSV not fetched")
    inventory = parse_inventory(inventory_raw)

    facts = {
        "classification": {
            "singleGuaranteedNationalTariff": False,
            "stationLevelPriceLookupRequiredForExactSimulation": True,
            "reason": "DRIVECO publishes consumer reference prices but explicitly states that each charger has its own tariff grid and exact pricing is shown before charging.",
        },
        "publishedReferencePricing": {
            "classification": "operator_published_reference_not_station_guarantee",
            "slow": {"eurPerKwh": 0.39},
            "fast": {"eurPerKwh": 0.51},
            "ultraFast": {"eurPerKwhMin": 0.55, "eurPerKwhMax": 0.59},
            "mustNotReplaceExactStationPrice": True,
        },
        "operatorDirect": {
            "application": {"available": True, "exactStationPriceShownBeforeCharge": True},
            "qrWebPortal": {"available": True, "exactStationPriceShownBeforeCharge": True},
            "bankCard": {"availableWhereTerminalPresent": True},
            "drivecoBadge": {"available": True, "requiresPaymentMethodOnAccount": True},
            "autocharge": {"availableWhereConfigured": True},
        },
        "roaming": {
            "classification": "third_party_eMSP",
            "operatorDirect": False,
            "badgeInteroperabilitySupported": True,
            "priceControlledByThirdPartyProvider": True,
            "mustNotBeClassifiedAsDrivecoDirect": True,
        },
        "fees": {
            "extendedParking": {
                "status": "station_specific_possible",
                "networkWideAmountEur": None,
                "trigger": "use beyond time strictly necessary for full recharge",
                "amountShownInSelectedChargePointTariff": True,
                "localThirdPartyParkingPenaltiesMayAlsoApply": True,
            },
            "paymentPreauthorization": {
                "status": "amount_displayed_in_app_or_web_portal",
                "networkWideAmountEur": None,
                "canCapAndAutomaticallyStopSession": True,
            },
        },
        "sessionRules": {
            "billingStartsAfterEnergyDeliveredKwhExceeds": 0.1,
            "sessionCanStopAt": ["cable_disconnection", "preauthorization_amount_reached", "remote_stop_by_driveco"],
        },
        "inventory": inventory,
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "driveco-official-france",
        "generatedAt": now_iso(),
        "operator": "DRIVECO",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "drivecoOfficialPages": True,
            "technicalInventoryPublishedByDrivecoOnDataGouv": True,
            "sources": [{"key": key, "url": url, "httpStatus": statuses.get(key)} for key, url in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Do not use the 0.39/0.51/0.55-0.59 EUR/kWh consumer references as universal station tariffs.",
            "Exact DRIVECO direct price must be resolved from the selected charge point before simulation.",
            "Third-party badge pricing belongs to the eMSP and must remain separate from DRIVECO direct pricing.",
            "Extended-parking fees and local parking penalties require station/site-level resolution.",
            "The official static IRVE inventory is recent but is not live availability.",
        ],
    }

    (out / "driveco_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# DRIVECO France official check\n\n"
        "- Guaranteed national tariff: **none**; exact station lookup required.\n"
        "- Published consumer references: **0.39 / 0.51 / 0.55-0.59 EUR/kWh**.\n"
        "- Direct access: **app, QR/web, bank card where present, DRIVECO badge, Autocharge where configured**.\n"
        "- Third-party badge: **eMSP roaming price**, not DRIVECO direct.\n"
        "- Preauthorization: **amount shown per flow**, no network-wide amount asserted.\n"
        "- Extended parking fee: **possible and station-specific**; local penalties can also apply.\n"
        f"- Official DRIVECO static IRVE rows: **{inventory['rowCount']}**.\n"
        f"- Samples retained: **{len(inventory['samples'])}**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
