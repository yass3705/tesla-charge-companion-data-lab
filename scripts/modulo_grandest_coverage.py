#!/usr/bin/env python3
"""Confirm Modulo Energies coverage in Grand Est without duplicating its operator tariff validator."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SIEM = "https://www.siem51.fr/vehicules-electriques/"
MODULO_DATA = Path("data/operator_direct/modulo_official_centre.json")


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(getattr(r, "status", 200)), r.read(), r.geturl()


def plain(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require(text: str, *items: str):
    n = norm(text)
    missing = [x for x in items if norm(x) not in n]
    if missing:
        raise RuntimeError("Modulo Grand Est coverage evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/modulo_grandest")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if not MODULO_DATA.exists():
        raise RuntimeError("Existing validated Modulo operator dataset is missing")
    modulo = json.loads(MODULO_DATA.read_text())
    if modulo.get("operator") != "Modulo Energies" or modulo.get("tccDecision", {}).get("operatorValidated") is not True:
        raise RuntimeError("Existing Modulo operator validation is not usable")
    if modulo.get("tccDecision", {}).get("defaultDisplay") != "reference_only":
        raise RuntimeError("Modulo exact-price safety classification unexpectedly changed")

    status, raw, final = fetch(SIEM)
    if status != 200:
        raise RuntimeError(f"SIEM HTTP failure={status}")
    text = plain(raw)
    require(
        text,
        "Territoire d’énergie Marne",
        "Modulo Energies",
        "l’un des fondateurs",
        "Société Publique Locale",
        "accès à tous",
        "coûts raisonnés et identiques",
    )

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "modulo-grandest-coverage",
        "generatedAt": now(),
        "operator": "Modulo Energies",
        "country": "FR",
        "region": "Grand Est",
        "department": "Marne",
        "authority": "Territoire d’énergie Marne (SIEM)",
        "coverage": {
            "officiallyConfirmed": True,
            "siemFoundingMemberOfModulo": True,
            "publicAccess": True,
            "networkCostPolicyPublishedAsReasonedAndIdentical": True,
        },
        "operatorValidationReference": {
            "dataset": modulo.get("dataset"),
            "operatorValidated": True,
            "currentEnvelope": modulo.get("publishedCurrentEnvelope"),
            "defaultDisplay": "reference_only",
        },
        "tccDecision": {
            "grandEstCoverageValidated": True,
            "reuseExistingModuloOperatorRules": True,
            "createSeparateGrandEstTariff": False,
            "rankableWithoutLocalConfirmation": False,
            "note": "Modulo is officially confirmed in the Marne. Reuse the already validated Modulo operator envelope; do not duplicate or rank its from-prices as exact Grand Est station prices until a station/local exact tariff is resolved.",
        },
        "sourceEvidence": {
            "officialOnly": True,
            "siemUrl": final,
            "siemHttpStatus": status,
            "siemSha256": hashlib.sha256(raw).hexdigest(),
            "existingOperatorDatasetPath": str(MODULO_DATA),
        },
        "publicationStatus": "validated_candidate",
    }
    sig = {k: payload[k] for k in ("coverage", "operatorValidationReference", "tccDecision")}
    payload["sourceEvidence"]["relevantCoverageFingerprintSha256"] = hashlib.sha256(
        json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (out / "modulo_grandest_coverage.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(
        "# Modulo Energies — Grand Est / Marne\n\n"
        "Territoire d'énergie Marne officially confirms that it is a founding member of SPL Modulo and uses the network for public EV charging. The existing Modulo operator validation is reused unchanged: published 0.52/0.40 EUR/kWh values are starting-price references, not universal exact station tariffs, so ranking still requires local/station confirmation.\n"
    )


if __name__ == "__main__":
    main()
