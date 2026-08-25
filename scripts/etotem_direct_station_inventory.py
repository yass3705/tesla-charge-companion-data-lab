#!/usr/bin/env python3
"""Build a strict France e-Totem physical-CPO station inventory from data.gouv.fr.

Scope:
- physical charging stations only (IRVE datasets published by e-Totem)
- keep a station only when the IRVE row names e-Totem as the operator
- no eMSP/roaming locations from the e-Totem mobility card
- preserve raw tariff text per station/PDC for later station-level resolution

Output: data/national/etotem_direct_stations_france.json.gz
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

API_BASE = "https://www.data.gouv.fr/api/1"
OUTPUT = Path("data/national/etotem_direct_stations_france.json.gz")
USER_AGENT = "TeslaChargeCompanionDataLab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"


def _norm(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def _get_json(url: str, retries: int = 4) -> dict:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.load(response)
        except Exception as exc:  # pragma: no cover - exercised by live workflow
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url}: {last}")


def _get_bytes(url: str, retries: int = 4) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"})
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except Exception as exc:  # pragma: no cover - exercised by live workflow
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"download failed after {retries} attempts: {url}: {last}")


def find_etotem_organization() -> dict:
    url = f"{API_BASE}/organizations/?q={urllib.parse.quote('e-Totem')}&page_size=50"
    payload = _get_json(url)
    candidates = payload.get("data", [])
    for org in candidates:
        if _norm(org.get("slug")) == "e-totem" or _norm(org.get("name")) == "e-totem":
            return org
    for org in candidates:
        if "totem" in _norm(org.get("name")):
            return org
    raise RuntimeError("Unable to resolve the e-Totem data.gouv.fr organization")


def list_etotem_irve_datasets(org_id: str) -> List[dict]:
    url = f"{API_BASE}/datasets/?organization={urllib.parse.quote(org_id)}&page_size=100"
    payload = _get_json(url)
    datasets = []
    for item in payload.get("data", []):
        title = _norm(item.get("title"))
        description = _norm(item.get("description"))
        if "recharge" in title and ("irve" in title or "vehicule" in title or "borne" in title):
            datasets.append(item)
        elif "reseau de points de charge" in description:
            datasets.append(item)
    return datasets


def choose_csv_resource(dataset: dict) -> Optional[dict]:
    resources = dataset.get("resources") or []
    csvs = [r for r in resources if _norm(r.get("format")) in {"csv", "csv.gz"}]
    if not csvs:
        return None
    mains = [r for r in csvs if _norm(r.get("type")) == "main"]
    pool = mains or csvs
    pool.sort(key=lambda r: str(r.get("last_modified") or r.get("modified") or r.get("created_at") or ""), reverse=True)
    return pool[0]


def decode_csv_bytes(content: bytes) -> str:
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            pass
    return content.decode("utf-8", errors="replace")


def read_csv_rows(content: bytes) -> List[dict]:
    text = decode_csv_bytes(content)
    sample = text[:10000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for row in reader:
        clean = {(k or "").strip().lstrip("\ufeff"): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        rows.append(clean)
    return rows


def is_etotem_operator(row: dict) -> bool:
    value = _norm(row.get("nom_operateur"))
    if not value:
        return False
    compact = re.sub(r"[^a-z0-9]", "", value)
    return "etotem" in compact


def station_id(row: dict) -> str:
    return (row.get("id_station_itinerance") or row.get("id_station_local") or "").strip()


def pdc_id(row: dict) -> str:
    return (row.get("id_pdc_itinerance") or row.get("id_pdc_local") or "").strip()


def parse_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_coordinates(value: object) -> Tuple[Optional[float], Optional[float]]:
    if not value:
        return None, None
    text = str(value).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, (list, tuple)) and len(obj) >= 2:
            lon = parse_float(obj[0])
            lat = parse_float(obj[1])
            return lat, lon
    except Exception:
        pass
    nums = re.findall(r"-?\d+(?:[\.,]\d+)?", text)
    if len(nums) >= 2:
        lon = parse_float(nums[0])
        lat = parse_float(nums[1])
        return lat, lon
    return None, None


def nonempty(value: object) -> Optional[str]:
    text = "" if value is None else str(value).strip()
    return text or None


KWH_PATTERNS = [
    re.compile(r"(?P<price>\d+(?:[\.,]\d+)?)\s*(?:€|eur)\s*(?:/|par)\s*kwh", re.I),
    re.compile(r"(?P<price>\d+(?:[\.,]\d+)?)\s*(?:€|eur)\s*kwh", re.I),
]
TIME_PATTERNS = [
    re.compile(r"(?P<price>\d+(?:[\.,]\d+)?)\s*(?:€|eur)\s*(?:/|par)\s*(?P<minutes>\d+)\s*min", re.I),
    re.compile(r"(?P<price>\d+(?:[\.,]\d+)?)\s*(?:€|eur)\s*(?:/|par)\s*h(?:eure)?", re.I),
]


def extract_tariff_hints(text: str) -> dict:
    text = (text or "").strip()
    prices = []
    for pattern in KWH_PATTERNS:
        for match in pattern.finditer(text):
            val = parse_float(match.group("price"))
            if val is not None and val not in prices:
                prices.append(val)
    duration = []
    for pattern in TIME_PATTERNS:
        for match in pattern.finditer(text):
            val = parse_float(match.group("price"))
            if val is None:
                continue
            item = {"priceEur": val, "raw": match.group(0)}
            minutes = match.groupdict().get("minutes")
            if minutes:
                item["minutes"] = int(minutes)
            elif re.search(r"h(?:eure)?", match.group(0), re.I):
                item["minutes"] = 60
            if item not in duration:
                duration.append(item)
    return {"pricePerKwhCandidatesEur": prices, "durationFeeCandidates": duration}


def _connector_types(row: dict) -> List[str]:
    mapping = [
        ("prise_type_ef", "EF"),
        ("prise_type_2", "T2"),
        ("prise_type_combo_ccs", "CCS"),
        ("prise_type_chademo", "CHAdeMO"),
        ("prise_type_autre", "OTHER"),
    ]
    out = []
    for field, label in mapping:
        val = _norm(row.get(field))
        if val in {"true", "1", "yes", "oui", "vrai"}:
            out.append(label)
    return out


def build_inventory(dataset_rows: Iterable[Tuple[dict, dict, dict]]) -> dict:
    """dataset_rows yields (dataset metadata, resource metadata, IRVE row)."""
    grouped: Dict[Tuple[str, str], List[Tuple[dict, dict, dict]]] = defaultdict(list)
    dropped_missing_station_id = 0
    for dataset, resource, row in dataset_rows:
        if not is_etotem_operator(row):
            continue
        sid = station_id(row)
        if not sid:
            dropped_missing_station_id += 1
            continue
        grouped[(str(dataset.get("id") or dataset.get("slug") or ""), sid)].append((dataset, resource, row))

    stations = []
    prefix_counter = Counter()
    dataset_counter = Counter()
    tariff_text_counter = Counter()
    total_pdcs = 0

    for (dataset_id, sid), entries in grouped.items():
        dataset, resource, first = entries[0]
        pdcs = []
        station_tariffs = []
        powers = []
        for _, _, row in entries:
            pid = pdc_id(row)
            power = parse_float(row.get("puissance_nominale"))
            if power is not None:
                powers.append(power)
            raw_tariff = nonempty(row.get("tarification"))
            if raw_tariff and raw_tariff not in station_tariffs:
                station_tariffs.append(raw_tariff)
                tariff_text_counter[raw_tariff] += 1
            pdcs.append({
                "id": pid or None,
                "powerKw": power,
                "connectors": _connector_types(row),
                "tarificationRaw": raw_tariff,
                "tariffHints": extract_tariff_hints(raw_tariff or ""),
                "paymentAtAct": nonempty(row.get("paiement_acte")),
                "paymentCard": nonempty(row.get("paiement_cb")),
                "free": nonempty(row.get("gratuit")),
                "updatedAt": nonempty(row.get("date_maj")),
            })
        total_pdcs += len(pdcs)
        lat, lon = parse_coordinates(first.get("coordonneesXY"))
        prefix = sid.split("P", 1)[0] if "P" in sid else sid[:6]
        prefix_counter[prefix] += 1
        dataset_title = str(dataset.get("title") or "")
        dataset_counter[dataset_title] += 1
        hints = {"pricePerKwhCandidatesEur": [], "durationFeeCandidates": []}
        for raw in station_tariffs:
            h = extract_tariff_hints(raw)
            for price in h["pricePerKwhCandidatesEur"]:
                if price not in hints["pricePerKwhCandidatesEur"]:
                    hints["pricePerKwhCandidatesEur"].append(price)
            for fee in h["durationFeeCandidates"]:
                if fee not in hints["durationFeeCandidates"]:
                    hints["durationFeeCandidates"].append(fee)
        stations.append({
            "stationId": sid,
            "stationIdLocal": nonempty(first.get("id_station_local")),
            "name": nonempty(first.get("nom_station")),
            "operatorName": nonempty(first.get("nom_operateur")),
            "brandName": nonempty(first.get("nom_enseigne")),
            "developerName": nonempty(first.get("nom_amenageur")),
            "address": nonempty(first.get("adresse_station")),
            "inseeCode": nonempty(first.get("code_insee_commune")),
            "latitude": lat,
            "longitude": lon,
            "hours": nonempty(first.get("horaires")),
            "accessCondition": nonempty(first.get("condition_acces")),
            "maxPowerKw": max(powers) if powers else None,
            "pdcCount": len(pdcs),
            "pdcs": pdcs,
            "tarificationRaw": station_tariffs,
            "tariffHints": hints,
            "dataset": {
                "id": dataset_id,
                "title": dataset_title,
                "resourceId": resource.get("id"),
                "resourceUrl": resource.get("url"),
            },
        })

    stations.sort(key=lambda s: (s.get("stationId") or "", s.get("name") or ""))
    with_tariff_text = sum(1 for s in stations if s["tarificationRaw"])
    with_kwh_hint = sum(1 for s in stations if s["tariffHints"]["pricePerKwhCandidatesEur"])

    return {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "operator": "e-Totem",
        "country": "FR",
        "scope": {
            "physicalCpoDirectOnly": True,
            "roamingIncluded": False,
            "filter": "IRVE rows published by e-Totem where nom_operateur identifies e-Totem",
            "tariffPolicy": "raw station/PDC tariff text preserved; no guessed national tariff",
        },
        "counts": {
            "stationCount": len(stations),
            "pdcCount": total_pdcs,
            "stationsWithTarificationText": with_tariff_text,
            "stationsWithParsedKwhCandidate": with_kwh_hint,
            "droppedMissingStationId": dropped_missing_station_id,
        },
        "stationsByPrefix": dict(prefix_counter.most_common()),
        "stationsByDataset": dict(dataset_counter.most_common()),
        "topTarificationTexts": [{"text": text, "stationRows": count} for text, count in tariff_text_counter.most_common(50)],
        "stations": stations,
    }


def main() -> int:
    org = find_etotem_organization()
    datasets = list_etotem_irve_datasets(str(org["id"]))
    if not datasets:
        raise RuntimeError("No e-Totem IRVE datasets found")

    collected = []
    source_summary = []
    for dataset in datasets:
        resource = choose_csv_resource(dataset)
        if not resource:
            source_summary.append({"dataset": dataset.get("title"), "status": "no_csv_resource"})
            continue
        content = _get_bytes(str(resource["url"]))
        rows = read_csv_rows(content)
        kept = sum(1 for row in rows if is_etotem_operator(row))
        source_summary.append({
            "dataset": dataset.get("title"),
            "datasetId": dataset.get("id"),
            "resourceId": resource.get("id"),
            "rowCount": len(rows),
            "eTotemOperatorRowCount": kept,
        })
        for row in rows:
            collected.append((dataset, resource, row))

    inventory = build_inventory(collected)
    inventory["sourceOrganization"] = {"id": org.get("id"), "name": org.get("name"), "slug": org.get("slug")}
    inventory["sourceDatasets"] = source_summary

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(inventory, handle, ensure_ascii=False, separators=(",", ":"))

    print(json.dumps(inventory["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(inventory["stationsByDataset"], ensure_ascii=False, indent=2))
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
