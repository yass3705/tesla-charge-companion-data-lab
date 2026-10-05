#!/usr/bin/env python3
"""Build the compact TCC France static IRVE bundle from the current national CSV."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://proxy.transport.data.gouv.fr/resource/consolidation-transport-irve-statique"
TILE_DEGREES = 0.5
YES = {"1", "true", "t", "yes", "oui", "vrai", "x"}


def key(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", value)


def get(row, *names):
    for name in names:
        value = row.get(key(name))
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def number(value):
    if value is None:
        return None
    raw = re.sub(r"[^0-9,.-]", "", str(value).replace("\u00a0", ""))
    if not raw:
        return None
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    try:
        result = float(raw)
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def enabled(value):
    return str(value or "").strip().lower() in YES


def coordinates(row):
    lat = number(get(row, "latitude"))
    lon = number(get(row, "longitude"))
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
        return round(lat, 6), round(lon, 6)
    raw = get(row, "coordonneesXY", "coordonnees", "coordinates")
    if not raw:
        return None
    # Support GeoJSON-like objects, POINT(lon lat), and comma/semicolon separated pairs.
    low = raw.lower()
    mlat = re.search(r'"lat(?:itude)?"\s*:\s*(-?\d+(?:[.,]\d+)?)', low)
    mlon = re.search(r'"(?:lon|lng|longitude)"\s*:\s*(-?\d+(?:[.,]\d+)?)', low)
    if mlat and mlon:
        a, b = number(mlat.group(1)), number(mlon.group(1))
        if a is not None and b is not None:
            return round(a, 6), round(b, 6)
    nums = [number(x) for x in re.findall(r"-?\d+(?:[.,]\d+)?", raw)]
    nums = [x for x in nums if x is not None]
    if len(nums) < 2:
        return None
    a, b = nums[0], nums[1]
    # Metropolitan France and overseas France conventions; prefer the plausible lat/lon order.
    if -90 <= b <= 90 and -180 <= a <= 180 and (abs(a) > 20 or abs(b) > 20):
        lat, lon = b, a
    elif -90 <= a <= 90 and -180 <= b <= 180:
        lat, lon = a, b
    else:
        return None
    return round(lat, 6), round(lon, 6)


def power_label(value):
    return str(int(value)) if float(value).is_integer() else str(value).rstrip("0").rstrip(".")


def hours_value(raw):
    text = str(raw or "").strip().lower()
    if not text:
        return 0
    if any(token in text for token in ("24/7", "24h/24", "24 h/24", "24/24")):
        return [[day, "00:00", "24:00"] for day in range(7)]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return 0


def stable_gzip(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with path.open("wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    return len(raw), path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()


def tile_part(value):
    return str(value) if value >= 0 else "m" + str(abs(value))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--source-sha256", required=True)
    ap.add_argument("--source-bytes", required=True, type=int)
    ap.add_argument("--source-last-modified", default="")
    ap.add_argument("--source-retrieved-at", required=True)
    args = ap.parse_args()
    out = Path(args.out_dir)
    tiles_dir = out / "tiles"
    out.mkdir(parents=True, exist_ok=True)
    stations = {}
    source_rows = 0
    with open(args.input, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        sample = fh.read(65536)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        if not reader.fieldnames:
            raise SystemExit("Static CSV has no header")
        normalized_headers = {key(name) for name in reader.fieldnames}
        if "idpd c itinerance".replace(" ", "") not in normalized_headers and "idpdcitinerance" not in normalized_headers:
            raise SystemExit(f"Static CSV does not contain id_pdc_itinerance; headers={reader.fieldnames[:20]}")
        for row in reader:
            source_rows += 1
            evse = get(row, "id_pdc_itinerance")
            if not evse:
                continue
            station_id = get(row, "id_station_itinerance", "id_station_local") or evse
            pos = coordinates(row)
            if pos is None:
                continue
            station = stations.setdefault(station_id, {
                "id": station_id, "name": "", "address": "", "lat": pos[0], "lon": pos[1],
                "operator": "", "amenageur": "", "hours": 0, "date": "", "declaredCount": 0,
                "evses": set(), "groups": {}
            })
            station["evses"].add(evse)
            station["name"] = station["name"] or get(row, "nom_station", "nom_enseigne") or station_id
            address = get(row, "adresse_station", "adresse")
            postal = get(row, "code_postal", "code_postal_station")
            city = get(row, "nom_commune", "commune")
            insee = get(row, "code_insee_commune", "code_insee")
            station["address"] = station["address"] or ", ".join(x for x in (address, " ".join(x for x in (postal, city) if x), insee) if x)
            station["operator"] = station["operator"] or get(row, "nom_operateur", "operateur", "nom_amenageur") or "AUTRE"
            station["amenageur"] = station["amenageur"] or get(row, "nom_amenageur", "nom_enseigne")
            station["hours"] = station["hours"] or hours_value(get(row, "horaires", "horaires_station"))
            station["date"] = max(station["date"], get(row, "date_maj", "date_mise_a_jour")[:10])
            count = number(get(row, "nbre_pdc", "nombre_pdc"))
            if count is not None:
                station["declaredCount"] = max(station["declaredCount"], int(count))
            kw = number(get(row, "puissance_nominale", "puissance"))
            if kw is None:
                kw = 0.0
            elif kw > 1000:
                kw /= 1000.0
            kw = round(kw, 1)
            plug_types = []
            for col, label in (
                ("prise_type_ef", "EF"), ("prise_type_2", "Type 2"),
                ("prise_type_combo_ccs", "CCS"), ("prise_type_chademo", "CHAdeMO")
            ):
                if enabled(get(row, col)):
                    plug_types.append(label)
            other = get(row, "prise_type_autre")
            if other and other.lower() not in {"false", "0", "non", "no"}:
                plug_types.append(other)
            if not plug_types:
                plug_types = ["INCONNU"]
            for plug in plug_types:
                kind = "DC" if any(token in plug.lower() for token in ("ccs", "combo", "chademo")) or (plug == "INCONNU" and kw > 43) else "AC"
                group_key = (kind, kw, plug)
                group = station["groups"].setdefault(group_key, set())
                group.add(evse)
    valid_stations = []
    all_evse = set()
    tiled = defaultdict(list)
    for station in stations.values():
        if not station["evses"]:
            continue
        all_evse.update(station["evses"])
        groups = []
        for ordinal, (gkey, ids) in enumerate(sorted(station["groups"].items(), key=lambda item: (item[0][0], item[0][1], item[0][2]))):
            kind, kw, plug = gkey
            kw_text = power_label(kw)
            suffix = kw_text.replace(".", "_")
            label = f"IRVE · {kind} {kw_text} kW" if plug == "INCONNU" else f"IRVE · {plug} {kw_text} kW"
            groups.append([f"irve-{ordinal}-{kind.lower()}-{suffix}", label, kind, kw, len(ids), [], sorted(ids)])
        pdc_count = max(len(station["evses"]), station["declaredCount"])
        row = [station["id"], station["name"], station["address"], station["lat"], station["lon"],
               station["operator"].upper(), pdc_count, station["hours"] or 0, groups,
               station["date"], station["amenageur"] or station["operator"]]
        valid_stations.append(row)
    valid_stations.sort(key=lambda row: str(row[0]))
    for row in valid_stations:
        lat_ix = math.floor(row[3] / TILE_DEGREES)
        lon_ix = math.floor(row[4] / TILE_DEGREES)
        tile_id = f"t_{tile_part(lat_ix)}_{tile_part(lon_ix)}"
        tiled[tile_id].append(row)
    if source_rows < 120000 or len(valid_stations) < 35000 or len(all_evse) < 120000:
        raise SystemExit(f"Refusing suspiciously small static build: rows={source_rows}, stations={len(valid_stations)}, pdc={len(all_evse)}")
    _, all_bytes, all_sha = stable_gzip(out / "all.json.gz", valid_stations)
    tile_meta = []
    for tile_id, rows in sorted(tiled.items()):
        _, size, sha = stable_gzip(tiles_dir / f"{tile_id}.json.gz", rows)
        latpart, lonpart = tile_id.split("_")[1:]
        def index(part):
            return int(part[1:]) * -1 if part.startswith("m") else int(part)
        lat_ix, lon_ix = index(latpart), index(lonpart)
        tile_meta.append({
            "id": tile_id, "file": f"tiles/{tile_id}.json.gz",
            "minLat": lat_ix * TILE_DEGREES, "maxLat": (lat_ix + 1) * TILE_DEGREES,
            "minLon": lon_ix * TILE_DEGREES, "maxLon": (lon_ix + 1) * TILE_DEGREES,
            "count": len(rows), "bytes": size, "sha256": sha
        })
    manifest = {
        "schemaVersion": 2, "dataset": "france-irve-static-v9",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceUrl": SOURCE_URL,
        "sourceRetrievedAt": args.source_retrieved_at,
        "sourceLastModified": args.source_last_modified or None,
        "sourceSha256": args.source_sha256,
        "sourceBytes": args.source_bytes,
        "sourceRows": source_rows, "stationCount": len(valid_stations),
        "pdcCount": len(all_evse), "skippedRows": source_rows - len(all_evse),
        "tileSizeDegrees": TILE_DEGREES, "tileCount": len(tile_meta),
        "allFile": "all.json.gz", "allBytes": all_bytes, "allSha256": all_sha,
        "tiles": tile_meta
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("sourceRows", "stationCount", "pdcCount", "skippedRows", "tileCount", "sourceSha256", "allSha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
