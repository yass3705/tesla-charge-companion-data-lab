#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import tempfile
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
OWNER_URL = "https://sigeif.fr/index.php/comment-et-ou-recharger-votre-vehicule-electrique"
GUIDE_URL = "https://www.sigeif.fr/sites/default/files/2025-10/GUIDE%20D%27UTILISATION%20IRVE%202025%20OCTOBRE_0.pdf"
DATASET_URL = "https://www.data.gouv.fr/datasets/bornes-de-recharges-sigeif-1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def fetch_bytes(url: str, attempts: int = 3) -> tuple[bytes, int]:
    last = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "*/*",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read(), int(getattr(resp, "status", 200))
        except Exception as exc:
            last = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Unable to fetch {url} after {attempts} attempts: {last}")


def html_text(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def pdf_text(raw: bytes) -> str:
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "guide.pdf"
        txt = Path(td) / "guide.txt"
        pdf.write_bytes(raw)
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
        return txt.read_text(encoding="utf-8", errors="replace")


def require(text: str, *phrases: str) -> None:
    n = norm(text)
    missing = [p for p in phrases if norm(p) not in n]
    if missing:
        raise RuntimeError(f"Missing official evidence: {missing}")


def main() -> int:
    owner_raw, owner_status = fetch_bytes(OWNER_URL)
    guide_raw, guide_status = fetch_bytes(GUIDE_URL)
    dataset_raw, dataset_status = fetch_bytes(DATASET_URL)
    if min(owner_status, guide_status, dataset_status) != 200:
        raise RuntimeError("One or more official SIGEIF sources returned non-200")

    owner = html_text(owner_raw)
    guide = pdf_text(guide_raw)
    dataset = html_text(dataset_raw)

    require(owner,
        "Aucune carte d’accès spécifique ou abonnement n’est nécessaire",
        "application Izivia",
        "service « Paynow »",
        "Pass Izivia",
        "Les tarifs de la recharge s'appliquent à tout le réseau du Sigeif",
        "applicable depuis le 1er octobre 2024",
    )
    require(guide,
        "Borne douce",
        "Jusqu’à 7 kW",
        "Jusqu’à 22 kW",
        "Borne semi-rapide",
        "Jusqu’à 24 kW",
        "Borne rapide",
        "Jusqu’à 50 kW",
        "Borne très rapide",
        "Jusqu’à 100 kW",
        "0,39 €/kWh",
        "0,45 €/kWh",
        "0,49 €/kWh",
        "Après 3 heures : + 0,05 €/min",
        "Plafond de nuit : 4 €",
        "de 20 h à 8 h",
        "Après 2 heures : + 0,2 €/min",
        "Après 1 heure : + 0,3 €/min",
        "Aucun plafond de nuit",
    )
    require(dataset, "Bornes de recharges SIGEIF", "Izivia", "schema-irve-statique")

    shared_soft_fee = {
        "freeMinutes": 180,
        "eurPerMinuteAfter": 0.05,
        "nightWindow": "20:00-08:00",
        "nightCapEur": 4.0,
        "basis": "connection_time",
    }
    facts = {
        "classification": {
            "regionalPublicNetwork": True,
            "scope": "Ile-de-France member municipalities",
            "technicalOperator": "IZIVIA",
            "singleNetworkGridClaimedByOwner": True,
            "exactTariffFullyMachineVerifiedForAllPowerClasses": True,
        },
        "operatorDirect": {
            "upTo7Kw": {"eurPerKwh": 0.39, "connectionOrParkingFee": shared_soft_fee},
            "upTo22Kw": {"eurPerKwh": 0.39, "connectionOrParkingFee": shared_soft_fee},
            "upTo24Kw": {
                "eurPerKwh": 0.45,
                "connectionOrParkingFee": {"freeMinutes": 120, "eurPerMinuteAfter": 0.20, "nightCapEur": None, "basis": "connection_time"},
            },
            "upTo50Kw": {
                "eurPerKwh": 0.49,
                "connectionOrParkingFee": {"freeMinutes": 60, "eurPerMinuteAfter": 0.30, "nightCapEur": None, "basis": "connection_time"},
            },
            "upTo100Kw": {
                "eurPerKwh": 0.49,
                "connectionOrParkingFee": {"freeMinutes": 60, "eurPerMinuteAfter": 0.30, "nightCapEur": None, "basis": "connection_time"},
            },
        },
        "access": {
            "subscriptionRequired": False,
            "specificCardRequired": False,
            "iziviaApp": True,
            "paynowBankCardAdHoc": True,
            "passIzivia": True,
        },
        "roaming": {
            "incomingMobilityProvidersSupported": True,
            "mobilityProviderMaySetDifferentRetailPrice": True,
            "mustRemainSeparateFromDirectTariff": True,
        },
        "billing": {
            "energyUnit": "kWh",
            "parkingOrConnectionTimeUnit": "minute",
        },
    }

    fingerprint = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload = {
        "schemaVersion": "1.1.0",
        "dataset": "sigeif-official-ile-de-france",
        "generatedAt": now_iso(),
        "operator": "SIGEIF / IZIVIA",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": "networkOfficial", "url": OWNER_URL, "httpStatus": owner_status, "rawSha256": hashlib.sha256(owner_raw).hexdigest()},
                {"key": "officialGuide2025", "url": GUIDE_URL, "httpStatus": guide_status, "rawSha256": hashlib.sha256(guide_raw).hexdigest()},
                {"key": "officialStaticDataset", "url": DATASET_URL, "httpStatus": dataset_status, "rawSha256": hashlib.sha256(dataset_raw).hexdigest()},
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Current direct tariff grid is machine-validated against the official SIGEIF 2025 usage guide rather than fragile individual IZIVIA station URLs.",
            "Third-party mobility-provider retail prices remain separate from SIGEIF direct pricing.",
            "Reservation pricing is intentionally not asserted as current because it is not shown in the current official guide used for this validation.",
        ],
    }

    out = Path("out/sigeif")
    out.mkdir(parents=True, exist_ok=True)
    (out / "sigeif_official_ile_de_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = [
        "# SIGEIF / IZIVIA official check",
        "",
        "- 7/22 kW: 0.39 EUR/kWh; after 3h +0.05 EUR/min; night cap 4 EUR from 20:00 to 08:00.",
        "- 24 kW: 0.45 EUR/kWh; after 2h +0.20 EUR/min; no night cap.",
        "- 50/100 kW: 0.49 EUR/kWh; after 1h +0.30 EUR/min; no night cap.",
        "- No subscription or dedicated card required; IZIVIA app, Paynow and Pass IZIVIA supported.",
        f"- Fingerprint: `{fingerprint}`",
    ]
    (out / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
