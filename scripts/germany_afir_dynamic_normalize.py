#!/usr/bin/env python3
"""Normalize public German AFIR dynamic status and join it to static EVSE IDs.

Current public dynamic feeds:
- eRound
- Qwello

This remains a staging/QA artifact. Occupied/charging/blocked are deliberately
NOT treated as hardware outages: TCC's simplified service state is about
operational vs out-of-service, not free-vs-busy connector availability.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import germany_afir_static_normalize as static

ENDPOINT = static.ENDPOINT
USER_AGENT = static.USER_AGENT
DYNAMIC_OFFERS = {
    "eround": {"offerId": "961629419076456448", "license": "CC0"},
    "qwello": {"offerId": "972966368902897664", "license": "CC0"},
}
STATIC_OFFERS = {
    "eround": static.OFFERS["eround"],
    "qwello": static.OFFERS["qwello"],
}

# These are intentionally conservative. Busy/reserved-style states still mean
# the charging equipment is operating, while explicit failure/unavailability
# states mean it should be considered out of service for TCC.
OPERATIONAL_RAW = {
    "available", "occupied", "charging", "blocked", "reserved", "preparing",
    "finishing", "suspendedev", "suspendedevse",
}
OUT_OF_SERVICE_RAW = {
    "faulted", "unavailable", "inoperative", "outoforder", "offline",
    "notavailable", "temporarilyunavailable",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_dynamic(offer_id: str) -> tuple[dict, dict]:
    url = ENDPOINT.format(offer_id=offer_id)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/xml, */*",
        "Accept-Encoding": "gzip",
        "Range": "bytes=0-99999999",
    })
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read()
        headers = dict(response.headers.items())
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8-sig"))
    return payload, {
        "url": url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "decodedBytes": len(raw),
        "contentType": headers.get("Content-Type"),
        "contentEncoding": headers.get("Content-Encoding"),
    }


def iter_publications(payload: Any):
    """Yield AFIR status publications independent of the envelope variant."""
    if isinstance(payload, dict):
        publication = payload.get("aegiEnergyInfrastructureStatusPublication")
        if isinstance(publication, dict):
            yield publication
        for value in payload.values():
            yield from iter_publications(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from iter_publications(value)


def static_indices(provider: str, payload: dict):
    sites, profile = static.get_sites(payload)
    point_index = {}
    station_index = {}
    site_index = {}
    evse_to_point = defaultdict(list)

    for raw_site in sites:
        normalized_site = static.normalize_site(provider, STATIC_OFFERS[provider]["offerId"], raw_site)
        sid = normalized_site.get("sourceSiteId")
        if sid:
            site_index[str(sid)] = {
                "sourceSiteId": sid,
                "operator": normalized_site.get("operator"),
                "evseIds": normalized_site.get("evseIds") or [],
            }
        for station in normalized_site.get("stations") or []:
            stid = station.get("sourceStationId")
            if stid:
                station_index[str(stid)] = {
                    "sourceStationId": stid,
                    "sourceSiteId": sid,
                }
            for point in station.get("points") or []:
                pid = point.get("sourcePointId")
                if not pid:
                    continue
                evse_ids = sorted({x.get("canonical") for x in point.get("evseIds") or [] if x.get("canonical")})
                row = {
                    "sourcePointId": str(pid),
                    "sourceStationId": stid,
                    "sourceSiteId": sid,
                    "evseIds": evse_ids,
                    "maxConnectorPowerKw": point.get("maxConnectorPowerKw"),
                }
                point_index[str(pid)] = row
                for evse in evse_ids:
                    evse_to_point[evse].append(str(pid))
    return {
        "profile": profile,
        "point": point_index,
        "station": station_index,
        "site": site_index,
        "evseToPoint": dict(evse_to_point),
    }


def raw_status_value(status_obj):
    value = static.enum_value(status_obj)
    return str(value).strip() if value is not None else None


def normalize_raw_state(raw_status: str | None, station_is_available: bool | None):
    key = "".join(ch for ch in str(raw_status or "").lower() if ch.isalnum())
    # Explicit station-level unavailability wins over a missing/unknown point state.
    if station_is_available is False:
        return "out_of_service"
    if key in OPERATIONAL_RAW:
        return "operational"
    if key in OUT_OF_SERVICE_RAW:
        return "out_of_service"
    return "unknown"


def energy_rate_updates(status: dict):
    result = []
    for update in static.as_list(status.get("energyRateUpdate")):
        if not isinstance(update, dict):
            continue
        prices = []
        for price in static.as_list(update.get("energyPrice")):
            if not isinstance(price, dict):
                continue
            prices.append({
                "priceType": static.enum_value(price.get("priceType")),
                "value": static.safe_float(price.get("value")),
                "priceCap": static.safe_float(price.get("priceCap")),
                "taxIncluded": price.get("taxIncluded"),
                "timeBasedApplicability": price.get("timeBasedApplicability"),
                "overallPeriod": price.get("overallPeriod"),
            })
        if prices:
            result.append({
                "energyRateReferenceId": ((update.get("energyRateReference") or {}).get("idG")
                                          if isinstance(update.get("energyRateReference"), dict) else None),
                "lastUpdated": update.get("lastUpdated"),
                "prices": prices,
            })
    return result


def extract_dynamic(provider: str, payload: dict, indices: dict):
    rows = []
    raw_statuses = Counter()
    unmatched_point_refs = []
    station_availability = Counter()
    publication_times = []

    for publication in iter_publications(payload):
        if publication.get("publicationTime"):
            publication_times.append(publication.get("publicationTime"))
        for site_status in static.as_list(publication.get("energyInfrastructureSiteStatus")):
            if not isinstance(site_status, dict):
                continue
            site_ref = site_status.get("reference") or {}
            dynamic_site_id = site_ref.get("idG") if isinstance(site_ref, dict) else None
            for station_status in static.as_list(site_status.get("energyInfrastructureStationStatus")):
                if not isinstance(station_status, dict):
                    continue
                station_ref = station_status.get("reference") or {}
                dynamic_station_id = station_ref.get("idG") if isinstance(station_ref, dict) else None
                is_available = station_status.get("isAvailable")
                if is_available is True:
                    station_availability["true"] += 1
                elif is_available is False:
                    station_availability["false"] += 1
                else:
                    station_availability["missing"] += 1
                for refill_status in static.as_list(station_status.get("refillPointStatus")):
                    if not isinstance(refill_status, dict):
                        continue
                    point_status = refill_status.get("aegiElectricChargingPointStatus")
                    if not isinstance(point_status, dict):
                        continue
                    reference = point_status.get("reference") or {}
                    point_id = str(reference.get("idG") or "") if isinstance(reference, dict) else ""
                    raw_status = raw_status_value(point_status.get("status"))
                    raw_statuses[raw_status or "<missing>"] += 1
                    static_point = indices["point"].get(point_id)
                    normalized = normalize_raw_state(raw_status, is_available)
                    row = {
                        "provider": provider,
                        "dynamicOfferId": DYNAMIC_OFFERS[provider]["offerId"],
                        "dynamicSiteId": dynamic_site_id,
                        "dynamicStationId": dynamic_station_id,
                        "sourcePointId": point_id or None,
                        "joinedToStaticPoint": static_point is not None,
                        "staticSiteId": static_point.get("sourceSiteId") if static_point else None,
                        "staticStationId": static_point.get("sourceStationId") if static_point else None,
                        "evseIds": static_point.get("evseIds") if static_point else [],
                        "rawStatus": raw_status,
                        "stationIsAvailable": is_available if isinstance(is_available, bool) else None,
                        "serviceState": normalized,
                        "lastUpdated": point_status.get("lastUpdated") or (reference.get("versionG") if isinstance(reference, dict) else None),
                        "dynamicTariffUpdates": energy_rate_updates(point_status),
                    }
                    rows.append(row)
                    if static_point is None:
                        unmatched_point_refs.append(point_id)

    return rows, {
        "publicationTimes": publication_times,
        "rawStatusDistribution": dict(raw_statuses),
        "stationIsAvailableDistribution": dict(station_availability),
        "unmatchedPointReferenceSample": [x for x in unmatched_point_refs if x][:100],
    }


def aggregate_sites(rows: list[dict]):
    grouped = defaultdict(list)
    for row in rows:
        key = (row["provider"], row.get("staticSiteId") or row.get("dynamicSiteId"))
        grouped[key].append(row)
    output = []
    for (provider, site_id), members in grouped.items():
        states = Counter(x["serviceState"] for x in members)
        if states["operational"]:
            service_state = "operational"
        elif states["out_of_service"] and not states["unknown"]:
            service_state = "out_of_service"
        else:
            service_state = "unknown"
        output.append({
            "provider": provider,
            "siteId": site_id,
            "serviceState": service_state,
            "pointStates": dict(states),
            "pointCount": len(members),
            "evseIds": sorted({ev for m in members for ev in m.get("evseIds") or []}),
            "allPointsJoinedToStatic": all(m.get("joinedToStaticPoint") for m in members),
            "hasDynamicTariffUpdate": any(bool(m.get("dynamicTariffUpdates")) for m in members),
        })
    return output


def build(output: Path):
    feeds = []
    all_rows = []
    static_summary = {}
    for provider in DYNAMIC_OFFERS:
        static_payload, static_transport = static.fetch_offer(STATIC_OFFERS[provider]["offerId"])
        indices = static_indices(provider, static_payload)
        dynamic_payload, dynamic_transport = fetch_dynamic(DYNAMIC_OFFERS[provider]["offerId"])
        rows, extra = extract_dynamic(provider, dynamic_payload, indices)
        all_rows.extend(rows)
        joined = sum(x["joinedToStaticPoint"] for x in rows)
        with_evse = sum(bool(x["evseIds"]) for x in rows)
        state_counts = Counter(x["serviceState"] for x in rows)
        tariff_updates = sum(bool(x["dynamicTariffUpdates"]) for x in rows)
        feed_stats = {
            "dynamicPoints": len(rows),
            "joinedStaticPoints": joined,
            "staticJoinRatePct": round(100 * joined / max(1, len(rows)), 2),
            "pointsWithCanonicalEvse": with_evse,
            "canonicalEvseRatePct": round(100 * with_evse / max(1, len(rows)), 2),
            "serviceStateDistribution": dict(state_counts),
            "dynamicTariffUpdatePoints": tariff_updates,
            "rawStatusDistribution": extra["rawStatusDistribution"],
            "stationIsAvailableDistribution": extra["stationIsAvailableDistribution"],
        }
        static_summary[provider] = {
            "staticPoints": len(indices["point"]),
            "staticStations": len(indices["station"]),
            "staticSites": len(indices["site"]),
        }
        feeds.append({
            "provider": provider,
            "staticOfferId": STATIC_OFFERS[provider]["offerId"],
            "dynamicOfferId": DYNAMIC_OFFERS[provider]["offerId"],
            "license": DYNAMIC_OFFERS[provider]["license"],
            "staticProfile": indices["profile"],
            "staticTransport": static_transport,
            "dynamicTransport": dynamic_transport,
            "publicationTimes": extra["publicationTimes"],
            "stats": feed_stats,
            "unmatchedPointReferenceSample": extra["unmatchedPointReferenceSample"],
        })

    sites = aggregate_sites(all_rows)
    total_joined = sum(x["joinedToStaticPoint"] for x in all_rows)
    total_evse = sum(bool(x["evseIds"]) for x in all_rows)
    total_states = Counter(x["serviceState"] for x in all_rows)
    site_states = Counter(x["serviceState"] for x in sites)
    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-afir-open-dynamic-normalized",
        "generatedAt": utc_now(),
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "dynamicStatusIncluded": True,
            "tariffsAreRawAfirComponents": True,
            "tariffsRankable": False,
            "statusSemantics": "operational means not explicitly out of service; busy states are not failures",
        },
        "staticSummary": static_summary,
        "feeds": feeds,
        "stats": {
            "dynamicPoints": len(all_rows),
            "joinedStaticPoints": total_joined,
            "staticJoinRatePct": round(100 * total_joined / max(1, len(all_rows)), 2),
            "pointsWithCanonicalEvse": total_evse,
            "canonicalEvseRatePct": round(100 * total_evse / max(1, len(all_rows)), 2),
            "serviceStateDistribution": dict(total_states),
            "sites": len(sites),
            "siteServiceStateDistribution": dict(site_states),
            "dynamicTariffUpdatePoints": sum(bool(x["dynamicTariffUpdates"]) for x in all_rows),
        },
        "points": all_rows,
        "sites": sites,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(result, handle, ensure_ascii=False, separators=(",", ":"))
    return result


def main():
    output = Path("data/germany/afir_open_dynamic_normalized.json.gz")
    result = build(output)
    print("TCC_AFIR_DYNAMIC_NORMALIZED=" + json.dumps(result["stats"], ensure_ascii=False, sort_keys=True))
    for feed in result["feeds"]:
        print("TCC_AFIR_DYNAMIC_FEED=" + json.dumps({"provider": feed["provider"], **feed["stats"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
