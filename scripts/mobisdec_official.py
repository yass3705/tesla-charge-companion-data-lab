#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import io
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
MOBISDEC_URL = "https://mobisdec.fr/"
SDEC_MOBILITY_URL = "https://www.sdec-energie.fr/node/110"
SDEC_2026_PDF = "https://www.sdec-energie.fr/sites/sdec.createurdimage.fr/files/note_annexes_csdec_01_2026_12_fevrier.pdf"
DATASET_PAGE = "https://www.data.gouv.fr/datasets/bornes-de-recharge-pour-vehicules-electriques-mobisdec"
DATASET_CSV = "https://www.data.gouv.fr/api/1/datasets/r/3a84cede-2dae-4313-9b0d-13b097e3fc4a"


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
            with urllib.request.urlopen(req, timeout=60) as resp:
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
        pdf = Path(td) / "source.pdf"
        txt = Path(td) / "source.txt"
        pdf.write_bytes(raw)
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
        return txt.read_text(encoding="utf-8", errors="replace")


def require(text: str, *phrases: str) -> None:
    n = norm(text)
    missing = [p for p in phrases if norm(p) not in n]
    if missing:
        raise RuntimeError(f"Missing official evidence: {missing}")


def parse_csv(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [dict(r) for r in csv.DictReader(io.StringIO(text), dialect=dialect)]


def row_blob(row: dict[str, str]) -> str:
    return norm(" | ".join(str(v or "") for v in row.values()))


def first_matching(rows: list[dict[str, str]], needle: str) -> dict[str, str] | None:
    n = norm(needle)
    for row in rows:
        if n in row_blob(row):
            return row
    return None


def compact_station(row: dict[str, str] | None) -> dict | None:
    if not row:
        return None
    wanted = [
        "id_station_itinerance", "id_pdc_itinerance", "nom_station", "adresse_station",
        "code_insee_commune", "nom_enseigne", "nom_operateur", "puissance_nominale",
        "prise_type_2", "prise_type_combo_ccs", "prise_type_chademo", "gratuit",
    ]
    out = {k: row.get(k) for k in wanted if row.get(k) not in (None, "")}
    if not out:
        # Schema-safe fallback: keep a small public subset by recognizable labels.
        for k, v in row.items():
            nk = norm(k)
            if v and any(t in nk for t in ("station", "adresse", "commune", "operateur", "puissance", "id_pdc", "id_station")):
                out[k] = v
            if len(out) >= 10:
                break
    return out


def main() -> int:
    mob_raw, mob_status = fetch_bytes(MOBISDEC_URL)
    sdec_raw, sdec_status = fetch_bytes(SDEC_MOBILITY_URL)
    pdf_raw, pdf_status = fetch_bytes(SDEC_2026_PDF)
    ds_raw, ds_status = fetch_bytes(DATASET_PAGE)
    csv_raw, csv_status = fetch_bytes(DATASET_CSV)
    if min(mob_status, sdec_status, pdf_status, ds_status, csv_status) != 200:
        raise RuntimeError("One or more official MobiSDEC/SDEC/data.gouv sources returned non-200")

    mob = html_text(mob_raw)
    sdec = html_text(sdec_raw)
    pdf = pdf_text(pdf_raw)
    ds = html_text(ds_raw)

    # Current public operator site: energy grid and access methods.
    require(mob,
        "0,42 €/kWh", "0,47 €/kWh", "0,52 €/kWh", "0,57 €/kWh", "0,62 €/kWh",
        "10 € par badge", "QR code", "application Mobisdec", "Carte Bancaire",
        "recharge terminée depuis 15min", "0,21 €/min", "minuit à 7h00",
        "badges d’autres opérateurs",
    )

    # Formal 2026 SDEC decision: authoritative approved tariff from 1 June 2026.
    require(pdf,
        "42.0 cts €", "47.0 cts €", "52.0 cts €", "57.0 cts €", "62.0 cts €",
        "22 cts €", "1er juin 2026", "24h00 et 07h00",
        "badge d’un autre opérateur de mobilité", "carte de paiement bancaire sans contact",
    )

    # Ownership / operating context and current technical operator.
    require(sdec, "527 bornes", "Load Stations", "réseau de bornes")
    require(ds, "MOBISDEC", "Load Stations", "schema-irve-statique")

    rows = parse_csv(csv_raw)
    if len(rows) < 100:
        raise RuntimeError(f"MobiSDEC technical dataset unexpectedly small: {len(rows)} rows")
    samples = {
        "caen": compact_station(first_matching(rows, "Caen")),
        "bayeux": compact_station(first_matching(rows, "Bayeux")),
        "vireNormandie": compact_station(first_matching(rows, "Vire Normandie") or first_matching(rows, "Vire")),
    }
    if not all(samples.values()):
        raise RuntimeError(f"Could not resolve all station samples from official technical dataset: {samples}")

    facts = {
        "classification": {
            "regionalPublicNetwork": True,
            "scope": "Calvados",
            "networkOwner": "SDEC Énergie",
            "serviceBrand": "MobiSDEC",
            "technicalOperator2026": "Load Stations",
            "officialTechnicalDatasetRows": len(rows),
            "energyTariffMachineVerified": True,
            "immobilizationFeeSourceDiscrepancy": True,
        },
        "operatorDirect": {
            "effectiveFrom": "2026-06-01",
            "energyTariffs": {
                "slow7Kva": {"eurPerKwh": 0.42},
                "normal22To25Kva": {"eurPerKwh": 0.47},
                "rapid50Kva": {"eurPerKwh": 0.52},
                "rapid100Kva": {"eurPerKwh": 0.57},
                "rapid150KvaAndAbove": {"eurPerKwh": 0.62},
            },
            "immobilization": {
                "graceAfterChargeCompleteMinutes": 15,
                "formalSdec2026ApprovedEurPerMinute": 0.22,
                "mobisdecWebsiteDisplayedEurPerMinute": 0.21,
                "nightWaiverWindow": "00:00-07:00",
                "nightWaiverAppliesToImmobilizationOnly": True,
                "energyStillBillableAtNight": True,
                "recommendedCalculatorValue": None,
                "manualBillingCheckRequired": True,
            },
            "account": {"badgeOpeningFeeEur": 10.0},
        },
        "accessChannels": {
            "mobisdecBadge": True,
            "mobisdecApp": True,
            "qrAdHoc": True,
            "qrSubscriptionRequired": False,
            "contactlessBankCard": True,
            "contactlessRestrictedToRapidStations": True,
            "separateDirectEnergyPriceByChannelPublished": False,
        },
        "roaming": {
            "incomingThirdPartyBadgesSupported": True,
            "thirdPartyRetailPriceMachineVerified": False,
            "mustRemainSeparateFromMobisdecDirectTariff": True,
            "mobisdecBadgeOutgoingRoamingSupported": True,
        },
        "technical": {
            "slowPowerKwRange": "3-7",
            "normalAcPowerKw": 22,
            "normalDcPowerKva": "25-30",
            "rapidPowerKwRange": "43-180",
            "stationExamplesFromOfficialDataset": samples,
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "mobisdec-official-calvados",
        "generatedAt": now_iso(),
        "operator": "MobiSDEC / SDEC Énergie",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": "mobisdecOfficial", "url": MOBISDEC_URL, "httpStatus": mob_status, "rawSha256": hashlib.sha256(mob_raw).hexdigest()},
                {"key": "sdecMobilityOfficial", "url": SDEC_MOBILITY_URL, "httpStatus": sdec_status, "rawSha256": hashlib.sha256(sdec_raw).hexdigest()},
                {"key": "sdecFormal2026Decision", "url": SDEC_2026_PDF, "httpStatus": pdf_status, "rawSha256": hashlib.sha256(pdf_raw).hexdigest()},
                {"key": "dataGouvDatasetPage", "url": DATASET_PAGE, "httpStatus": ds_status, "rawSha256": hashlib.sha256(ds_raw).hexdigest()},
                {"key": "dataGouvTechnicalCsv", "url": DATASET_CSV, "httpStatus": csv_status, "rawSha256": hashlib.sha256(csv_raw).hexdigest()},
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source_with_fee_discrepancy",
        "notes": [
            "The five 2026 energy prices are consistent between the public MobiSDEC site and the formal SDEC tariff decision effective 1 June 2026.",
            "The immobilization fee is not safe to publish as a single calculator value yet: the formal SDEC 2026 decision says 0.22 EUR/min, while the current MobiSDEC public page still displays 0.21 EUR/min.",
            "Both sources agree that immobilization starts 15 minutes after charging ends and is waived from 00:00 to 07:00 while energy remains billable.",
            "No distinct member/app/QR direct-energy grid is published; third-party roaming retail pricing remains separate.",
        ],
    }

    out = Path("out/mobisdec")
    out.mkdir(parents=True, exist_ok=True)
    (out / "mobisdec_official_calvados.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = [
        "# MobiSDEC / SDEC Énergie official check",
        "",
        "- Effective 2026 direct energy grid: 7 kVA 0.42; 22/25 kVA 0.47; 50 kVA 0.52; 100 kVA 0.57; >=150 kVA 0.62 EUR/kWh.",
        "- Badge opening fee: 10 EUR; QR ad-hoc and app supported; contactless bank card is limited to rapid stations.",
        "- Immobilization begins 15 min after charge completion and is waived 00:00-07:00, but the fee is DISPUTED across official sources: formal 2026 SDEC decision 0.22 EUR/min vs current MobiSDEC page 0.21 EUR/min.",
        "- Calculator immobilization value intentionally left unset pending a live billed-session/app check.",
        f"- Official technical dataset rows: {len(rows)}; sample stations resolved in Caen, Bayeux and Vire Normandie.",
        f"- Fingerprint: `{fingerprint}`",
    ]
    (out / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
