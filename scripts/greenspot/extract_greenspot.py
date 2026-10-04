#!/usr/bin/env python3
# Reliability audit note: unmatched FRGSP EVSE stay fail-closed.
"""Read-only national Greenspot extractor for Tesla Charge Companion.

Sources:
- current national IRVE consolidated resource on data.gouv.fr
- public Greenspot / Last Mile Solutions map backend at greenspot.evc-net.com

No login, cookie, token or payment/session action is used.
Only EVSEs whose normalized eMI3 identifier starts with FRGSPE are retained.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import gzip
import json
import math
import pathlib
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

IRVE_RESOURCE_ID = "eb76d20a-8501-400e-b336-d85724de5435"
IRVE_URL = f"https://tabular-api.data.gouv.fr/api/resources/{IRVE_RESOURCE_ID}/data/"
LMS_BASE = "https://greenspot.evc-net.com"
LMS_AJAX = f"{LMS_BASE}/api/ajax"
LMS_HANDLER = "\\LMS\\EV\\AsyncServices\\DashboardAsyncService"
TARIFF_PROVIDER = 422
USER_AGENT = "Tesla-Charge-Companion-Greenspot-ReadOnly/1.0"


def http_json(url: str, timeout: int = 45):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read()
    return json.loads(payload.decode("utf-8"))


def normalize_evse(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


def norm_text(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def freshness_key(row: dict) -> tuple[str, str]:
    return (str(row.get("date_maj") or ""), str(row.get("last_modified") or ""))


def fetch_irve_rows(page_size: int = 200) -> tuple[list[dict], dict]:
    page = 1
    rows: list[dict] = []
    meta = {}
    while True:
        params = urllib.parse.urlencode(
            {
                "page": page,
                "page_size": page_size,
                "id_pdc_itinerance__contains": "FR*GSP",
            }
        )
        obj = http_json(f"{IRVE_URL}?{params}", timeout=60)
        batch = obj.get("data") or []
        rows.extend(batch)
        meta = obj.get("meta") or meta
        next_link = (obj.get("links") or {}).get("next")
        if not next_link or not batch:
            break
        page += 1
        if page > 1000:
            raise RuntimeError("IRVE pagination safety limit reached")
    return rows, meta


def is_genuine_greenspot(row: dict) -> bool:
    evse = normalize_evse(row.get("id_pdc_itinerance"))
    # eMI3 country+party+type: FR + GSP + E
    return evse.startswith("FRGSPE")


def dedupe_irve(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    genuine = [r for r in rows if is_genuine_greenspot(r)]
    by_evse: dict[str, dict] = {}
    for row in genuine:
        key = normalize_evse(row.get("id_pdc_itinerance"))
        prev = by_evse.get(key)
        if prev is None or freshness_key(row) >= freshness_key(prev):
            by_evse[key] = row
    return list(by_evse.values()), genuine


def row_coords(row: dict):
    coords = row.get("coordonneesXY")
    if isinstance(coords, list) and len(coords) >= 2:
        try:
            lon = float(coords[0])
            lat = float(coords[1])
            if math.isfinite(lat) and math.isfinite(lon):
                return lat, lon
        except (TypeError, ValueError):
            pass
    lat = row.get("consolidated_latitude")
    lon = row.get("consolidated_longitude")
    try:
        lat = float(lat)
        lon = float(lon)
        if math.isfinite(lat) and math.isfinite(lon):
            return lat, lon
    except (TypeError, ValueError):
        pass
    return None


def async_url(method: str, params: dict, metric_key: str) -> str:
    requests = {
        "0": {
            "handler": LMS_HANDLER,
            "method": method,
            "params": params,
        }
    }
    query = urllib.parse.urlencode(
        {
            "requests": json.dumps(requests, ensure_ascii=False, separators=(",", ":")),
            "metricKey": metric_key,
        }
    )
    return f"{LMS_AJAX}?{query}"


def unwrap_async(obj):
    if isinstance(obj, list):
        if len(obj) == 1 and isinstance(obj[0], list):
            return obj[0]
        return obj
    if isinstance(obj, dict):
        if "0" in obj and isinstance(obj["0"], list):
            return obj["0"]
        if 0 in obj and isinstance(obj[0], list):
            return obj[0]
    return []


def spots_status(lat: float, lon: float, pad: float = 0.0025) -> list[dict]:
    params = {
        "active": True,
        "rechargeSpotIds": None,
        "provider": None,
        "profile": None,
        "view": "clustered",
        "mode": "current",
        "maxCache": 0,
        "bounds": {
            "south": lat - pad,
            "west": lon - pad,
            "north": lat + pad,
            "east": lon + pad,
        },
    }
    return unwrap_async(http_json(async_url("spotsStatus", params, "DeviceMap_432"), timeout=45))


def point_details(device_ids: list[int]) -> list[dict]:
    if not device_ids:
        return []
    params = {
        "deviceIds": device_ids,
        "tariffProvider": TARIFF_PROVIDER,
    }
    return unwrap_async(
        http_json(async_url("spotsStatusPointData", params, "DeviceMap_1037"), timeout=60)
    )


def chunks(values: list, size: int):
    for i in range(0, len(values), size):
        yield values[i : i + size]


def query_site(site: dict) -> dict:
    lat = site["lat"]
    lon = site["lon"]
    expected = set(site["expectedEvse"])

    try:
        status_rows = spots_status(lat, lon, 0.0025)
        ids = sorted(
            {
                int(x["id"])
                for x in status_rows
                if isinstance(x, dict) and x.get("id") is not None
            }
        )
        # In very dense places reduce the radius instead of expanding a huge detail call.
        if len(ids) > 300:
            status_rows = spots_status(lat, lon, 0.0009)
            ids = sorted(
                {
                    int(x["id"])
                    for x in status_rows
                    if isinstance(x, dict) and x.get("id") is not None
                }
            )

        details: list[dict] = []
        for batch in chunks(ids, 80):
            details.extend(point_details(batch))
            time.sleep(0.04)

        own = []
        for item in details:
            if not isinstance(item, dict):
                continue
            evse = normalize_evse(item.get("evseId"))
            if evse.startswith("FRGSPE"):
                own.append(item)

        own_by_evse = {normalize_evse(x.get("evseId")): x for x in own}
        exact = sorted(expected.intersection(own_by_evse))
        missing = sorted(expected.difference(own_by_evse))

        # One wider retry only when exact inventory records were missed.
        if missing:
            status_rows2 = spots_status(lat, lon, 0.0100)
            ids2 = sorted(
                {
                    int(x["id"])
                    for x in status_rows2
                    if isinstance(x, dict) and x.get("id") is not None
                }
            )
            new_ids = [x for x in ids2 if x not in ids]
            for batch in chunks(new_ids, 80):
                details.extend(point_details(batch))
                time.sleep(0.04)
            own = [
                x
                for x in details
                if isinstance(x, dict)
                and normalize_evse(x.get("evseId")).startswith("FRGSPE")
            ]
            own_by_evse = {normalize_evse(x.get("evseId")): x for x in own}
            exact = sorted(expected.intersection(own_by_evse))
            missing = sorted(expected.difference(own_by_evse))

        return {
            "key": site["key"],
            "lat": lat,
            "lon": lon,
            "expected": sorted(expected),
            "exact": exact,
            "missing": missing,
            "details": own,
            "error": None,
        }
    except Exception as exc:
        return {
            "key": site["key"],
            "lat": lat,
            "lon": lon,
            "expected": sorted(expected),
            "exact": [],
            "missing": sorted(expected),
            "details": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def summarize_irve_access(keys: list[str], inventory_by_evse: dict[str, dict]) -> dict:
    rows = [inventory_by_evse[k] for k in keys if k in inventory_by_evse]

    def bucket(field: str):
        return dict(
            sorted(
                Counter(
                    "<null>" if r.get(field) is None else str(r.get(field))
                    for r in rows
                ).items(),
                key=lambda kv: (-kv[1], kv[0]),
            )
        )

    dates = sorted(str(r.get("date_maj")) for r in rows if r.get("date_maj"))
    return {
        "count": len(rows),
        "conditionAcces": bucket("condition_acces"),
        "paiementActe": bucket("paiement_acte"),
        "paiementCb": bucket("paiement_cb"),
        "paiementAutre": bucket("paiement_autre"),
        "reservation": bucket("reservation"),
        "implantationStation": bucket("implantation_station"),
        "operator": bucket("nom_operateur"),
        "brand": bucket("nom_enseigne"),
        "dateMajMin": dates[0] if dates else None,
        "dateMajMax": dates[-1] if dates else None,
    }


def clean_detail(item: dict) -> dict:
    location = item.get("location") or {}
    return {
        "id": item.get("id"),
        "evseId": item.get("evseId"),
        "rechargeSpotId": item.get("rechargeSpotId"),
        "channelNo": item.get("channelNo"),
        "globalStatus": item.get("globalStatus"),
        "lastStatusChangeDate": item.get("lastStatusChangeDate"),
        "lastUpdateDate": item.get("lastUpdateDate"),
        "connectorName": item.get("connectorName"),
        "connectorFormat": item.get("connectorFormat"),
        "phases": item.get("phases"),
        "amp": item.get("amp"),
        "powerW": item.get("power"),
        "maxPower": item.get("maxPower"),
        "vat": item.get("vat"),
        "tariffId": item.get("tariffId"),
        "simpleTariff": item.get("simpleTariff"),
        "qrCode": item.get("qrCode"),
        "qrCodeFull": item.get("qrCodeFull"),
        "location": {
            "id": location.get("id"),
            "locationId": location.get("locationId"),
            "name": location.get("name"),
            "address": location.get("address"),
            "zipCode": location.get("zipCode"),
            "city": location.get("city"),
            "countryCode": location.get("countryCode"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "alwaysOpen": location.get("alwaysOpen"),
            "chargingWhenClosed": location.get("chargingWhenClosed"),
            "lastUpdateDate": location.get("lastUpdateDate"),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-sites", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    raw_rows, irve_meta = fetch_irve_rows()
    inventory, genuine_rows = dedupe_irve(raw_rows)

    missing_coords = []
    grouped: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for row in inventory:
        coords = row_coords(row)
        if not coords:
            missing_coords.append(row)
            continue
        # Preserve site separation while collapsing duplicate rows at the same published point.
        key = (round(coords[0], 6), round(coords[1], 6))
        grouped[key].append(row)

    sites = []
    for idx, (key, rows) in enumerate(sorted(grouped.items())):
        if args.max_sites and idx >= args.max_sites:
            break
        sites.append(
            {
                "key": f"{key[0]:.6f},{key[1]:.6f}",
                "lat": key[0],
                "lon": key[1],
                "expectedEvse": sorted(
                    {normalize_evse(r.get("id_pdc_itinerance")) for r in rows}
                ),
            }
        )

    site_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(query_site, site) for site in sites]
        for fut in concurrent.futures.as_completed(futures):
            site_results.append(fut.result())

    live_by_evse: dict[str, dict] = {}
    errors = []
    missing_exact = set()
    for site in site_results:
        if site.get("error"):
            errors.append(
                {
                    "site": site["key"],
                    "expected": site["expected"],
                    "error": site["error"],
                }
            )
        missing_exact.update(site.get("missing") or [])
        for detail in site.get("details") or []:
            key = normalize_evse(detail.get("evseId"))
            if key.startswith("FRGSPE"):
                live_by_evse[key] = detail

    inventory_by_evse = {
        normalize_evse(row.get("id_pdc_itinerance")): row for row in inventory
    }

    matched = sorted(set(inventory_by_evse).intersection(live_by_evse))
    unmatched = sorted(set(inventory_by_evse).difference(live_by_evse))
    live_extras = sorted(set(live_by_evse).difference(inventory_by_evse))

    records = []
    for evse in sorted(live_by_evse):
        detail = clean_detail(live_by_evse[evse])
        irve = inventory_by_evse.get(evse)
        records.append(
            {
                "evseKey": evse,
                "match": "exact_irve_evse" if irve else "live_extra_same_queried_site",
                "irve": irve,
                "live": detail,
                "directTariff": detail.get("simpleTariff"),
                "source": "greenspot_evcnet_public_map",
                "tariffProvider": TARIFF_PROVIDER,
            }
        )

    signature_counts = defaultdict(int)
    with_tariff = 0
    without_tariff = 0
    for record in records:
        tariff = record.get("directTariff")
        if tariff is None:
            without_tariff += 1
            continue
        with_tariff += 1
        signature_counts[json.dumps(tariff, sort_keys=True, ensure_ascii=False)] += 1

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "schemaVersion": 1,
        "country": "FR",
        "cpo": "Greenspot",
        "generatedAt": now,
        "source": {
            "inventory": {
                "authority": "data.gouv.fr national IRVE consolidated resource",
                "resourceId": IRVE_RESOURCE_ID,
                "filterDiscovery": "id_pdc_itinerance contains FR*GSP, then strict normalized prefix FRGSPE",
            },
            "live": {
                "authority": "Greenspot / Last Mile Solutions first-party public portal",
                "base": LMS_BASE,
                "endpoint": "/api/ajax",
                "handler": LMS_HANDLER,
                "statusMethod": "spotsStatus",
                "detailMethod": "spotsStatusPointData",
                "tariffProvider": TARIFF_PROVIDER,
                "authentication": "none",
            },
        },
        "records": records,
        "unmatchedInventoryEvses": unmatched,
        "inventoryWithoutCoordinates": [
            r.get("id_pdc_itinerance") for r in missing_coords
        ],
        "siteErrors": errors,
        "liveExtras": live_extras,
    }

    report = {
        "schemaVersion": 1,
        "generatedAt": now,
        "country": "FR",
        "cpo": "Greenspot",
        "irveCandidateRows": len(raw_rows),
        "strictGreenspotRowsBeforeDedup": len(genuine_rows),
        "uniqueIrveEvses": len(inventory_by_evse),
        "uniqueCoordinateSites": len(grouped),
        "queriedSites": len(sites),
        "inventoryWithoutCoordinates": len(missing_coords),
        "exactLiveMatches": len(matched),
        "unmatchedIrveEvses": len(unmatched),
        "matchedInventoryProfile": summarize_irve_access(matched, inventory_by_evse),
        "unmatchedInventoryProfile": summarize_irve_access(unmatched, inventory_by_evse),
        "unmatchedPriorityRows": [
            {
                "evse": inventory_by_evse[k].get("id_pdc_itinerance"),
                "station": inventory_by_evse[k].get("id_station_itinerance"),
                "name": inventory_by_evse[k].get("nom_station"),
                "operator": inventory_by_evse[k].get("nom_operateur"),
                "brand": inventory_by_evse[k].get("nom_enseigne"),
                "coords": inventory_by_evse[k].get("coordonneesXY"),
                "powerKw": inventory_by_evse[k].get("puissance_nominale"),
                "conditionAcces": inventory_by_evse[k].get("condition_acces"),
                "paiementActe": inventory_by_evse[k].get("paiement_acte"),
                "paiementCb": inventory_by_evse[k].get("paiement_cb"),
                "paiementAutre": inventory_by_evse[k].get("paiement_autre"),
                "reservation": inventory_by_evse[k].get("reservation"),
                "tarification": inventory_by_evse[k].get("tarification"),
                "dateMaj": inventory_by_evse[k].get("date_maj"),
            }
            for k in unmatched
            if (
                inventory_by_evse[k].get("paiement_acte") is True
                or inventory_by_evse[k].get("paiement_cb") is True
                or inventory_by_evse[k].get("reservation") is False
            )
        ],
        "liveExtrasAtQueriedSites": len(live_extras),
        "liveRecords": len(records),
        "liveRecordsWithSimpleTariff": with_tariff,
        "liveRecordsWithoutSimpleTariff": without_tariff,
        "uniqueSimpleTariffSignatures": len(signature_counts),
        "tariffSignatures": [
            {"count": count, "simpleTariff": json.loads(signature)}
            for signature, count in sorted(
                signature_counts.items(), key=lambda kv: (-kv[1], kv[0])
            )
        ],
        "siteErrors": len(errors),
        "irveMeta": irve_meta,
        "classification": {
            "ownNetworkFilter": "normalized live evseId starts FRGSPE",
            "directTariffField": "simpleTariff",
            "thirdPartyRoamingExcluded": True,
            "nationalConstantAllowed": False,
            "unmatchedPolicy": "fail_closed",
            "note": "Greenspot first-party states there is no badge surcharge on its own network; only FRGSP own-network records are eligible. Preserve every timeslot/component exactly.",
        },
    }

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gz_path = pathlib.Path(str(out_path) + ".gz")
    with gzip.open(gz_path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    report_path = pathlib.Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
