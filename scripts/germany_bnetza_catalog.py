#!/usr/bin/env python3
"""Build a normalized German charging baseline from the Bundesnetzagentur registry.

The BNetzA CSV is the static national baseline only. Dynamic operational status
and ad-hoc prices are intentionally left for AFIR/Mobilithek enrichment.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SOURCE_PAGE = "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/Ladesaeulenkarte/start.html"
GENERIC_CSV = "https://data.bundesnetzagentur.de/Bundesnetzagentur/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/Ladesaeulenregister_BNetzA.csv"
USER_AGENT = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"

ALIASES = {
    "station_id": ("ladeeinrichtungs id", "ladeeinrichtung id", "ladestation id", "station id"),
    "operator": ("betreiber", "betreiberin"),
    "operator_id": ("evse operator id", "operator id", "bdew code"),
    "street": ("strasse",),
    "house_number": ("hausnummer",),
    "address_extra": ("adresszusatz",),
    "postal_code": ("postleitzahl", "plz"),
    "city": ("ort", "stadt"),
    "state": ("bundesland",),
    "district": ("kreis kreisfreie stadt", "landkreis", "kreis"),
    "latitude": ("breitengrad", "latitude", "lat"),
    "longitude": ("langengrad", "longitude", "lon", "lng"),
    "commissioned": ("inbetriebnahmedatum", "inbetriebnahme"),
    "connection_power": ("anschlussleistung", "nennleistung der ladeeinrichtung"),
    "charger_type": ("art der ladeeinrichtung", "art der ladeeinrichung"),
    "charge_point_count": ("anzahl ladepunkte", "anzahl der ladepunkte"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm_header(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ß", "ss").lower()
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean(value) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def number(value):
    text = clean(value)
    if not text:
        return None
    text = text.replace("\u00a0", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def integer(value):
    x = number(value)
    return int(round(x)) if x is not None else None


def clamp_coord(value, lo, hi):
    x = number(value)
    return x if x is not None and lo <= x <= hi else None


def request(url: str, attempts: int = 4, timeout: int = 90) -> bytes:
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"unable to fetch {url}: {last}")


def discover_csv_urls(page_html: str, base_url: str = SOURCE_PAGE) -> list[str]:
    candidates = []
    for raw_href in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', page_html, flags=re.I):
        href = html.unescape(raw_href)
        absolute = urllib.parse.urljoin(base_url, href)
        low = absolute.lower()
        if "ladesaeulenregister" in low and ".csv" in low:
            candidates.append(absolute)

    def rank(url: str):
        dates = re.findall(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", url)
        date_key = max(("".join(parts) for parts in dates), default="")
        return date_key, "bnetza" in url.lower(), len(url)

    return sorted(dict.fromkeys(candidates), key=rank, reverse=True)


def decode_csv_bytes(payload: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    raise RuntimeError("unable to decode BNetzA CSV")


def detect_dialect(text: str) -> csv.Dialect:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,|\t")
    except csv.Error:
        class Semi(csv.excel):
            delimiter = ";"
        return Semi()


def find_header_row(rows: list[list[str]]) -> int:
    for idx, row in enumerate(rows[:10]):
        normalized = {norm_header(x) for x in row}
        if "betreiber" in normalized and "breitengrad" in normalized:
            return idx
    return 0


def column_map(headers: Iterable[str]) -> dict[str, str]:
    normalized = {norm_header(h): h for h in headers}
    result = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[target] = normalized[alias]
                break
        if target in result:
            continue
        for nh, original in normalized.items():
            if any(nh.startswith(alias + " ") or alias in nh for alias in aliases):
                result[target] = original
                break
    return result


def normalize_station_id(row: dict[str, str], cmap: dict[str, str], lat, lon) -> str:
    explicit = clean(row.get(cmap.get("station_id", ""), ""))
    if explicit:
        return f"bnetza:{explicit}"
    identity = "|".join([
        clean(row.get(cmap.get("operator", ""), "")).lower(),
        clean(row.get(cmap.get("street", ""), "")).lower(),
        clean(row.get(cmap.get("house_number", ""), "")).lower(),
        clean(row.get(cmap.get("postal_code", ""), "")),
        clean(row.get(cmap.get("city", ""), "")).lower(),
        "" if lat is None else f"{lat:.6f}",
        "" if lon is None else f"{lon:.6f}",
    ])
    return "bnetza:auto:" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:20]


def connector_columns(headers: Iterable[str]) -> list[dict[str, str]]:
    groups: dict[int, dict[str, str]] = {}
    for header in headers:
        nh = norm_header(header)
        digits = re.findall(r"\b([1-9]\d*)\b", nh)
        if not digits:
            match = re.search(r"(?:steckertypen|public key|evse id|leistung|p)\s*([1-9]\d*)$", nh)
            digits = [match.group(1)] if match else []
        if not digits:
            continue
        idx = int(digits[-1])
        slot = groups.setdefault(idx, {})
        if "steckertyp" in nh:
            slot["standard"] = header
        elif "evse" in nh and "id" in nh:
            slot["evse_id"] = header
        elif "public key" in nh:
            slot["public_key"] = header
        elif re.fullmatch(r"p\s*\d+", nh) or re.search(r"(^| )p( |$)", nh) or "leistung" in nh:
            slot["power"] = header
    return [dict(index=idx, **groups[idx]) for idx in sorted(groups)]


def parse_csv(payload: bytes) -> tuple[list[dict], dict]:
    text, encoding = decode_csv_bytes(payload)
    dialect = detect_dialect(text)
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        raise RuntimeError("BNetzA CSV is empty")
    header_idx = find_header_row(rows)
    headers = [clean(x) for x in rows[header_idx]]
    cmap = column_map(headers)
    required = ("operator", "latitude", "longitude")
    missing = [name for name in required if name not in cmap]
    if missing:
        raise RuntimeError(f"BNetzA CSV missing required columns: {missing}; headers={headers[:30]}")
    connector_map = connector_columns(headers)

    stations = []
    skipped_coordinates = 0
    for values in rows[header_idx + 1:]:
        if not any(clean(v) for v in values):
            continue
        if len(values) < len(headers):
            values = values + [""] * (len(headers) - len(values))
        row = dict(zip(headers, values))
        lat = clamp_coord(row.get(cmap["latitude"]), -90, 90)
        lon = clamp_coord(row.get(cmap["longitude"]), -180, 180)
        if lat is None or lon is None:
            skipped_coordinates += 1
            continue
        connectors = []
        for group in connector_map:
            standard = clean(row.get(group.get("standard", ""), ""))
            power = number(row.get(group.get("power", ""), ""))
            evse_id = clean(row.get(group.get("evse_id", ""), ""))
            public_key = clean(row.get(group.get("public_key", ""), ""))
            if not (standard or power is not None or evse_id or public_key):
                continue
            connectors.append({
                "index": group["index"],
                "standard": standard or None,
                "powerKw": power,
                "evseId": evse_id or None,
                "publicKey": public_key or None,
            })
        station = {
            "stationId": normalize_station_id(row, cmap, lat, lon),
            "source": "bnetza",
            "operator": clean(row.get(cmap["operator"], "")),
            "operatorId": clean(row.get(cmap.get("operator_id", ""), "")) or None,
            "address": {
                "street": clean(row.get(cmap.get("street", ""), "")) or None,
                "houseNumber": clean(row.get(cmap.get("house_number", ""), "")) or None,
                "extra": clean(row.get(cmap.get("address_extra", ""), "")) or None,
                "postalCode": clean(row.get(cmap.get("postal_code", ""), "")) or None,
                "city": clean(row.get(cmap.get("city", ""), "")) or None,
                "state": clean(row.get(cmap.get("state", ""), "")) or None,
                "district": clean(row.get(cmap.get("district", ""), "")) or None,
                "countryCode": "DE",
            },
            "coordinates": {"latitude": lat, "longitude": lon},
            "commissionedDate": clean(row.get(cmap.get("commissioned", ""), "")) or None,
            "connectionPowerKw": number(row.get(cmap.get("connection_power", ""), "")),
            "chargerType": clean(row.get(cmap.get("charger_type", ""), "")) or None,
            "chargePointCount": integer(row.get(cmap.get("charge_point_count", ""), "")),
            "connectors": connectors,
            "operationalStatus": "unknown",
        }
        stations.append(station)
    meta = {
        "encoding": encoding,
        "delimiter": dialect.delimiter,
        "headerRow": header_idx + 1,
        "columns": headers,
        "mappedColumns": cmap,
        "connectorGroups": connector_map,
        "skippedWithoutCoordinates": skipped_coordinates,
    }
    return stations, meta


def build(source_url: str | None, output: Path, input_file: Path | None = None) -> dict:
    fetched_at = utc_now()
    selected_url = source_url
    if input_file:
        payload = input_file.read_bytes()
        selected_url = f"file://{input_file}"
    else:
        if not selected_url:
            page = request(SOURCE_PAGE).decode("utf-8", errors="replace")
            candidates = discover_csv_urls(page)
            candidates.append(GENERIC_CSV)
            errors = []
            payload = None
            for candidate in dict.fromkeys(candidates):
                try:
                    payload = request(candidate)
                    selected_url = candidate
                    break
                except RuntimeError as exc:
                    errors.append(str(exc))
            if payload is None:
                raise RuntimeError("no BNetzA CSV could be fetched: " + "; ".join(errors))
        else:
            payload = request(selected_url)
    stations, parse_meta = parse_csv(payload)
    if len(stations) < 50000 and not input_file:
        raise RuntimeError(f"implausibly low BNetzA station-row count: {len(stations)}")
    operators = len({s["operator"] for s in stations if s["operator"]})
    charge_points = sum(s["chargePointCount"] or 0 for s in stations)
    connector_rows = sum(len(s["connectors"]) for s in stations)
    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-bnetza-static-baseline",
        "generatedAt": fetched_at,
        "countryCode": "DE",
        "source": {
            "authority": "Bundesnetzagentur",
            "url": selected_url,
            "registryPage": SOURCE_PAGE,
            "license": "CC BY 4.0",
            "attribution": "bundesnetzagentur.de",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        },
        "scope": {
            "publicChargingOnly": True,
            "dynamicStatusIncluded": False,
            "tariffsIncluded": False,
            "teslaExcluded": False,
            "note": "BNetzA is the static baseline; AFIR/Mobilithek is required for status and ad-hoc prices.",
        },
        "stats": {
            "stationRows": len(stations),
            "declaredChargePoints": charge_points,
            "connectorRows": connector_rows,
            "operators": operators,
            "skippedWithoutCoordinates": parse_meta["skippedWithoutCoordinates"],
        },
        "parse": parse_meta,
        "stations": stations,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(output, "wb", compresslevel=9) as handle:
        handle.write(encoded)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url")
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/germany/bnetza_baseline.json.gz"))
    args = parser.parse_args()
    result = build(args.source_url, args.output, args.input_file)
    print(json.dumps(result["stats"], ensure_ascii=False, indent=2))
    print(result["source"]["url"])


if __name__ == "__main__":
    main()
