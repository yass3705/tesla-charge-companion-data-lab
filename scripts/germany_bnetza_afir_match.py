#!/usr/bin/env python3
"""QA-only matcher between the German BNetzA baseline and normalized AFIR feeds.

Pipeline:
1. Fetch/normalize the live BNetzA national registry.
2. Regroup BNetzA installation rows into conservative physical sites.
3. Fetch/normalize the currently anonymous Mobilithek AFIR feeds.
4. Match physical sites by exact EVSE ID first, then strict address/operator,
   then strict geographic/operator fallback.

This script does not publish to TCC and does not make AFIR tariffs rankable.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

try:
    import germany_bnetza_live as bnetza_live  # patches live header discovery
    import germany_bnetza_catalog as bnetza
    import germany_afir_static_normalize as afir
except ImportError:
    from . import germany_bnetza_live as bnetza_live  # noqa:F401
    from . import germany_bnetza_catalog as bnetza
    from . import germany_afir_static_normalize as afir


def clean_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


LEGAL_WORDS = {
    "gmbh", "mbh", "ag", "kg", "kgaa", "se", "eg", "ohg", "ug",
    "co", "und", "&", "gesellschaft", "mit", "beschrankter", "haftung",
}


def operator_norm(value) -> str:
    tokens = [t for t in clean_text(value).split() if t not in LEGAL_WORDS]
    return " ".join(tokens)


def operator_similarity(a, b) -> float:
    aa, bb = operator_norm(a), operator_norm(b)
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    at, bt = set(aa.split()), set(bb.split())
    token_jaccard = len(at & bt) / max(1, len(at | bt))
    seq = SequenceMatcher(None, aa, bb).ratio()
    containment = 0.95 if aa in bb or bb in aa else 0.0
    return max(token_jaccard, seq, containment)


def canonical_evse(value):
    return afir.canonical_evse_id(value)


def addr_parts(address: dict | None):
    address = address or {}
    return {
        "postal": clean_text(address.get("postalCode")),
        "city": clean_text(address.get("city")),
        "street": clean_text(address.get("street")),
        "house": clean_text(address.get("houseNumber")),
    }


def address_key(address: dict | None):
    p = addr_parts(address)
    if not p["postal"] or not p["street"]:
        return None
    return "|".join((p["postal"], p["city"], p["street"], p["house"]))


def address_key_loose(address: dict | None):
    p = addr_parts(address)
    if not p["postal"] or not p["street"]:
        return None
    return "|".join((p["postal"], p["street"], p["house"]))


def haversine_m(a: dict | None, b: dict | None):
    if not a or not b:
        return None
    try:
        lat1, lon1 = float(a["latitude"]), float(a["longitude"])
        lat2, lon2 = float(b["latitude"]), float(b["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def station_evse_ids(row: dict):
    out = []
    for conn in row.get("connectors") or []:
        ev = canonical_evse(conn.get("evseId"))
        if ev:
            out.append(ev)
    return sorted(set(out))


def physical_group_key(row: dict):
    """Conservative grouping: same operator + exact postal/street/house when possible.

    Coordinates are quantized and included to prevent merging large premises with the
    same postal address but physically separated charging areas.
    """
    op = operator_norm(row.get("operator"))
    addr = address_key(row.get("address"))
    c = row.get("coordinates") or {}
    lat, lon = c.get("latitude"), c.get("longitude")
    coord = ""
    if lat is not None and lon is not None:
        coord = f"{round(float(lat), 4):.4f}|{round(float(lon), 4):.4f}"
    if addr:
        raw = f"addr|{op}|{addr}|{coord}"
    else:
        raw = f"geo|{op}|{coord}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def group_bnetza(rows: list[dict]):
    groups = defaultdict(list)
    for row in rows:
        groups[physical_group_key(row)].append(row)
    result = []
    for gid, members in groups.items():
        evse = sorted({x for row in members for x in station_evse_ids(row)})
        charge_points = sum((row.get("chargePointCount") or 0) for row in members)
        operators = [row.get("operator") for row in members if row.get("operator")]
        operator = Counter(operators).most_common(1)[0][0] if operators else None
        coords = [row.get("coordinates") for row in members if row.get("coordinates")]
        coord = None
        if coords:
            coord = {
                "latitude": sum(float(x["latitude"]) for x in coords) / len(coords),
                "longitude": sum(float(x["longitude"]) for x in coords) / len(coords),
            }
        address = next((row.get("address") for row in members if address_key(row.get("address"))), None)
        if not address:
            address = next((row.get("address") for row in members if row.get("address")), None)
        result.append({
            "physicalSiteId": f"bnetza-site:{gid}",
            "operator": operator,
            "address": address,
            "coordinates": coord,
            "rowCount": len(members),
            "declaredChargePoints": charge_points,
            "evseIds": evse,
            "sourceStationIds": [row.get("stationId") for row in members],
            "maxConnectionPowerKw": max(
                [row.get("connectionPowerKw") for row in members if row.get("connectionPowerKw") is not None],
                default=None,
            ),
        })
    return result


def grid_cell(coords: dict | None, scale=500):
    if not coords:
        return None
    return (int(float(coords["latitude"]) * scale), int(float(coords["longitude"]) * scale))


def grid_neighbours(cell):
    if cell is None:
        return []
    x, y = cell
    return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def site_has_tariff(site: dict):
    if site.get("tariffs"):
        return True
    for station in site.get("stations") or []:
        if station.get("tariffs"):
            return True
        for point in station.get("points") or []:
            if point.get("tariffs"):
                return True
    return False


def match(bsites: list[dict], asites: list[dict]):
    evse_to_afir = defaultdict(set)
    addr_to_afir = defaultdict(set)
    loose_addr_to_afir = defaultdict(set)
    geo = defaultdict(set)
    by_id = {}
    for idx, site in enumerate(asites):
        aid = f"{site.get('provider')}:{site.get('sourceSiteId') or idx}"
        site["_matchId"] = aid
        by_id[aid] = site
        for ev in site.get("evseIds") or []:
            evse_to_afir[ev].add(aid)
        ak = address_key(site.get("address"))
        if ak:
            addr_to_afir[ak].add(aid)
        alk = address_key_loose(site.get("address"))
        if alk:
            loose_addr_to_afir[alk].add(aid)
        cell = grid_cell(site.get("coordinates"))
        if cell:
            geo[cell].add(aid)

    matched = {}
    conflicts = []
    unmatched = []

    # Pass 1: exact EVSE-ID intersection.
    for b in bsites:
        candidates = set()
        exact_ids = []
        for ev in b.get("evseIds") or []:
            ids = evse_to_afir.get(ev, set())
            if ids:
                candidates.update(ids)
                exact_ids.append(ev)
        if len(candidates) == 1:
            aid = next(iter(candidates))
            matched[b["physicalSiteId"]] = {
                "method": "evse_exact",
                "confidence": 1.0,
                "afirSiteId": aid,
                "matchingEvseIds": exact_ids,
                "distanceM": haversine_m(b.get("coordinates"), by_id[aid].get("coordinates")),
                "operatorSimilarity": operator_similarity(b.get("operator"), by_id[aid].get("operator")),
            }
        elif len(candidates) > 1:
            conflicts.append({
                "bnetzaSiteId": b["physicalSiteId"],
                "reason": "evse_points_to_multiple_afir_sites",
                "candidateAfirSiteIds": sorted(candidates),
                "matchingEvseIds": exact_ids,
            })
        else:
            unmatched.append(b)

    # Pass 2: exact address + reasonably similar operator, unique best candidate.
    still = []
    for b in unmatched:
        candidates = set()
        ak = address_key(b.get("address"))
        if ak:
            candidates.update(addr_to_afir.get(ak, set()))
        if not candidates:
            alk = address_key_loose(b.get("address"))
            if alk:
                candidates.update(loose_addr_to_afir.get(alk, set()))
        scored = []
        for aid in candidates:
            a = by_id[aid]
            sim = operator_similarity(b.get("operator"), a.get("operator"))
            dist = haversine_m(b.get("coordinates"), a.get("coordinates"))
            if sim >= 0.55 and (dist is None or dist <= 250):
                scored.append((sim, -(dist or 0), aid, dist))
        scored.sort(reverse=True)
        if scored and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.12):
            sim, _, aid, dist = scored[0]
            matched[b["physicalSiteId"]] = {
                "method": "address_operator",
                "confidence": round(min(0.94, 0.75 + sim * 0.2), 3),
                "afirSiteId": aid,
                "matchingEvseIds": [],
                "distanceM": dist,
                "operatorSimilarity": sim,
            }
        else:
            still.append(b)
    unmatched = still

    # Pass 3: strict geospatial fallback. Require <=40m and operator similarity >=0.65.
    still = []
    for b in unmatched:
        candidates = set()
        for cell in grid_neighbours(grid_cell(b.get("coordinates"))):
            candidates.update(geo.get(cell, set()))
        scored = []
        for aid in candidates:
            a = by_id[aid]
            dist = haversine_m(b.get("coordinates"), a.get("coordinates"))
            if dist is None or dist > 40:
                continue
            sim = operator_similarity(b.get("operator"), a.get("operator"))
            if sim < 0.65:
                continue
            scored.append((dist, -sim, aid, sim))
        scored.sort()
        if scored and (len(scored) == 1 or scored[1][0] - scored[0][0] >= 12):
            dist, _, aid, sim = scored[0]
            matched[b["physicalSiteId"]] = {
                "method": "geo_operator",
                "confidence": round(max(0.70, 0.90 - dist / 200), 3),
                "afirSiteId": aid,
                "matchingEvseIds": [],
                "distanceM": dist,
                "operatorSimilarity": sim,
            }
        else:
            still.append(b)
    unmatched = still

    # Compact enriched rows only for matched sites; raw source data remains separate.
    match_rows = []
    for b in bsites:
        m = matched.get(b["physicalSiteId"])
        if not m:
            continue
        a = by_id[m["afirSiteId"]]
        match_rows.append({
            "bnetzaSiteId": b["physicalSiteId"],
            "afirSiteId": m["afirSiteId"],
            "provider": a.get("provider"),
            "method": m["method"],
            "confidence": m["confidence"],
            "matchingEvseIds": m["matchingEvseIds"],
            "distanceM": None if m["distanceM"] is None else round(m["distanceM"], 1),
            "operatorSimilarity": round(m["operatorSimilarity"], 3),
            "bnetzaOperator": b.get("operator"),
            "afirOperator": a.get("operator"),
            "bnetzaDeclaredChargePoints": b.get("declaredChargePoints"),
            "afirChargePoints": a.get("chargePointCount"),
            "afirHasTariff": site_has_tariff(a),
            "afirEvseCount": len(a.get("evseIds") or []),
        })

    method_counts = Counter(x["method"] for x in match_rows)
    providers = Counter(x["provider"] for x in match_rows)
    tariff_matches = sum(bool(x["afirHasTariff"]) for x in match_rows)
    stats = {
        "bnetzaPhysicalSites": len(bsites),
        "afirSites": len(asites),
        "matchedPhysicalSites": len(match_rows),
        "unmatchedBnetzaPhysicalSites": len(unmatched),
        "matchRatePct": round(100 * len(match_rows) / max(1, len(bsites)), 2),
        "matchesByMethod": dict(method_counts),
        "matchedWithAfirTariff": tariff_matches,
        "conflicts": len(conflicts),
        "matchesByProvider": dict(providers),
        "bnetzaSitesWithEvseIds": sum(bool(x.get("evseIds")) for x in bsites),
        "bnetzaUniqueEvseIds": len({ev for x in bsites for ev in x.get("evseIds") or []}),
        "matchedExactEvseSites": method_counts.get("evse_exact", 0),
    }
    return match_rows, unmatched, conflicts, stats


def build(output: Path):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bp = root / "bnetza.json.gz"
        ap = root / "afir.json.gz"
        bresult = bnetza.build(None, bp, None)
        aresult = afir.build(ap)

    bsites = group_bnetza(bresult["stations"])
    matches, unmatched, conflicts, stats = match(bsites, aresult["sites"])
    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-bnetza-afir-match-report",
        "generatedAt": afir.utc_now(),
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "dynamicStatusIncluded": False,
            "tariffsRankable": False,
            "note": "QA match report; fallback matches are candidates until quality review.",
        },
        "sources": {
            "bnetza": bresult["source"],
            "afirFeeds": aresult["feeds"],
        },
        "stats": stats,
        "matches": matches,
        "conflicts": conflicts,
        "unmatchedSample": [
            {
                "bnetzaSiteId": x["physicalSiteId"],
                "operator": x.get("operator"),
                "address": x.get("address"),
                "coordinates": x.get("coordinates"),
                "declaredChargePoints": x.get("declaredChargePoints"),
                "evseIds": x.get("evseIds"),
            }
            for x in unmatched[:1000]
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(output, "wb", compresslevel=9) as f:
        f.write(raw)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/germany/bnetza_afir_match_report.json.gz"))
    args = parser.parse_args()
    result = build(args.output)
    print("TCC_GERMANY_MATCH=" + json.dumps(result["stats"], ensure_ascii=False, sort_keys=True))
    for method, count in sorted(result["stats"]["matchesByMethod"].items()):
        print(f"TCC_GERMANY_MATCH_METHOD={method}:{count}")
    for provider, count in sorted(result["stats"]["matchesByProvider"].items()):
        print(f"TCC_GERMANY_MATCH_PROVIDER={provider}:{count}")


if __name__ == "__main__":
    main()
