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
SYDESL_MOBILITY = "https://sydesl.fr/mobilite-durable/"
SYDESL_TARIFF_PDF = "https://sydesl.fr/wp-content/uploads/2026/05/AG-CT01-autunois.pdf"
QWELLO_PUBLIC_TARIFF_URL = "https://qwello.fr/fr"
QWELLO_PUBLIC_EXPERIENCE_URL = "https://qwello.fr/fr/experience"


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
    sydesl_raw, sydesl_status = fetch_bytes(SYDESL_MOBILITY)
    pdf_raw, pdf_status = fetch_bytes(SYDESL_TARIFF_PDF)
    if min(sydesl_status, pdf_status) != 200:
        raise RuntimeError("One or more official SYDESL sources returned non-200")

    sydesl = html_text(sydesl_raw)
    tariff_pdf = pdf_text(pdf_raw)

    require(sydesl,
        "C’est l’opérateur QWELLO qui a été retenu",
        "désormais le propriétaire des bornes déployées",
        "repris les bornes installées initialement par le SYDESL",
    )
    require(tariff_pdf, "QWELLO", "22 kW AC")
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
                "timeComponentBasis": "connection_or_infrastructure_time",
                "tariffStatus": "initial_published_tariff",
            },
            "currentTariffModel": {
                "exactCurrentPriceMachineVerified": False,
                "stationOrAppLookupRequired": True,
                "publicTariffPage": QWELLO_PUBLIC_TARIFF_URL,
            },
        },
        "access": {
            "currentDirectAccessMethodsMachineVerified": False,
            "publicExperiencePage": QWELLO_PUBLIC_EXPERIENCE_URL,
        },
        "roaming": {
            "retailPriceMachineVerifiedInThisRun": False,
            "mustRemainSeparateFromDirectTariff": True,
        },
        "technical": {
            "saoneEtLoireQwelloDeploymentPowerKw": 22,
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
                {"key": "sydeslOfficialMobility", "url": SYDESL_MOBILITY, "httpStatus": sydesl_status, "rawSha256": hashlib.sha256(sydesl_raw).hexdigest()},
                {"key": "sydeslOfficial2026TariffPresentation", "url": SYDESL_TARIFF_PDF, "httpStatus": pdf_status, "rawSha256": hashlib.sha256(pdf_raw).hexdigest()},
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "SYDESL is the public coordinating authority/source context, not the current CPO for the Qwello stations it coordinated.",
            "The 0.30 EUR/kWh + 0.02 EUR/min figure is preserved exactly as an initial 2026 Qwello tariff for 22 kW AC in the official SYDESL presentation.",
            "Qwello public pages are JavaScript-rendered and are intentionally not blocking machine evidence in this GitHub workflow.",
            "A permanent France-wide Qwello tariff is not asserted; exact current pricing must be checked at station/app level.",
            "Direct-access and roaming retail details are not machine-validated in this run and must remain separate until independently verified.",
        ],
    }

    out = Path("out/qwello_saone_et_loire")
    out.mkdir(parents=True, exist_ok=True)
    (out / "qwello_saone_et_loire_official.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    summary = [
        "# Qwello Saône-et-Loire official check",
        "",
        "- Qwello, not SYDESL, is the current CPO/owner for inherited and new SYDESL-coordinated stations.",
        "- Official SYDESL 2026 initial tariff: 0.30 EUR/kWh + 0.02 EUR/min TTC for Qwello 22 kW AC.",
        "- Exact current Qwello station price is intentionally not generalized from that initial tariff.",
        "- Qwello JS-rendered pages are non-blocking; station/app lookup remains required for the current price.",
        "- Roaming retail remains separate and unasserted until independently machine-verified.",
        f"- Fingerprint: `{fingerprint}`",
    ]
    (out / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
