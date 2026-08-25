#!/usr/bin/env python3
"""Build a strict La Borne Bleue direct-station inventory for TCC V8.

Source inventory: the official Alizé/Bouygues IRVE dataset published on data.gouv.fr.
Scope is fail-closed: only rows explicitly carrying the "La Borne Bleue" network
label are retained. Other Alizé-operated networks are never inferred as LBB.

Tariffs are taken from the official La Borne Bleue tariff grid effective
2025-04-03. Partner-network roaming is intentionally excluded.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESOURCE_URL = "https://www.data.gouv.fr/api/1/datasets/r/5f29737c-5393-46f9-8140-2509992adc7a"
DATASET_PAGE = "https://www.data.gouv.fr/datasets/64c28634468d0d94dd98405e"
TARIFF_URL = "https://labornebleue.fr/tarifs/"
DEFAULT_OUT = Path("data/national/labornebleue_direct_stations_idf.json.gz")
UA = "Mozilla/5.0 TCC-LaBorneBleue/1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(value: Any) -> str:
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def truthy(value: Any) -> bool:
    return norm(value) in {"1", "true", "vrai", "yes", "oui"}


def field(row: dict[str, str], *names: str) -> str:
    lowered = {norm(k).replace(" ", "_"): v for k, v in row.items()}
    for name in names:
        key = norm(name).replace(" ", "_")
        value = lowered.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def download() -> bytes:
    req = urllib.request.Request(
        RESOURCE_URL,
        headers={"User-Agent": UA, "Accept": "text/csv,*/*;q=0.8", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        if int(getattr(r, "status", 200)) != 200:
            raise RuntimeError(f"IRVE source HTTP {r.status}")
        return r.read()


def decode_csv(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            if "\n" in text:
                return text
        except UnicodeDecodeError:
            pass
    raise RuntimeError("unable to decode Alizé IRVE CSV")


def parse_rows(raw: bytes) -> list[dict[str, str]]:
    text = decode_csv(raw)
    sample = text[:65536]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    if not rows:
        raise RuntimeError("Alizé IRVE source is empty")
    return rows


def is_lbb(row: dict[str, str]) -> bool:
    # Strict explicit network identity only. SIPPEREC alone is not enough because
    # the source also contains other Bouygues/Alizé networks.
    values = [
        field(row, "nom_enseigne"),
        field(row, "nom_operateur"),
        field(row, "nom_amenageur"),
        field(row, "nom_station"),
        field(row, "observations"),
    ]
    return any(norm(v) in {"la borne bleue", "labornebleue"} for v in values) or any(
        "la borne bleue" in norm(v) for v in values[:3]
    )


def parse_coords(row: dict[str, str]) -> tuple[float, float]:
    raw = field(row, "coordonneesXY", "coordonnees_xy", "coordinates")
    if raw:
        try:
            value = json.loads(raw.replace("'", '"'))
            if isinstance(value, list) and len(value) >= 2:
                lon, lat = float(value[0]), float(value[1])
                if 41 <= lat <= 52 and -6 <= lon <= 10.5:
                    return lat, lon
        except Exception:
            pass
        nums = re.findall(r"-?\d+(?:[.,]\d+)?", raw)
        if len(nums) >= 2:
            a, b = [float(x.replace(",", ".")) for x in nums[:2]]
            # schema-irve-statique uses [longitude, latitude]
            lon, lat = a, b
            if 41 <= lat <= 52 and -6 <= lon <= 10.5:
                return lat, lon
    lat = field(row, "latitude", "lat")
    lon = field(row, "longitude", "lon", "lng")
    if lat and lon:
        a, b = float(lat.replace(",", ".")), float(lon.replace(",", "."))
        if 41 <= a <= 52 and -6 <= b <= 10.5:
            return a, b
    raise ValueError("missing/invalid coordinates")


def power_kw(row: dict[str, str]) -> float:
    raw = field(row, "puissance_nominale", "puissance_nominale_kw", "power")
    m = re.search(r"\d+(?:[.,]\d+)?", raw)
    return float(m.group(0).replace(",", ".")) if m else 0.0


def kind(row: dict[str, str]) -> str:
    if truthy(field(row, "prise_type_combo_ccs")) or truthy(field(row, "prise_type_chademo")):
        return "DC"
    return "AC"


def public_exact(k: str, power: float) -> dict[str, Any] | None:
    if k == "DC" and power > 50:
        return {"model": "kwh_plus_elapsed", "currency": "EUR", "pricePerKwh": 0.50,
                "afterMinutes": 30, "afterRatePerMinute": 0.20}
    if k != "AC":
        return None
    if 3.7 <= power <= 7.4:
        return {"model": "time_windows", "currency": "EUR",
                "windows": [{"start": "08:00", "end": "20:00", "ratePerMinute": 4.50 / 60},
                            {"start": "20:00", "end": "08:00", "ratePerMinute": 3.50 / 60}]}
    if power <= 22:
        return {"model": "per_minute", "currency": "EUR", "ratePerMinute": 6.50 / 60}
    return {"model": "per_minute", "currency": "EUR", "ratePerMinute": 12.00 / 60}


def subscriber_exact(k: str, power: float) -> dict[str, Any] | None:
    if k == "DC" and power > 50:
        return {"model": "kwh_plus_elapsed", "currency": "EUR", "pricePerKwh": 0.45,
                "afterMinutes": 30, "afterRatePerMinute": 0.20}
    if k != "AC":
        return None
    if 3.7 <= power <= 7.4:
        return {"model": "time_windows", "currency": "EUR",
                "windows": [{"start": "08:00", "end": "20:00", "ratePerMinute": 3.50 / 60},
                            {"start": "20:00", "end": "08:00", "ratePerMinute": 2.50 / 60, "capEur": 12.0}]}
    if power <= 22:
        return {"model": "time_windows", "currency": "EUR",
                "windows": [{"start": "08:00", "end": "20:00", "ratePerMinute": 5.50 / 60},
                            {"start": "20:00", "end": "08:00", "ratePerMinute": 5.50 / 60, "capEur": 12.0}]}
    return {"model": "per_minute", "currency": "EUR", "ratePerMinute": 11.00 / 60}


def runtime_rules(exact: dict[str, Any]) -> dict[str, Any]:
    model = exact["model"]
    if model == "kwh_plus_elapsed":
        return {"type": "rules", "labornebleueExact": exact, "rules": [{
            "scope": "allDay", "start": "00:00", "end": "24:00", "billing": "kwh",
            "currency": "EUR", "pricePerKwh": exact["pricePerKwh"], "chargePerMinute": 0,
            "connectionFee": 0, "idlePerMinute": 0,
            "afterMinutesRate": exact["afterRatePerMinute"],
            "afterMinutesThreshold": exact["afterMinutes"],
            "afterMinutesCap": 0, "afterMinutesCapStart": "00:00", "afterMinutesCapEnd": "24:00",
        }]}
    windows = exact.get("windows") or [{"start": "00:00", "end": "24:00", "ratePerMinute": exact["ratePerMinute"]}]
    return {"type": "rules", "labornebleueExact": exact, "rules": [{
        "scope": "timeWindow" if len(windows) > 1 else "allDay",
        "start": w["start"], "end": w["end"], "billing": "minute", "currency": "EUR",
        "pricePerKwh": 0, "chargePerMinute": w["ratePerMinute"], "connectionFee": 0,
        "idlePerMinute": 0, "afterMinutesRate": 0, "afterMinutesThreshold": 0,
        "afterMinutesCap": 0, "afterMinutesCapStart": "00:00", "afterMinutesCapEnd": "24:00",
    } for w in windows]}


def build(rows: list[dict[str, str]]) -> dict[str, Any]:
    selected = [r for r in rows if is_lbb(r)]
    if not selected:
        # Keep diagnostics useful in Actions logs without broadening the published scope.
        enseignes = Counter(field(r, "nom_enseigne") for r in rows if field(r, "nom_enseigne"))
        operators = Counter(field(r, "nom_operateur") for r in rows if field(r, "nom_operateur"))
        raise RuntimeError(f"no explicit La Borne Bleue rows; top enseignes={enseignes.most_common(20)}; "
                           f"top operators={operators.most_common(20)}")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        sid = field(row, "id_station_itinerance", "id_station_local")
        if not sid:
            raise RuntimeError("La Borne Bleue row without station identifier")
        grouped[sid].append(row)

    stations = []
    excluded_unpriced = 0
    evse_total = 0
    configuration_total = 0
    for sid, source_rows in sorted(grouped.items()):
        first = source_rows[0]
        try:
            lat, lon = parse_coords(first)
        except ValueError as exc:
            raise RuntimeError(f"{sid}: {exc}") from exc
        config_groups: dict[tuple[str, float], list[dict[str, str]]] = defaultdict(list)
        for row in source_rows:
            p = power_kw(row)
            k = kind(row)
            if not (p > 0):
                continue
            pub, sub = public_exact(k, p), subscriber_exact(k, p)
            if pub is None or sub is None:
                # DC <= 50 kW is not explicitly priced by the current official grid.
                excluded_unpriced += 1
                continue
            config_groups[(k, p)].append(row)

        configs = []
        for idx, ((k, p), rows2) in enumerate(sorted(config_groups.items())):
            evses = sorted({field(r, "id_pdc_itinerance", "id_pdc_local") for r in rows2 if field(r, "id_pdc_itinerance", "id_pdc_local")})
            stalls = len(evses) or len(rows2)
            evse_total += stalls
            for plan, exact, provider, subscription in (
                ("public", public_exact(k, p), "La Borne Bleue direct", None),
                ("subscriber", subscriber_exact(k, p), "La Borne Bleue direct — Abonné", "labornebleue-annual"),
            ):
                assert exact is not None
                configs.append({
                    "id": f"labornebleue-{sid}-{idx}-{plan}",
                    "label": f"{provider} · {k} {p:g} kW",
                    "kind": k, "powerKw": p, "stalls": stalls,
                    "pricing": runtime_rules(exact),
                    "offerProvider": provider, "offerType": "operator_direct",
                    "subscriptionId": subscription,
                    "labornebleueDirect": True, "labornebleueVerified": True,
                    "labornebleueOwnNetworkOnly": True,
                    "labornebleueEvseIds": evses,
                })
                configuration_total += 1
        if not configs:
            continue
        station_evses = {field(r, "id_pdc_itinerance", "id_pdc_local") for r in source_rows if field(r, "id_pdc_itinerance", "id_pdc_local")}
        stations.append({
            "stationId": sid,
            "name": field(first, "nom_station") or "Station La Borne Bleue",
            "address": field(first, "adresse_station"),
            "latitude": lat, "longitude": lon, "countryCode": "FR",
            "chargePointCount": len(station_evses) or len(source_rows),
            "configurations": configs,
            "sourceNetworkLabel": field(first, "nom_enseigne"),
            "sourceOperatorLabel": field(first, "nom_operateur"),
            "lastUpdated": max((field(r, "date_maj") for r in source_rows), default=""),
        })

    source_pdc = sum(len(v) for v in grouped.values())
    if source_pdc < 800 or source_pdc > 2500:
        raise RuntimeError(f"strict La Borne Bleue source point count outside guardrail: {source_pdc}")
    if len(stations) < 200 or len(stations) > 1500:
        raise RuntimeError(f"strict La Borne Bleue priced station count outside guardrail: {len(stations)}")

    return {
        "schemaVersion": "1.0.0",
        "dataset": "labornebleue-direct-tcc-v8-idf",
        "generatedAt": now_iso(),
        "source": {"datasetPage": DATASET_PAGE, "resourceUrl": RESOURCE_URL, "officialTariffUrl": TARIFF_URL},
        "scope": {
            "countryCode": "FR", "region": "Ile-de-France",
            "onlyDirectCpo": True, "strictExplicitNetworkLabel": True,
            "partnerLocationsIncluded": False, "partnerTariffsIncluded": False,
            "subscriptionDiscountAtPartnerOperators": False,
            "subscriptionAnnualFeeEur": 10.0,
            "tariffEffectiveFrom": "2025-04-03",
            "dcTariffRule": "strictly_above_50_kw",
        },
        "counts": {
            "sourceRows": len(rows), "strictSourceStations": len(grouped),
            "strictSourceChargePoints": source_pdc, "publishedStations": len(stations),
            "publishedConfigurations": configuration_total, "publishedEvseSlots": evse_total,
            "unpricedDcAtOrBelow50Excluded": excluded_unpriced,
        },
        "stations": stations,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--input", help="optional local CSV fixture")
    args = ap.parse_args()
    raw = Path(args.input).read_bytes() if args.input else download()
    payload = build(parse_rows(raw))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if out.suffix == ".gz":
        with out.open("wb") as raw_out:
            with gzip.GzipFile(fileobj=raw_out, mode="wb", compresslevel=9, mtime=0) as f:
                f.write(data)
    else:
        out.write_bytes(data + b"\n")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
