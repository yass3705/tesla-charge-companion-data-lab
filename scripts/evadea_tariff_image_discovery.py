#!/usr/bin/env python3
"""Discover current e-Vadea tariff facts from the official image-only tariff page.

The official e-Vadea tariff table is published as an image. This discovery step is
intentionally separate from the final tariff extractor: OCR is used only because
no textual tariff equivalent is exposed on the official page. The report keeps
only tariff-relevant OCR lines and source fingerprints.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import subprocess
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
SOURCES = {
    "tariffs": "https://www.e-vadea.fr/fr/tarifs",
    "faq": "https://www.e-vadea.fr/fr/faq",
    "howTo": "https://www.e-vadea.fr/fr/comment-ca-marche",
    "map": "https://www.e-vadea.fr/fr/carte-des-bornes",
    "dataset": "https://www.data.gouv.fr/datasets/e-vadea-stations-de-recharge-pour-les-vehicules-electriques",
    "inventoryCsv": "https://www.data.gouv.fr/api/1/datasets/r/29f5db7c-5148-4353-a78c-25085a119394",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,image/png,text/csv,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=50) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw, charset


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def text_from_html(raw: bytes, charset: str) -> str:
    s = raw.decode(charset, errors="replace")
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def find_tariff_image(html_raw: str, base_url: str) -> str:
    patterns = [
        r'<img[^>]+(?:alt|title)=["\'][^"\']*Tarification tableau[^"\']*["\'][^>]+src=["\']([^"\']+)',
        r'<img[^>]+src=["\']([^"\']+)["\'][^>]+(?:alt|title)=["\'][^"\']*Tarification tableau[^"\']*["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html_raw, flags=re.I | re.S)
        if m:
            return urllib.parse.urljoin(base_url, html.unescape(m.group(1)))
    m = re.search(r'(["\'])(/storage/text_images/[^"\']+\.(?:png|jpg|jpeg|webp))\1', html_raw, flags=re.I)
    if m:
        return urllib.parse.urljoin(base_url, html.unescape(m.group(2)))
    raise RuntimeError("e-Vadea official tariff image URL not found in tariff page")


def tariff_lines(ocr: str) -> list[str]:
    keep = []
    for raw in ocr.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        n = norm(line)
        if any(tok in n for tok in ("€", "eur", "kwh", "kw", "min", "heure", "forfait", "post", "tarif")) or re.search(r"\b0[,.]\d{2,3}\b", n):
            keep.append(line[:300])
    out = []
    seen = set()
    for line in keep:
        key = norm(line)
        if key not in seen:
            seen.add(key)
            out.append(line)
    return out[:80]


def numeric_candidates(lines: list[str]) -> list[float]:
    vals = set()
    for line in lines:
        for m in re.finditer(r"(?<!\d)(\d{1,3}[,.]\d{1,3})(?!\d)", line):
            try:
                v = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            if 0.01 <= v <= 100.0:
                vals.add(v)
    return sorted(vals)


def inventory_summary(raw: bytes) -> dict:
    text = raw.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t")
        rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    except csv.Error:
        rows = list(csv.DictReader(io.StringIO(text), delimiter=";") )
    samples = []
    for row in rows[:1000]:
        lower = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k is not None}
        name = lower.get("nom_station") or lower.get("n_station") or lower.get("nom_enseigne")
        address = lower.get("adresse_station") or lower.get("adresse")
        evse = lower.get("id_pdc_itinerance") or lower.get("id_pdc_local")
        power = lower.get("puissance_nominale") or lower.get("puissance_nominale_kw")
        if name or address or evse:
            samples.append({"stationName": name, "address": address, "evseId": evse, "powerObservedRaw": power})
        if len(samples) >= 3:
            break
    return {
        "rowCount": len(rows),
        "publisherLastUpdateKnown": "2024-02-09",
        "freshnessStatus": "stale_official_static_inventory_not_live_availability",
        "samples": samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/evadea")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    status, tariff_raw, charset = fetch(SOURCES["tariffs"])
    if status != 200:
        raise RuntimeError(f"tariffs page HTTP {status}")
    tariff_html = tariff_raw.decode(charset, errors="replace")
    if "Tarification tableau" not in tariff_html and "tarification tableau" not in tariff_html.lower():
        raise RuntimeError("official tariff-table image marker missing")
    image_url = find_tariff_image(tariff_html, SOURCES["tariffs"])
    img_status, image_bytes, _ = fetch(image_url)
    if img_status != 200 or len(image_bytes) < 1000:
        raise RuntimeError(f"official tariff image fetch failed HTTP {img_status}, bytes={len(image_bytes)}")
    image_path = out / "tariff_table.png"
    image_path.write_bytes(image_bytes)

    try:
        proc = subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", "fra+eng", "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("tesseract executable missing") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract failed: {proc.stderr[-500:]}")
    ocr = proc.stdout
    lines = tariff_lines(ocr)
    if not lines:
        raise RuntimeError("OCR produced no tariff-relevant lines")

    faq_status, faq_raw, faq_charset = fetch(SOURCES["faq"])
    how_status, how_raw, how_charset = fetch(SOURCES["howTo"])
    csv_status, csv_raw, _ = fetch(SOURCES["inventoryCsv"])
    if faq_status != 200 or how_status != 200 or csv_status != 200:
        raise RuntimeError("one or more official supporting sources failed")
    faq = norm(text_from_html(faq_raw, faq_charset))
    how = norm(text_from_html(how_raw, how_charset))

    # These supporting pages are partly rendered differently between crawler/browser
    # and the raw GitHub-runner response. Record what the runner can prove, but do
    # not block the image-discovery workflow on secondary HTML evidence.
    preauth_evidence = bool(
        "pre-autorisation" in faq
        and re.search(r"\b49(?:[,.]00)?(?:\s*€|\s*eur)?\b", faq)
    )
    post_charge_evidence = "forfait post-charge" in faq or "forfait post charge" in faq
    tolerance_evidence = bool(re.search(r"tolerance\s+de\s+5\s*(?:mn|min|minutes?)\b", faq))
    roaming_evidence = "tarif different" in how and "operateur de mobilite" in how
    guest_evidence = "invite" in faq or "invité" in faq
    live_evidence = "disponibilite en temps reel" in how

    report = {
        "schemaVersion": "1.1.0",
        "dataset": "evadea-official-tariff-image-discovery",
        "generatedAt": now_iso(),
        "operator": "e-Vadea",
        "country": "FR",
        "status": "discovery_not_yet_validated_tariff_model",
        "tariffImage": {
            "url": image_url,
            "sha256": hashlib.sha256(image_bytes).hexdigest(),
            "bytes": len(image_bytes),
            "ocrEngine": "tesseract fra+eng psm6",
            "tariffRelevantLines": lines,
            "numericCandidates": numeric_candidates(lines),
        },
        "supportingHtmlEvidence": {
            "bankCardPreauthorization49EurObservedInRawFaq": preauth_evidence,
            "postChargeFeeObservedInRawFaq": post_charge_evidence,
            "postChargeTolerance5MinutesObservedInRawFaq": tolerance_evidence,
            "thirdPartyMobilityTariffMayDifferObservedInRawHowTo": roaming_evidence,
            "guestModeObservedInRawFaq": guest_evidence,
            "liveAvailabilityObservedInRawHowTo": live_evidence,
        },
        "validatedNonImageRules": {
            "bankCardPreauthorizationEur": 49.0 if preauth_evidence else None,
            "postChargeFeeExists": True if post_charge_evidence else None,
            "postChargeToleranceMinutes": 5 if tolerance_evidence else None,
            "thirdPartyMobilityBadgeTariffMayDiffer": True if roaming_evidence else None,
            "appGuestModeAvailable": True if guest_evidence else None,
            "liveAvailabilityViaSmartphone": True if live_evidence else None,
        },
        "inventory": inventory_summary(csv_raw),
        "sources": [{"key": k, "url": v} for k, v in SOURCES.items()],
        "notes": [
            "Tariff amounts remain discovery candidates until the OCR table structure is reviewed.",
            "Secondary FAQ/how-to facts are nullable when the raw GitHub-runner HTML does not expose browser-rendered text.",
            "No older third-party price is promoted to current official pricing.",
            "The e-Vadea publisher inventory is stale and must not be used as live availability.",
        ],
    }
    (out / "discovery.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "imageUrl": image_url,
        "imageSha256": report["tariffImage"]["sha256"],
        "numericCandidates": report["tariffImage"]["numericCandidates"],
        "tariffRelevantLines": lines,
        "supportingHtmlEvidence": report["supportingHtmlEvidence"],
        "inventoryRows": report["inventory"]["rowCount"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
