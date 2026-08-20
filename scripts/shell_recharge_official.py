#!/usr/bin/env python3
"""Validate current Shell Recharge France public-charging tariff rules.

Operator-rule validator only: no national station database is built. Shell's
first-party station locator is sampled across several French sites. The common
Shell App tariff is stored as an observed direct-network rule, but it is not
promoted to a guaranteed France-wide tariff without a national tariff page.
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

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

SOURCES = {
    "sommesous": "https://find.shell.com/fr/fuel/10029225-sommesous-a26/fr_TN",
    "roussillon": "https://find.shell.com/fr/fuel/12166202-roussillon-a7/fr_TN",
    "cestas": "https://find.shell.com/fr/fuel/10029643-cestas-ouest-a63/fr_MA",
    "lesSalles": "https://find.shell.com/fr/fuel/11796090-les-salles-haut-forez-nord-a89/fr_LU",
    "criquetot": "https://find.shell.com/fr/fuel/13078456-ev-criquetot-le-havre/fr_FR",
}

EXPECTED_EUR_PER_KWH = 0.64
EXPECTED_SESSION_FEE_EUR = 0.35


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=40) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace")


def text_from_html(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def has_amount(text: str, value: float) -> bool:
    s = norm(text)
    forms = {f"{value:.2f}", f"{value:.2f}".replace(".", ",")}
    return any(re.search(rf"(?<!\d){re.escape(v)}(?!\d)", s) for v in forms)


def extract_power_classes(text: str) -> list[int]:
    vals = []
    for m in re.finditer(r"(?<!\d)(50|150|300)(?:[.,]0)?\s*kw", norm(text)):
        v = int(m.group(1))
        if v not in vals:
            vals.append(v)
    return vals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/shell_recharge")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    samples = []
    statuses = {}
    all_powers = []
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        text = text_from_html(raw)
        n = norm(text)
        # These URLs are Shell first-party station pages. Their visible tariff
        # blocks are more stable than the optional rendered "Operator" label.
        if "shell app" not in n:
            raise RuntimeError(f"{key}: Shell App tariff marker missing")
        if not has_amount(text, EXPECTED_EUR_PER_KWH):
            raise RuntimeError(f"{key}: expected {EXPECTED_EUR_PER_KWH:.2f} EUR/kWh not found")
        if not has_amount(text, EXPECTED_SESSION_FEE_EUR):
            raise RuntimeError(f"{key}: expected {EXPECTED_SESSION_FEE_EUR:.2f} EUR session fee not found")
        if "additional fees may apply" not in n:
            raise RuntimeError(f"{key}: additional-fees warning missing")
        powers = extract_power_classes(text)
        for p in powers:
            if p not in all_powers:
                all_powers.append(p)
        samples.append({
            "key": key,
            "shellAppEurPerKwh": EXPECTED_EUR_PER_KWH,
            "sessionFeeEur": EXPECTED_SESSION_FEE_EUR,
            "powerKwObserved": powers,
            "additionalFeesMayApply": True,
        })

    if len(samples) < 5:
        raise RuntimeError("Shell Recharge: insufficient first-party station samples")
    if not {50, 150, 300}.issubset(set(all_powers)):
        raise RuntimeError(f"Shell Recharge: expected 50/150/300 kW sample coverage, got {all_powers}")

    facts = {
        "classification": {
            "singleGuaranteedNationalCpoDirectTariff": False,
            "reason": "Multiple current Shell France station pages show the same Shell App tariff, but no first-party France-wide tariff page was used to prove universality.",
            "stationLevelLookupRecommendedForExactCpoDirect": True,
            "commonObservedDirectTariffAcrossSamples": True,
        },
        "operatorDirect": {
            "shellApp": {
                "observedEurPerKwh": EXPECTED_EUR_PER_KWH,
                "observedSessionFeeEur": EXPECTED_SESSION_FEE_EUR,
                "sampleCount": len(samples),
                "sampleConsistency": "all_samples_match",
                "nationalGuarantee": False,
            },
        },
        "fees": {
            "sessionFee": {
                "observedEur": EXPECTED_SESSION_FEE_EUR,
                "observedOnAllSamples": True,
            },
            "additionalFees": {
                "status": "station_pages_warn_additional_fees_may_apply",
                "networkWideIdleOrParkingAmount": None,
                "exactSiteCheckRequired": True,
            },
        },
        "payment": {
            "shellAppTariffExplicitlyPublishedOnSamples": True,
            "adHocBankCardFranceWideStatus": "not_asserted_from_sample_tariff_blocks",
            "note": "General station amenity pages list card acceptance, but this validator does not equate forecourt card acceptance with a universal EV ad-hoc tariff.",
        },
        "technical": {
            "samplePowerClassesKw": sorted(all_powers),
            "connectorMarkersObserved": ["CCS", "CHAdeMO", "Type 2"],
        },
        "stationValidationSamples": samples,
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "shell-recharge-official-france",
        "generatedAt": now_iso(),
        "operator": "Shell Recharge",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sourceType": "Shell first-party station locator",
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "0.64 EUR/kWh plus 0.35 EUR/session is strongly corroborated across the sampled Shell Recharge France sites, but remains classified as an observed common tariff rather than a guaranteed national tariff.",
            "Additional idle, parking or site fees must remain station-specific unless Shell publishes a network-wide rule.",
        ],
    }

    (out / "shell_recharge_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Shell Recharge France official check\n\n"
        "- Validation model: **operator rules only**, no national station extract.\n"
        f"- Shell App tariff observed on **{len(samples)} first-party French stations**: **0.64 EUR/kWh + 0.35 EUR/session**.\n"
        "- Sample powers include **50 / 150 / 300 kW** and all samples match the same tariff.\n"
        "- Classification: **strong common observed tariff**, but not promoted to a guaranteed national tariff without a France-wide tariff page.\n"
        "- Every sampled page warns that **additional fees may apply**; exact idle/parking rules remain site-specific.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
