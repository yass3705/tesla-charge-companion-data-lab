#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def text(v):
    return "" if v is None else str(v).strip()


def norm_id(v):
    return re.sub(r"[^A-Z0-9]", "", text(v).upper())


def first(row, *names):
    for n in names:
        if n in row and text(row.get(n)):
            return text(row.get(n))
    return ""


def truthy(v):
    s = text(v).lower()
    if not s:
        return None
    if s in {"true", "1", "oui", "yes", "vrai"}:
        return True
    if s in {"false", "0", "non", "no", "faux"}:
        return False
    return s


def to_float(v):
    s = text(v).replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group(0)) if m else None


def pick_delimiter(path):
    sample = Path(path).read_bytes()[:131072].decode("utf-8-sig", errors="replace")
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        # PAN IRVE Etalab exports are normally comma-separated, but keep a robust fallback.
        return "," if sample.count(",") >= sample.count(";") else ";"


def is_picoty(row):
    candidates = [
        first(row, "id_station_itinerance", "id_station"),
        first(row, "id_pdc_itinerance", "id_pdc"),
    ]
    return any(norm_id(v).startswith("FRPY2") for v in candidates if v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_csv")
    ap.add_argument("output_json")
    ap.add_argument("--source-url", default="")
    args = ap.parse_args()

    delimiter = pick_delimiter(args.input_csv)
    pdc_rows = []
    all_columns = []

    with open(args.input_csv, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        all_columns = list(reader.fieldnames or [])
        for raw in reader:
            row = {text(k): text(v) for k, v in raw.items() if k is not None}
            if not is_picoty(row):
                continue

            station_id = first(row, "id_station_itinerance", "id_station")
            pdc_id = first(row, "id_pdc_itinerance", "id_pdc")
            tariff = first(row, "tarification", "tarif", "tarification_acte")
            power = to_float(first(row, "puissance_nominale", "puissance_nominale_kw"))
            entry = {
                "stationId": station_id,
                "pdcId": pdc_id,
                "operator": first(row, "nom_operateur", "operateur"),
                "brand": first(row, "nom_enseigne", "enseigne"),
                "stationName": first(row, "nom_station"),
                "address": first(row, "adresse_station", "adresse"),
                "cityCode": first(row, "code_insee_commune"),
                "coordinatesRaw": first(row, "coordonneesXY", "coordonnees_xy"),
                "powerKw": power,
                "tarificationRaw": tariff,
                "free": truthy(first(row, "gratuit")),
                "payAsYouGo": truthy(first(row, "paiement_acte")),
                "bankCard": truthy(first(row, "paiement_cb")),
                "otherPayment": first(row, "paiement_autre"),
                "hours": first(row, "horaires"),
                "observations": first(row, "observations"),
                "updatedAt": first(row, "date_maj", "date_mise_a_jour"),
                "connectorT2": truthy(first(row, "prise_type_2")),
                "connectorComboCCS": truthy(first(row, "prise_type_combo_ccs")),
                "connectorChademo": truthy(first(row, "prise_type_chademo")),
                "connectorEF": truthy(first(row, "prise_type_ef")),
            }
            # Preserve the complete matching PAN row for auditability; no authentication data exists in PAN.
            entry["panRaw"] = row
            pdc_rows.append(entry)

    stations = defaultdict(lambda: {
        "stationId": "",
        "operator": "",
        "brand": "",
        "stationName": "",
        "address": "",
        "cityCode": "",
        "coordinatesRaw": "",
        "rawTarifications": [],
        "powerKw": [],
        "pdcIds": [],
        "evses": [],
    })

    for e in pdc_rows:
        sid = e["stationId"] or (e["pdcId"].rsplit("*", 1)[0] if "*" in e["pdcId"] else e["pdcId"])
        s = stations[sid]
        s["stationId"] = sid
        for key in ["operator", "brand", "stationName", "address", "cityCode", "coordinatesRaw"]:
            if not s[key] and e.get(key):
                s[key] = e[key]
        if e["pdcId"] and e["pdcId"] not in s["pdcIds"]:
            s["pdcIds"].append(e["pdcId"])
        if e["powerKw"] is not None and e["powerKw"] not in s["powerKw"]:
            s["powerKw"].append(e["powerKw"])
        if e["tarificationRaw"] and e["tarificationRaw"] not in s["rawTarifications"]:
            s["rawTarifications"].append(e["tarificationRaw"])
        s["evses"].append(e)

    station_list = list(stations.values())
    for s in station_list:
        s["powerKw"].sort()
        s["pdcIds"].sort()
        s["rawTarifications"].sort()
        s["evses"].sort(key=lambda x: (x.get("pdcId") or "", x.get("powerKw") or 0))
    station_list.sort(key=lambda x: x["stationId"])

    tariff_counter = Counter(e["tarificationRaw"] for e in pdc_rows if e["tarificationRaw"])
    empty_tariff_count = sum(1 for e in pdc_rows if not e["tarificationRaw"])
    unique_station_tariffs = Counter()
    for s in station_list:
        for t in s["rawTarifications"]:
            unique_station_tariffs[t] += 1

    out = {
        "schemaVersion": "1.0.0",
        "dataset": "avia-volt-picoty-pan-irve-extract",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "url": args.source_url,
            "format": "PAN IRVE Etalab consolidated static CSV",
            "delimiterDetected": delimiter,
            "columns": all_columns,
        },
        "scope": {
            "country": "FR",
            "operatorPrefixNormalized": "FRPY2",
            "physicalCpoDirectInventory": True,
            "roamingTariffsIncluded": False,
            "note": "Filter is identifier-based (FR*PY2 station/PDC IDs); tarificationRaw is preserved exactly as published in PAN and must be interpreted before ranking in TCC.",
        },
        "counts": {
            "panRowsMatched": len(pdc_rows),
            "stationCount": len(station_list),
            "pdcWithTarificationRaw": len(pdc_rows) - empty_tariff_count,
            "pdcWithoutTarificationRaw": empty_tariff_count,
            "stationsWithTarificationRaw": sum(1 for s in station_list if s["rawTarifications"]),
            "stationsWithoutTarificationRaw": sum(1 for s in station_list if not s["rawTarifications"]),
        },
        "tarificationSummary": {
            "pdcRawValues": [{"value": k, "pdcCount": v} for k, v in tariff_counter.most_common()],
            "stationRawValues": [{"value": k, "stationCount": v} for k, v in unique_station_tariffs.most_common()],
        },
        "stations": station_list,
    }

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(out["tarificationSummary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
