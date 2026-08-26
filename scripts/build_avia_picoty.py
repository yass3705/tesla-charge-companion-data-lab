#!/usr/bin/env python3
"""Build the national AVIA VOLT / Picoty CPO dataset from French IRVE data.

The collector is deliberately conservative:
- rows are retained only when a public identifier resolves to Picoty ``FR*PY2``
  or the IRVE operator field explicitly identifies Picoty;
- a commercial AVIA/AVIA VOLT label alone never proves the CPO;
- station and EVSE granularity is preserved;
- roaming/eMSP prices are never promoted to direct-CPO prices;
- the observed 0.59 EUR/kWh market price is not emitted as a verified tariff.

Input may be a local CSV/JSON/JSONL file or an HTTP(S) URL returning one of those
formats. Output is deterministic JSON and, optionally, gzip-compressed JSON.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PICOTY_PREFIX = "FR*PY2"
PICOTY_NORMALIZED_PREFIX = "FRPY2"

ID_FIELDS = (
    "id_pdc_itinerance",
    "id_station_itinerance",
    "id_operateur",
    "code_operateur",
    "operator_id",
    "evse_id",
    "station_id",
)
OPERATOR_FIELDS = ("nom_operateur", "operateur", "operator")

DIRECT_TARIFF_MARKERS = (
    "paiement direct",
    "paiement a l acte",
    "paiement a l'acte",
    "sans badge",
    "ad hoc",
    "ad-hoc",
    "carte bancaire",
    "non abonne",
    "non-abonne",
)
ROAMING_TARIFF_MARKERS = (
    "operateur de mobilite",
    "badge",
    "chargemap",
    "ulys",
    "electroverse",
    "shell recharge",
    "freshmile",
    "kiwhi",
)


def norm_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def normalized_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def is_picoty_row(row: dict[str, Any]) -> bool:
    """Return True only for a Picoty CPO row, never from brand alone."""
    for key in ID_FIELDS:
        if norm_id(row.get(key)).startswith(PICOTY_NORMALIZED_PREFIX):
            return True
    operator_text = " ".join(str(row.get(k) or "") for k in OPERATOR_FIELDS)
    return "picoty" in normalized_text(operator_text)


def first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    s = normalized_text(value)
    if s in {"true", "1", "oui", "yes", "y"}:
        return True
    if s in {"false", "0", "non", "no", "n"}:
        return False
    return None


def parse_coordinates(row: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (latitude, longitude) from normalized fields or IRVE coordonneesXY."""
    lat = as_float(first(row, "consolidated_latitude", "latitude", "y"))
    lon = as_float(first(row, "consolidated_longitude", "longitude", "x"))
    if lat is not None and lon is not None:
        return lat, lon

    raw = first(row, "coordonneesXY", "coordonnees_xy", "coordinates")
    if raw in (None, ""):
        return None, None
    coords: Any = raw
    if isinstance(raw, str):
        try:
            coords = json.loads(raw)
        except json.JSONDecodeError:
            nums = re.findall(r"-?\d+(?:[\.,]\d+)?", raw)
            if len(nums) >= 2:
                coords = [float(nums[0].replace(",", ".")), float(nums[1].replace(",", "."))]
    if isinstance(coords, dict):
        coords = coords.get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        lon = as_float(coords[0])
        lat = as_float(coords[1])
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None, None


def load_bytes(source: str) -> bytes:
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "tcc-data-lab/avia-picoty"})
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read()
    return Path(source).read_bytes()


def load_rows(source: str) -> list[dict[str, Any]]:
    raw = load_bytes(source)
    if source.endswith(".gz"):
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8-sig")
    stripped = text.lstrip()

    if stripped.startswith("["):
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("JSON root must be an array")
        return [dict(x) for x in payload]
    if stripped.startswith("{"):
        payload = json.loads(text)
        if isinstance(payload, dict):
            for key in ("data", "records", "results", "features"):
                value = payload.get(key)
                if isinstance(value, list):
                    rows = []
                    for item in value:
                        if isinstance(item, dict) and key == "features" and isinstance(item.get("properties"), dict):
                            props = dict(item["properties"])
                            geom = item.get("geometry") or {}
                            if isinstance(geom, dict) and isinstance(geom.get("coordinates"), list):
                                props.setdefault("coordonneesXY", geom["coordinates"])
                            rows.append(props)
                        elif isinstance(item, dict):
                            rows.append(dict(item))
                    return rows
        return [dict(payload)]

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [dict(row) for row in csv.DictReader(io.StringIO(text), dialect=dialect)]


def parse_connectors(row: dict[str, Any]) -> list[str]:
    candidates = {
        "type_2": ("prise_type_2", "type_2"),
        "ccs": ("prise_type_combo_ccs", "combo_ccs", "ccs"),
        "chademo": ("prise_type_chademo", "chademo"),
        "ef": ("prise_type_ef", "ef"),
        "other": ("prise_type_autre", "autre"),
    }
    out = []
    for name, keys in candidates.items():
        if any(as_bool(row.get(k)) is True for k in keys):
            out.append(name)
    return out


def parse_direct_tariff(row: dict[str, Any]) -> dict[str, Any]:
    """Parse only an explicitly identified direct/ad-hoc EUR/kWh tariff.

    IRVE's ``tarification`` field is free text. A numeric price alone is not enough
    to prove that it is Picoty's direct CPO price, because the text can describe an
    eMSP/badge tariff. The original source text is always preserved.
    """
    raw = first(row, "tarification", "pricing", "tarif")
    result: dict[str, Any] = {
        "kind": "direct_cpo",
        "status": "unknown",
        "eur_per_kwh": None,
        "source": None,
        "source_text": raw,
        "confidence": "none",
    }
    if raw in (None, ""):
        return result

    text = str(raw)
    normalized = normalized_text(text)
    has_direct_marker = any(marker in normalized for marker in DIRECT_TARIFF_MARKERS)
    has_direct_marker = has_direct_marker or re.search(r"\bcb\b", normalized) is not None
    has_roaming_marker = any(marker in normalized for marker in ROAMING_TARIFF_MARKERS)

    # A roaming-only indication is explicitly not a direct Picoty tariff. When both
    # kinds of wording coexist, require an unambiguous single direct numeric value.
    if not has_direct_marker:
        return result

    matches = re.findall(r"(\d+[\.,]\d+)\s*(?:€|EUR)?\s*/?\s*kWh", text, flags=re.I)
    values = {round(float(m.replace(",", ".")), 6) for m in matches}
    if len(values) == 1:
        result.update(
            status="verified_from_irve_direct_text",
            eur_per_kwh=next(iter(values)),
            source="IRVE.tarification",
            confidence="medium" if not has_roaming_marker else "low",
        )
    return result


def station_key(row: dict[str, Any]) -> str:
    value = first(row, "id_station_itinerance", "station_id", "id_station_local")
    if value:
        return str(value)
    lat, lon = parse_coordinates(row)
    name = first(row, "nom_station", "station_name", "nom_enseigne", "adresse_station")
    return f"synthetic:{name}:{lat}:{lon}"


def evse_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evse_id": first(row, "id_pdc_itinerance", "evse_id", "id_pdc_local"),
        "local_evse_id": first(row, "id_pdc_local"),
        "power_kw": as_float(first(row, "puissance_nominale", "puissance_nominale_kw", "power_kw")),
        "connectors": parse_connectors(row),
        "payment": {
            "pay_as_you_go": as_bool(first(row, "paiement_acte")),
            "bank_card": as_bool(first(row, "paiement_cb")),
            "other": as_bool(first(row, "paiement_autre")),
        },
        "free": as_bool(first(row, "gratuit")),
        "reservation": as_bool(first(row, "reservation")),
        "hours": first(row, "horaires"),
        "accessibility": first(row, "accessibilite_pmr", "accessibility"),
        "observations": first(row, "observations", "observation"),
        "direct_tariff": parse_direct_tariff(row),
    }


def build(rows: Iterable[dict[str, Any]], source: str) -> dict[str, Any]:
    rows = list(rows)
    picoty_rows = [row for row in rows if is_picoty_row(row)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in picoty_rows:
        grouped[station_key(row)].append(row)

    stations = []
    for key in sorted(grouped):
        rs = grouped[key]
        r0 = rs[0]
        lat, lon = parse_coordinates(r0)
        stations.append(
            {
                "station_id": first(r0, "id_station_itinerance", "station_id", "id_station_local") or key,
                "local_station_id": first(r0, "id_station_local"),
                "name": first(r0, "nom_station", "station_name", "nom_enseigne"),
                "operator": "Picoty",
                "brand": "AVIA VOLT",
                "source_operator_name": first(r0, "nom_operateur", "operateur", "operator"),
                "source_brand_name": first(r0, "nom_enseigne", "reseau"),
                "cpo_id_prefix": PICOTY_PREFIX,
                "address": first(r0, "adresse_station", "adresse", "address"),
                "postal_code": first(r0, "code_postal", "postal_code"),
                "city": first(r0, "consolidated_commune", "commune", "ville", "city"),
                "city_code_insee": first(r0, "code_insee_commune"),
                "latitude": lat,
                "longitude": lon,
                "evses": sorted(
                    (evse_record(r) for r in rs),
                    key=lambda x: str(x.get("evse_id") or x.get("local_evse_id") or ""),
                ),
            }
        )

    tariff_counts: dict[str, int] = defaultdict(int)
    for station in stations:
        for evse in station["evses"]:
            tariff_counts[evse["direct_tariff"]["status"]] += 1

    return {
        "schema_version": 1,
        "dataset": "avia_picoty_direct_france",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "operator": {"name": "Picoty", "brand": "AVIA VOLT", "cpo_id_prefix": PICOTY_PREFIX},
        "policy": {
            "brand_alone_proves_cpo": False,
            "roaming_tariffs_as_direct": False,
            "avia_carte_deftpower_as_direct": False,
            "unverified_0_59_fallback_published": False,
        },
        "stats": {
            "input_rows": len(rows),
            "picoty_rows": len(picoty_rows),
            "stations": len(stations),
            "evses": sum(len(s["evses"]) for s in stations),
            "tariff_status_counts": dict(sorted(tariff_counts.items())),
        },
        "stations": stations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="IRVE CSV/JSON/JSONL path or URL")
    parser.add_argument("--output", default="data/avia_picoty_direct_france.json")
    parser.add_argument("--gzip", action="store_true", help="also write <output>.gz")
    args = parser.parse_args()

    rows = load_rows(args.input)
    dataset = build(rows, args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    output.write_text(payload, encoding="utf-8")
    if args.gzip:
        with gzip.open(str(output) + ".gz", "wt", encoding="utf-8", compresslevel=9) as fh:
            fh.write(payload)

    print(json.dumps(dataset["stats"], ensure_ascii=False))
    if dataset["stats"]["stations"] == 0:
        print("No Picoty/AVIA stations found", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
