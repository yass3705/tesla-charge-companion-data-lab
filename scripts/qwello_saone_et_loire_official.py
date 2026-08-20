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
QWELLO_HOME = "https://qwello.fr/fr"
QWELLO_EXPERIENCE = "https://qwello.fr/fr/experience"
SYDESL_MOBILITY = "https://sydesl.fr/mobilite-durable/"
SYDESL_TARIFF_PDF = "https://sydesl.fr/wp-content/uploads/2026/05/AG-CT01-autunois.pdf"


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


def require_regex(text: str, pattern: str, label: str) -> None:
    if not re.search(pattern, norm(text), flags=re.I):
        raise RuntimeError(f"Missing official evidence: {label}")


def main() -> int:
    home_raw, home_status = fetch_bytes(QWELLO_HOME)
    experience_raw, experience_status = fetch_bytes(QWELLO_EXPERIENCE)
    sydesl_raw, sydesl_status = fetch_bytes(SYDESL_MOBILITY)
    pdf_raw, pdf_status = fetch_bytes(SYDESL_TARIFF_PDF)
    if min(home_status, experience_status, sydesl_status, pdf_status) != 200:
        raise RuntimeError("One or more official Qwello/SYDESL sources returned non-200")

    home = html_text(home_raw)
    experience = html_text(experience_raw)
    sydesl = html_text(sydesl_raw)
    tariff_pdf = pdf_text(pdf_raw)

    require(sydesl,
        "C’est l’opérateur QWELLO qui a été retenu",
        "désormais le propriétaire des bornes déployées",
        "repris les bornes installées initialement par le SYDESL",
    )
    require(home,
        "redevance d'infrastructure",
        "0,30€/kWh",
        "0,02€/min",
        "tarifs d'itinérance",
    )
    require(experience,
        "Application Qwello",
        "Sans contact",
        "même si vous n'êtes pas encore enregistré",
    )
    require(tariff_pdf,
        "QWELLO",
        "22 kW AC",
    )
    require_regex(
        tariff_pdf,
        r"tarif initial de 0[,.]3\s*€/kwh\s*\+\s*0[,.]02\s*€/min\s*ttc\s*pour qwello",
        "SYDESL 2026 initial Qwello tariff 0.30 EUR/kWh + 0.02 EUR/min TTC",
    )

    facts = {
        "classification": {
            "chargePointOperator": "Qwello",
            "scope": "Saône-et-Loire rollout coordinated by SYDESL",
            "sydeslIsCurrentCpo": False,
            "qwelloOwnsNewAndInheritedSydeslStations": True,
            "publishedInitialTariffMachineVerified": True,
            "networkWideCurrentUniformTariffAsserted": False,
            "exactCurrentStationTariffLookupRequired": True,
        },
        "operatorDirect": {
            "saoneEtLoire22KwInitialPublishedTariff": {
                "powerKw": 22,
                "eurPerKwh": 0.30,
                "eurPerMinute": 0.02,
                "vatIncluded": True,
                "timeComponentBasis": "infrastructure_usage_time",
                "tariffStatus": "initial_published_tariff",
            },
            "pricingFramework": {
                "energyComponent": True,
                "infrastructureTimeComponent": True,
                "officialSiteShowsTariffByLocation": True,
                "perStationCurrentPriceMustBeChecked": True,
            },
            "officialQwelloSiteExample": {
                "location": "Amanlis",
                "eurPerKwh": 0.30,
                "eurPerMinute": 0.02,
                "nightCapEur": 3.60,
                "nightCapAppliesToInfrastructureFee": True,
                "mustNotBeGeneralizedToAllStations": True,
            },
        },
        "access": {
            "registrationRequired": False,
            "qwelloApp": True,
            "contactlessPayment": True,
            "qwelloCard": True,
        },
        "roaming": {
            "supported": True,
            "thirdPartyMobilityProviderTariffMayVary": True,
            "mustRemainSeparateFromQwelloDirectTariff": True,
        },
        "technical": {
            "saoneEtLoireQwelloDeploymentPowerKw": 22,
            "type2": True,
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "qwello-saone-et-loire-official-france",
        "generatedAt": now_iso(),
        "operator": "Qwello",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": "qwelloOfficialHome", "url": QWELLO_HOME, "httpStatus": home_status, "rawSha256": hashlib.sha256(home_raw).hexdigest()},
                {"key": "qwelloOfficialExperience", "url": QWELLO_EXPERIENCE, "httpStatus": experience_status, "rawSha256": hashlib.sha256(experience_raw).hexdigest()},
                {"key": "sydeslOfficialMobility", "url": SYDESL_MOBILITY, "httpStatus": sydesl_status, "rawSha256": hashlib.sha256(sydesl_raw).hexdigest()},
                {"key": "sydeslOfficial2026TariffPresentation", "url": SYDESL_TARIFF_PDF, "httpStatus": pdf_status, "rawSha256": hashlib.sha256(pdf_raw).hexdigest()},
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "SYDESL is kept as the public coordinating authority/source context, not as the current charge-point operator for these stations.",
            "The 0.30 EUR/kWh + 0.02 EUR/min figure is preserved exactly as the official SYDESL 2026 presentation labels it: an initial Qwello tariff for 22 kW AC in Saône-et-Loire.",
            "Qwello's official site confirms an energy-plus-infrastructure-time pricing model, but displays tariffs by location; therefore a single permanent France-wide tariff is not asserted.",
            "The Amanlis night cap is stored only as an official Qwello site example and must not be copied to Saône-et-Loire stations without station-level confirmation.",
            "Roaming/eMSP retail prices remain separate from Qwello direct pricing.",
        ],
    }

    out = Path("out/qwello_saone_et_loire")
    out.mkdir(parents=True, exist_ok=True)
    output = out / "qwello_saone_et_loire_official.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = [
        "# Qwello Saône-et-Loire official check",
        "",
        "- Qwello, not SYDESL, is the current CPO/owner for the inherited and new SYDESL-coordinated 22 kW network.",
        "- Official SYDESL 2026 initial tariff: 0.30 EUR/kWh + 0.02 EUR/min TTC for Qwello 22 kW AC.",
        "- Qwello direct pricing combines energy and infrastructure-time components.",
        "- No preregistration is required; app and contactless payment are supported.",
        "- Exact current tariff remains station/location-specific; roaming prices stay separate.",
        f"- Fingerprint: `{fingerprint}`",
    ]
    (out / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
