#!/usr/bin/env python3
"""Normalize selected public German AFIR/DATEX II static charging feeds.

The output is a QA/staging artifact. It preserves raw tariff components and
normalizes physical/technical data without yet deciding TCC tariff precedence.
Only Mobilithek offers that currently allow anonymous file access are included.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT = "https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{offer_id}/file/noauth"
USER_AGENT = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"

OFFERS = {
    "chargecloud": {"offerId": "978597062404620288", "license": "CC0"},
    "eround": {"offerId": "961625658278940672", "license": "CC0"},
    "qwello": {"offerId": "972963216296222720", "license": "CC0"},
}

EVSE_ID_HINT = re.compile(r"^[A-Z]{2}[A-Z0-9*._:-]{5,}$", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def enum_value(value):
    if isinstance(value, dict):
        return value.get("value") or value.get("extendedValueG")
    return value


def text_value(value):
    """Pick a human-readable multilingual value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        if isinstance(value.get("value"), str):
            return value["value"].strip() or None
        vals = as_list(value.get("values"))
        for preferred in ("de", "en"):
            for item in vals:
                if isinstance(item, dict) and item.get("lang") == preferred and item.get("value"):
                    return str(item["value"]).strip()
        for item in vals:
            if isinstance(item, dict) and item.get("value"):
                return str(item["value"]).strip()
    return None


def safe_float(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def canonical_evse_id(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip().upper()
    if not EVSE_ID_HINT.match(raw):
        return None
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    if len(compact) < 7 or not compact.startswith("DE"):
        return None
    return compact


def fetch_offer(offer_id: str) -> tuple[dict, dict]:
    url = ENDPOINT.format(offer_id=offer_id)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, */*",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            headers = dict(response.headers.items())
            if "gzip" in response.headers.get("Content-Encoding", "").lower():
                raw = gzip.GzipFile(fileobj=response).read()
            else:
                raw = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}: {exc.read(1000)!r}") from exc
    data = json.loads(raw.decode("utf-8-sig"))
    return data, {
        "url": url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "decodedBytes": len(raw),
        "contentType": headers.get("Content-Type"),
        "contentEncoding": headers.get("Content-Encoding"),
    }


def get_sites(payload: dict) -> tuple[list[dict], dict]:
    root = payload.get("payload") or {}
    publication = root.get("aegiEnergyInfrastructureTablePublication") or {}
    sites = []
    for table in as_list(publication.get("energyInfrastructureTable")):
        if isinstance(table, dict):
            sites.extend(s for s in as_list(table.get("energyInfrastructureSite")) if isinstance(s, dict))
    profile = {
        "modelBaseVersionG": root.get("modelBaseVersionG"),
        "versionG": root.get("versionG"),
        "profileNameG": root.get("profileNameG"),
        "profileVersionG": root.get("profileVersionG"),
        "publicationTime": publication.get("publicationTime"),
        "publicationCreator": publication.get("publicationCreator"),
    }
    return sites, profile


def coordinates_from_location(location: Any):
    if not isinstance(location, dict):
        return None
    # DATEX implementations use both pointByCoordinates and coordinatesForDisplay,
    # under point or area locations. Walk deterministically and take the first sane pair.
    stack = [location]
    while stack:
        current = stack.pop(0)
        if not isinstance(current, dict):
            continue
        lat = safe_float(current.get("latitude"))
        lon = safe_float(current.get("longitude"))
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return {"latitude": lat, "longitude": lon}
        for key in (
            "pointCoordinates", "coordinatesForDisplay", "pointByCoordinates",
            "locPointLocation", "locAreaLocation", "locationReference",
        ):
            child = current.get(key)
            if isinstance(child, dict):
                stack.append(child)
    return None


def find_facility_address(value: Any):
    if not isinstance(value, dict):
        return None
    queue = [value]
    while queue:
        current = queue.pop(0)
        if not isinstance(current, dict):
            continue
        if "postcode" in current and ("city" in current or "addressLine" in current):
            lines = {}
            for line in as_list(current.get("addressLine")):
                if not isinstance(line, dict):
                    continue
                kind = enum_value(line.get("type"))
                txt = text_value(line.get("text"))
                if kind and txt:
                    lines[str(kind)] = txt
            return {
                "street": lines.get("street"),
                "houseNumber": lines.get("houseNumber"),
                "region": lines.get("region"),
                "postalCode": str(current.get("postcode") or "").strip() or None,
                "city": text_value(current.get("city")),
                "countryCode": str(current.get("countryCode") or "DE").upper(),
            }
        for child in current.values():
            if isinstance(child, dict):
                queue.append(child)
            elif isinstance(child, list):
                queue.extend(x for x in child if isinstance(x, dict))
    return None


def organisation_name(wrapper: Any):
    if not isinstance(wrapper, dict):
        return None
    org = wrapper.get("afacAnOrganisation") if isinstance(wrapper.get("afacAnOrganisation"), dict) else wrapper
    return text_value(org.get("name")) or text_value(org.get("legalName"))


def external_identifiers(value: Any):
    results = []
    for item in as_list(value):
        if not isinstance(item, dict):
            continue
        identifier = item.get("identifier")
        if not identifier:
            continue
        type_obj = item.get("typeOfIdentifier")
        type_value = enum_value(type_obj)
        extended = type_obj.get("extendedValueG") if isinstance(type_obj, dict) else None
        results.append({
            "identifier": str(identifier).strip(),
            "type": type_value,
            "extendedType": extended,
        })
    return results


def pick_evse_ids(point: dict):
    candidates = []
    for item in external_identifiers(point.get("externalIdentifier")):
        marker = f"{item.get('type') or ''} {item.get('extendedType') or ''}".lower()
        canonical = canonical_evse_id(item.get("identifier"))
        if canonical and ("evse" in marker or canonical.startswith("DE")):
            candidates.append({"raw": item["identifier"], "canonical": canonical, "source": "externalIdentifier"})
    idg = point.get("idG")
    canonical = canonical_evse_id(idg if isinstance(idg, str) else None)
    if canonical:
        candidates.append({"raw": idg, "canonical": canonical, "source": "idG"})
    dedup = []
    seen = set()
    for item in candidates:
        if item["canonical"] not in seen:
            seen.add(item["canonical"])
            dedup.append(item)
    return dedup


def normalize_power_kw(raw):
    """Connector maxPowerAtSocket is observed in watts in all tested feeds."""
    x = safe_float(raw)
    if x is None or x < 0:
        return None
    return x / 1000.0


def normalize_connectors(point: dict):
    connectors = []
    for conn in as_list(point.get("connector")):
        if not isinstance(conn, dict):
            continue
        power_kw = normalize_power_kw(conn.get("maxPowerAtSocket"))
        connectors.append({
            "type": enum_value(conn.get("connectorType")),
            "format": enum_value(conn.get("connectorFormat")),
            "powerKw": power_kw,
            "rawPowerAtSocket": safe_float(conn.get("maxPowerAtSocket")),
            "voltage": safe_float(conn.get("voltage")),
            "maximumCurrent": safe_float(conn.get("maximumCurrent")),
            "externalIdentifiers": external_identifiers(conn.get("externalIdentifier")),
        })
    return connectors


def normalize_tariffs(container: dict, scope: str):
    rates = []
    for energy in as_list(container.get("electricEnergy")):
        if not isinstance(energy, dict):
            continue
        for rate in as_list(energy.get("energyRate")):
            if not isinstance(rate, dict):
                continue
            currencies = [str(x) for x in as_list(rate.get("applicableCurrency")) if x]
            prices = []
            for price in as_list(rate.get("energyPrice")):
                if not isinstance(price, dict):
                    continue
                prices.append({
                    "priceType": enum_value(price.get("priceType")),
                    "value": safe_float(price.get("value")),
                    "priceCap": safe_float(price.get("priceCap")),
                    "taxIncluded": price.get("taxIncluded"),
                    "timeBasedApplicability": price.get("timeBasedApplicability"),
                    "overallPeriod": price.get("overallPeriod"),
                })
            if prices:
                rates.append({
                    "scope": scope,
                    "idG": rate.get("idG"),
                    "lastUpdated": rate.get("lastUpdated"),
                    "currency": currencies,
                    "prices": prices,
                    "payment": rate.get("payment"),
                })
    return rates


def normalize_site(provider: str, offer_id: str, site: dict):
    site_coords = coordinates_from_location(site.get("locationReference"))
    site_address = find_facility_address(site.get("locationReference"))
    site_operator = organisation_name(site.get("operator"))
    stations_out = []
    evse_all = []
    site_tariffs = normalize_tariffs(site, "site")

    for station in as_list(site.get("energyInfrastructureStation")):
        if not isinstance(station, dict):
            continue
        station_coords = coordinates_from_location(station.get("locationReference")) or site_coords
        station_address = find_facility_address(station.get("locationReference")) or site_address
        station_operator = organisation_name(station.get("operator")) or site_operator
        points = []
        station_tariffs = normalize_tariffs(station, "station")
        for refill in as_list(station.get("refillPoint")):
            if not isinstance(refill, dict):
                continue
            point = refill.get("aegiElectricChargingPoint")
            if not isinstance(point, dict):
                continue
            evse_ids = pick_evse_ids(point)
            evse_all.extend(x["canonical"] for x in evse_ids)
            connectors = normalize_connectors(point)
            point_tariffs = normalize_tariffs(point, "chargingPoint")
            powers = [c["powerKw"] for c in connectors if c.get("powerKw") is not None]
            points.append({
                "sourcePointId": point.get("idG"),
                "version": point.get("versionG"),
                "currentType": enum_value(point.get("currentType")),
                "deliveryUnit": enum_value(point.get("deliveryUnit")),
                "chargingMode": enum_value(point.get("chargingMode")),
                "numberOfConnectors": point.get("numberOfConnectors"),
                "evseIds": evse_ids,
                "connectors": connectors,
                "maxConnectorPowerKw": max(powers) if powers else None,
                "tariffs": point_tariffs,
            })
        station_powers = [p["maxConnectorPowerKw"] for p in points if p.get("maxConnectorPowerKw") is not None]
        stations_out.append({
            "sourceStationId": station.get("idG"),
            "version": station.get("versionG"),
            "lastUpdated": station.get("lastUpdated"),
            "name": text_value(station.get("name")),
            "operator": station_operator,
            "coordinates": station_coords,
            "address": station_address,
            "numberOfRefillPoints": station.get("numberOfRefillPoints"),
            "maxConnectorPowerKw": max(station_powers) if station_powers else None,
            "authentication": [enum_value(x) for x in as_list(station.get("authenticationAndIdentificationMethods"))],
            "points": points,
            "tariffs": station_tariffs,
        })

    coords = site_coords or next((s["coordinates"] for s in stations_out if s.get("coordinates")), None)
    address = site_address or next((s["address"] for s in stations_out if s.get("address")), None)
    operators = [s.get("operator") for s in stations_out if s.get("operator")]
    operator = site_operator or (Counter(operators).most_common(1)[0][0] if operators else None)
    max_powers = [s["maxConnectorPowerKw"] for s in stations_out if s.get("maxConnectorPowerKw") is not None]
    return {
        "source": "mobilithek-afir",
        "provider": provider,
        "offerId": offer_id,
        "sourceSiteId": site.get("idG"),
        "version": site.get("versionG"),
        "lastUpdated": site.get("lastUpdated"),
        "name": text_value(site.get("name")),
        "typeOfSite": enum_value(site.get("typeOfSite")),
        "operator": operator,
        "coordinates": coords,
        "address": address,
        "evseIds": sorted(set(evse_all)),
        "stationCount": len(stations_out),
        "chargePointCount": sum(len(s["points"]) for s in stations_out),
        "maxConnectorPowerKw": max(max_powers) if max_powers else None,
        "stations": stations_out,
        "tariffs": site_tariffs,
    }


def build(output: Path) -> dict:
    feeds = []
    all_sites = []
    for provider, meta in OFFERS.items():
        payload, transport = fetch_offer(meta["offerId"])
        sites, profile = get_sites(payload)
        normalized = [normalize_site(provider, meta["offerId"], site) for site in sites]
        feeds.append({
            "provider": provider,
            "offerId": meta["offerId"],
            "license": meta["license"],
            "profile": profile,
            "transport": transport,
            "stats": {
                "sites": len(normalized),
                "stations": sum(x["stationCount"] for x in normalized),
                "chargePoints": sum(x["chargePointCount"] for x in normalized),
                "sitesWithEvse": sum(bool(x["evseIds"]) for x in normalized),
                "uniqueEvseIds": len({ev for x in normalized for ev in x["evseIds"]}),
                "sitesWithTariffs": sum(bool(x["tariffs"]) or any(bool(s["tariffs"]) or any(bool(p["tariffs"]) for p in s["points"]) for s in x["stations"]) for x in normalized),
            },
        })
        all_sites.extend(normalized)

    all_evse = [ev for site in all_sites for ev in site["evseIds"]]
    stats = {
        "sites": len(all_sites),
        "stations": sum(x["stationCount"] for x in all_sites),
        "chargePoints": sum(x["chargePointCount"] for x in all_sites),
        "sitesWithCoordinates": sum(bool(x["coordinates"]) for x in all_sites),
        "sitesWithAddress": sum(bool(x["address"]) for x in all_sites),
        "sitesWithOperator": sum(bool(x["operator"]) for x in all_sites),
        "sitesWithEvse": sum(bool(x["evseIds"]) for x in all_sites),
        "uniqueEvseIds": len(set(all_evse)),
        "duplicateEvseIdsAcrossSites": sum(count - 1 for count in Counter(all_evse).values() if count > 1),
        "sitesWithTariffs": sum(bool(x["tariffs"]) or any(bool(s["tariffs"]) or any(bool(p["tariffs"]) for p in s["points"]) for s in x["stations"]) for x in all_sites),
    }
    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-afir-open-static-normalized",
        "generatedAt": utc_now(),
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "dynamicStatusIncluded": False,
            "tariffsAreRawAfirComponents": True,
            "tariffsRankable": False,
            "note": "No tariff precedence/classification is applied at this stage.",
        },
        "feeds": feeds,
        "stats": stats,
        "sites": all_sites,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(output, "wb", compresslevel=9) as handle:
        handle.write(encoded)
    return result


def main():
    output = Path("data/germany/afir_open_static_normalized.json.gz")
    result = build(output)
    print("TCC_AFIR_NORMALIZED=" + json.dumps(result["stats"], ensure_ascii=False, sort_keys=True))
    for feed in result["feeds"]:
        print("TCC_AFIR_FEED=" + json.dumps({"provider": feed["provider"], **feed["stats"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
