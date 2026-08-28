#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from pypdf import PdfReader

TARIFF_URL = "https://eniplenitude.com/mobilita-elettrica/tariffe-ricarica-auto-elettrica"
OFFER_URL = "https://eniplenitude.com/mobilita-elettrica/offerta-estate-ricarica"
EXCLUSION_PDF = "https://eniplenitude.com/content/dam/plenitude-it/documenti/pdf/e-mobility/promo-estate-2026/potr_colonnine_conto_terzi_escluse_da_offerta_estate_2026.pdf"
OUT = Path("data/reports/plenitude_italy_official.json")
OUT_MD = Path("data/reports/plenitude_italy_official.md")
UA = "tesla-charge-companion-data-lab/plenitude-italy-1.0"


def fetch(url: str) -> requests.Response:
    r = requests.get(url, timeout=45, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9,en;q=0.5"})
    r.raise_for_status()
    return r


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def require(text: str, *tokens: str) -> None:
    low = text.lower().replace(" ", " ")
    missing = [t for t in tokens if t.lower() not in low]
    if missing:
        raise RuntimeError("missing official Plenitude markers: " + ", ".join(missing))


def main() -> None:
    tariff = fetch(TARIFF_URL)
    offer = fetch(OFFER_URL)
    page_text = norm(tariff.text + " " + offer.text)

    require(page_text, "0,53", "0,60", "0,65", "0,12", "0,20", "0,30", "60 minuti", "30/09/2026")
    require(page_text, "rete proprietaria", "escluse", "app", "RFID")

    pdf = fetch(EXCLUSION_PDF)
    pdf_sha = hashlib.sha256(pdf.content).hexdigest()
    reader = PdfReader(io.BytesIO(pdf.content))
    pages = [(page.extract_text() or "") for page in reader.pages]
    exclusion_text = "\n".join(pages)
    exclusion_lines = [re.sub(r"\s+", " ", line).strip() for line in exclusion_text.splitlines()]
    exclusion_lines = [line for line in exclusion_lines if line]

    payload = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "operator": "Plenitude On The Road",
        "country": "IT",
        "punPartyId": "BEC",
        "currentOffer": {
            "validFrom": "2026-06-01",
            "validThrough": "2026-09-30T23:59:59+02:00",
            "requiresRegisteredUser": True,
            "activationMethods": ["app", "RFID"],
            "ownNetworkOnly": True,
            "exceptionsExist": True,
            "ratesEurPerKwh": {
                "quickAcUpTo22Kw": 0.53,
                "fastDcUpTo75Kw": 0.60,
                "fastPlusUltraFastDcFrom75Kw": 0.65
            },
            "classificationNotes": [
                "AC connectors installed on Fast/Fast+/UltraFast stations follow the station tariff class.",
                "The summer offer excludes stations explicitly identified by Plenitude in the station detail and official exclusion list."
            ]
        },
        "overstay": {
            "graceMinutesAfterChargingEnds": 60,
            "quickAc": {"eurPerMinute": 0.12, "inactiveWindow": "23:00-07:00"},
            "fastDc": {"eurPerMinute": 0.20, "active": "24h"},
            "fastPlusUltraFastDc": {"eurPerMinute": 0.30, "active": "24h"}
        },
        "publicationPolicy": {
            "candidateForTcc": True,
            "rankableWithoutExceptionResolution": False,
            "failClosedReason": "official summer offer has explicit excluded third-party-account stations; exclusion list must be matched before broad PUN BEC publication"
        },
        "exclusionList": {
            "url": EXCLUSION_PDF,
            "httpStatus": pdf.status_code,
            "pageCount": len(reader.pages),
            "sha256": pdf_sha,
            "extractedNonEmptyLineCount": len(exclusion_lines),
            "sample": exclusion_lines[:80]
        },
        "sources": [TARIFF_URL, OFFER_URL, EXCLUSION_PDF]
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        "# Plenitude On The Road Italy official tariff probe\n\n"
        "- PUN partyId: **BEC**\n"
        "- Summer 2026 own-network rates: **0.53 €/kWh AC <=22 kW; 0.60 €/kWh DC <=75 kW; 0.65 €/kWh DC >=75 kW**.\n"
        "- Valid through **30 September 2026 23:59** for registered app/RFID sessions.\n"
        "- 60-minute post-charge grace; then 0.12 €/min Quick AC (except 23:00-07:00), 0.20 €/min Fast DC, 0.30 €/min Fast+/UltraFast DC.\n"
        f"- Official exclusion PDF fetched: **{len(reader.pages)} pages**, sha256 `{pdf_sha}`.\n"
        "- Publication remains **fail-closed** until exclusion rows are matched to PUN stations.\n",
        encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
