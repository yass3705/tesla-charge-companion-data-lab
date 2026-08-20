#!/usr/bin/env python3
"""Collect and validate official Révéo public pricing metadata and OCPI tariff evidence.

Important classification rule:
- The public Révéo pricing page is the authority for direct/public access structure,
  badge/subscription pricing and the fact that some territories use different grids.
- The JSON linked from Révéo's "Tarif Roaming" page is an OCPI/GIREVE technical
  tariff feed. It is preserved separately and MUST NOT be relabelled as direct
  retail pricing without an independent direct-public confirmation.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
PRICING_URL = "https://reveocharge.com/tarifs/"
HOW_URL = "https://reveocharge.com/comment-ca-marche/"
ROAMING_PAGE_URL = "https://reveocharge.com/tarif-roaming/"
OCPI_URL = "https://roaming.road.io/files/2ac5b1b4-2d18-4578-98fe-53db518e1a63/tariffs.json"
OUT = Path("out/reveo")


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat().replace("+00:00", "Z")


def fetch(url: str, attempts: int = 3) -> tuple[int, bytes]:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=45) as resp:
                return int(getattr(resp, "status", 200)), resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Unable to fetch {url} after {attempts} attempts: {last}")


def text_from_html(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("’", "'").replace(" ", " ")).strip()


def require(text: str, snippets: list[str], key: str) -> None:
    n = norm(text)
    for snippet in snippets:
        if norm(snippet) not in n:
            raise RuntimeError(f"{key}: required evidence missing: {snippet}")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def active_tariff(item: dict, at: datetime) -> bool:
    start = parse_dt(item.get("start_date_time"))
    end = parse_dt(item.get("end_date_time"))
    return (start is None or start <= at) and (end is None or at < end)


def human_text(item: dict) -> str | None:
    for entry in item.get("tariff_alt_text") or []:
        if entry.get("language") == "fr" and entry.get("text"):
            return re.sub(r"\s+", " ", str(entry["text"])).strip()
    entries = item.get("tariff_alt_text") or []
    if entries and entries[0].get("text"):
        return re.sub(r"\s+", " ", str(entries[0]["text"])).strip()
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    p_status, p_raw = fetch(PRICING_URL)
    h_status, h_raw = fetch(HOW_URL)
    r_status, r_raw = fetch(ROAMING_PAGE_URL)
    o_status, o_raw = fetch(OCPI_URL)
    if any(x != 200 for x in (p_status, h_status, r_status, o_status)):
        raise RuntimeError(f"Unexpected HTTP statuses: pricing={p_status}, how={h_status}, roaming={r_status}, ocpi={o_status}")

    pricing = text_from_html(p_raw)
    how = text_from_html(h_raw)
    roaming = text_from_html(r_raw)

    require(pricing, [
        "Le prix du badge Révéo : 12,00€",
        "Abonnement Révéo : 1,50€/mois/badge",
        "jusqu’à 50% de remise",
        "Hérault",
        "Pyrénées-Orientales",
        "Toulouse Métropole",
        "prix à la minute",
        "durée de connexion",
    ], "pricing")
    require(how, [
        "Scanner le QR code",
        "tarif public",
        "sans s’abonner",
        "réseaux partenaires",
    ], "how")
    require(roaming, [
        "transmise en OCPI via GIREVE",
        "FR*M31 / FR*S48 / FR*S12 / FR*S34",
        "tariffs.json",
    ], "roaming")

    tariffs = json.loads(o_raw.decode("utf-8", errors="strict"))
    if not isinstance(tariffs, list) or not tariffs:
        raise RuntimeError("OCPI tariff feed is empty or not a list")

    at = now()
    party_ids = sorted({str(x.get("party_id")) for x in tariffs if x.get("party_id")})
    required_parties = {"M31", "S48", "S12", "S34"}
    if not required_parties.issubset(set(party_ids)):
        raise RuntimeError(f"OCPI feed missing expected operation codes: {sorted(required_parties - set(party_ids))}")

    active = [x for x in tariffs if active_tariff(x, at)]
    if not active:
        raise RuntimeError("OCPI feed has no currently active tariffs")

    compact = []
    for item in active:
        txt = human_text(item)
        compact.append({
            "countryCode": item.get("country_code"),
            "partyId": item.get("party_id"),
            "tariffId": item.get("id"),
            "currency": item.get("currency"),
            "grossTtcDisplayText": txt,
            "startDateTime": item.get("start_date_time"),
            "endDateTime": item.get("end_date_time"),
            "lastUpdated": item.get("last_updated"),
            "machineComponents": item.get("elements"),
            "classification": "cpo_ocpi_tariff_transmitted_to_roaming_via_gireve",
        })

    readable = [x for x in compact if x["grossTtcDisplayText"]]
    if len(readable) < 8:
        raise RuntimeError(f"Too few human-readable active OCPI tariffs: {len(readable)}")

    feed_sha = hashlib.sha256(o_raw).hexdigest()
    relevant = {
        "publicAccess": {
            "subscriptionRequired": False,
            "qrBankCardAdHoc": True,
            "appWithoutSubscription": True,
            "publicTariffShownInApp": True,
        },
        "membership": {
            "badgePurchaseEur": 12.0,
            "subscriptionEurPerMonthPerBadge": 1.5,
            "discountUpToPercent": 50,
        },
        "directTariffModel": {
            "energyAndConnectionTimeComponents": True,
            "variesByStationTypeAndMaxPower": True,
            "specialTerritories": ["Hérault", "Pyrénées-Orientales", "Toulouse Métropole"],
            "exactCurrentPublicGridFullyMachineReadableFromPricingPage": False,
            "exactStationTariffLookupRequired": True,
        },
        "roaming": {
            "separateFromDirectRetail": True,
            "technicalOcpiFeedPublished": True,
            "transport": "OCPI via GIREVE",
            "operationCodes": ["FR*M31", "FR*S48", "FR*S12", "FR*S34"],
        },
    }
    fingerprint = hashlib.sha256(json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "reveo-official-france",
        "generatedAt": iso(at),
        "operator": "Révéo",
        "country": "FR",
        **relevant,
        "technicalTariffEvidence": {
            "scope": "OCPI tariffs explicitly published by Révéo on its Tarif Roaming page; not relabelled as direct retail",
            "activeTariffs": compact,
            "feedSha256": feed_sha,
        },
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": "pricing", "url": PRICING_URL, "httpStatus": p_status, "rawSha256": hashlib.sha256(p_raw).hexdigest()},
                {"key": "how", "url": HOW_URL, "httpStatus": h_status, "rawSha256": hashlib.sha256(h_raw).hexdigest()},
                {"key": "roaming", "url": ROAMING_PAGE_URL, "httpStatus": r_status, "rawSha256": hashlib.sha256(r_raw).hexdigest()},
                {"key": "ocpiTariffs", "url": OCPI_URL, "httpStatus": o_status, "rawSha256": feed_sha},
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Révéo's public pricing page confirms pricing mechanics, badge/subscription prices and special territorial grids, but does not expose the complete direct-public price table as machine-readable text.",
            "The linked OCPI/GIREVE feed is retained as technical roaming tariff evidence only; it must not overwrite direct-public pricing in Charge Companion.",
            "For an exact direct price at a specific Révéo station, the official app remains the required lookup when the web page does not expose the grid value directly.",
        ],
    }

    (OUT / "reveo_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = [
        "# Révéo official check",
        "",
        "- Public access works without subscription; QR/card ad-hoc and app public tariff are supported.",
        "- Révéo badge: 12 EUR; optional subscription: 1.50 EUR/month/badge; advertised discount up to 50%.",
        "- Direct pricing depends on station type/max power and connection duration; Hérault, Pyrénées-Orientales and Toulouse Métropole use different grids.",
        f"- Official OCPI/GIREVE feed: {len(active)} active tariffs, {len(readable)} with human-readable TTC text, operation codes {', '.join(party_ids)}.",
        "- OCPI/GIREVE tariffs are classified separately from direct retail pricing.",
        f"- Fingerprint: `{fingerprint}`",
    ]
    (OUT / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
