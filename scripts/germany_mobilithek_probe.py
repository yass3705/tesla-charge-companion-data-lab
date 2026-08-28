#!/usr/bin/env python3
"""Probe public Mobilithek metadata for German AFIR charging offers.

This is a discovery/QA step only. It does not yet consume the live DATEX II
payload. The output records offer metadata, related URLs, license hints and
related publication IDs so that the production feed registry can be built from
Mobilithek itself rather than from a hand-maintained CPO list.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{offer_id}"
USER_AGENT = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"

SEEDS = {
    "eco-movement-static": "954064102947180544",
    "enbw-static": "907574882292453376",
    "enbw-dynamic": "907575401287241728",
    "chargecloud-static": "978597062404620288",
    "eround-static": "961625658278940672",
    "monta-static": "963836072152719360",
    "monta-dynamic": "963870983660167168",
    "qwello-static": "972963216296222720",
    "edri-static": "972837891969273856",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            payload = response.read()
            status = getattr(response, "status", 200)
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network error for {url}: {exc}") from exc
    try:
        data = json.loads(payload.decode("utf-8-sig"))
    except Exception as exc:
        preview = payload[:500].decode("utf-8", errors="replace")
        raise RuntimeError(f"non-JSON metadata ({status}, {content_type}): {preview!r}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected metadata type {type(data).__name__} for {url}")
    return data


def walk_strings(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk_strings(child, f"{path}[{idx}]")
    elif isinstance(value, str):
        yield path, value


def summarize(offer_id: str, payload: dict) -> dict:
    strings = list(walk_strings(payload))
    urls = []
    ids = []
    license_hints = []
    afir_text = []
    for path, text in strings:
        low = text.lower()
        if text.startswith(("http://", "https://")):
            urls.append({"path": path, "url": text})
        if re.fullmatch(r"\d{15,20}", text) and text != offer_id:
            ids.append({"path": path, "id": text})
        if any(token in low for token in ("license", "lizenz", "creative commons", "cc0", "cc by")):
            license_hints.append({"path": path, "value": text})
        if "afir" in low or "recharging" in low or "lade" in low:
            afir_text.append({"path": path, "value": text[:500]})
    return {
        "offerId": offer_id,
        "metadataApi": API.format(offer_id=offer_id),
        "urls": urls,
        "relatedNumericIds": ids,
        "licenseHints": license_hints,
        "afirText": afir_text,
        "topLevelKeys": sorted(payload.keys()),
        "raw": payload,
    }


def build(output: Path, seeds: dict[str, str] | None = None) -> dict:
    seeds = seeds or SEEDS
    offers = {}
    errors = {}
    for label, offer_id in seeds.items():
        try:
            offers[label] = summarize(offer_id, fetch_json(API.format(offer_id=offer_id)))
        except Exception as exc:
            errors[label] = str(exc)
    result = {
        "schemaVersion": 1,
        "dataset": "germany-mobilithek-afir-metadata-probe",
        "generatedAt": utc_now(),
        "countryCode": "DE",
        "source": "Mobilithek public metadata API",
        "seedCount": len(seeds),
        "successCount": len(offers),
        "errorCount": len(errors),
        "offers": offers,
        "errors": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/germany/mobilithek_metadata_probe.json"))
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps({
        "seedCount": result["seedCount"],
        "successCount": result["successCount"],
        "errorCount": result["errorCount"],
        "errors": result["errors"],
    }, ensure_ascii=False, indent=2))
    if result["successCount"] < 5:
        raise SystemExit("too few Mobilithek metadata offers were readable")


if __name__ == "__main__":
    main()
