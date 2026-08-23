#!/usr/bin/env python3
"""Enrich the strict E55C station inventory with E55C Scan Pay tariffs.

Only public, read-only E55C sources are used:

* the E55C uMap lists the exact Scan Pay link for each charge point;
* the EVSE portal tariff-display endpoint returns the prices shown before
  payment for that exact charge point.

No dynamic connector or station status is requested or published. Third-party
eMSP/roaming prices are not collected.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from electric55_station_base import offers_for_station, render


MAP_SETTINGS_URL = "https://umap.openstreetmap.fr/fr/map/1234362/geojson/"
MAP_LAYER_URL = "https://umap.openstreetmap.fr/fr/datalayer/{map_id}/{layer_id}/"
TARIFF_ENDPOINT = (
    "https://rest.service-evse.com/v1/util/pricing-model/tariff-display/"
    "{charging_station_id}?tenant=e55c&ConnectorID={connector_id}"
)
UA = "Tesla-Charge-Companion-E55C-Builder/1.1 (+public-read-only-tariffs)"
LINK_RE = re.compile(r"href=[\"']([^\"']*https://ev-qr\.com/[^\"']+)[\"']", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def evse_key(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def fetch_bytes(url: str, *, timeout: int = 30) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*;q=0.8",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl()


def fetch_json(url: str, *, timeout: int = 30) -> tuple[dict[str, Any], bytes, str]:
    raw, final_url = fetch_bytes(url, timeout=timeout)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON object expected from {url}")
    return payload, raw, final_url


def _normalized_payment_url(charging_station_id: str, connector_id: int) -> str:
    query = urllib.parse.urlencode(
        {"t": "e55c", "b": charging_station_id, "c": str(connector_id)}
    )
    return f"https://ev-qr.com/?{query}"


def extract_map_links(features: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return exact E55C payment links indexed by case-insensitive EVSE ID."""
    links: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        description = html.unescape(str(properties.get("description") or ""))
        for raw_url in LINK_RE.findall(description):
            parsed = urllib.parse.urlsplit(html.unescape(raw_url))
            query = urllib.parse.parse_qs(parsed.query)
            tenant = (query.get("t") or [""])[0].lower()
            charging_station_id = (query.get("b") or [""])[0].strip()
            connector_raw = (query.get("c") or [""])[0]
            if tenant != "e55c" or not evse_key(charging_station_id).startswith("FR*55C*"):
                continue
            try:
                connector_id = int(connector_raw)
            except (TypeError, ValueError):
                continue
            if connector_id <= 0:
                continue
            key = evse_key(charging_station_id)
            candidate = {
                "chargingStationId": charging_station_id,
                "connectorId": connector_id,
                "paymentUrl": _normalized_payment_url(charging_station_id, connector_id),
                "mapFeatureId": feature.get("id"),
            }
            previous = links.get(key)
            if previous and (
                previous["chargingStationId"] != candidate["chargingStationId"]
                or previous["connectorId"] != candidate["connectorId"]
            ):
                raise RuntimeError(f"conflicting E55C map links for {key}")
            links[key] = candidate
    return links


def load_official_map(settings_url: str = MAP_SETTINGS_URL) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    settings, settings_raw, settings_final_url = fetch_json(settings_url)
    properties = settings.get("properties") or {}
    author = str((properties.get("author") or {}).get("name") or "").strip()
    team = str(((properties.get("permissions") or {}).get("team") or {}).get("name") or "").strip()
    if "e55c" not in {author.lower(), team.lower()}:
        raise RuntimeError(f"uMap is not identified as E55C-owned (author={author!r}, team={team!r})")
    map_id = str(properties.get("id") or "1234362")
    layers = properties.get("datalayers") or []
    if not layers:
        raise RuntimeError("E55C uMap exposes no data layer")

    links: dict[str, dict[str, Any]] = {}
    layer_evidence: list[dict[str, Any]] = []
    for layer in layers:
        layer_id = str(layer.get("id") or "").strip()
        if not layer_id:
            continue
        url = MAP_LAYER_URL.format(map_id=map_id, layer_id=layer_id)
        payload, raw, final_url = fetch_json(url)
        features = payload.get("features") or []
        if not isinstance(features, list):
            raise RuntimeError(f"invalid E55C uMap data layer {layer_id}")
        for key, value in extract_map_links(features).items():
            if key in links and links[key] != value:
                raise RuntimeError(f"duplicate conflicting E55C uMap link for {key}")
            links[key] = value
        layer_evidence.append({
            "id": layer_id,
            "name": (layer.get("properties") or {}).get("name"),
            "url": final_url,
            "featureCount": len(features),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    if not links:
        raise RuntimeError("E55C uMap contains no valid ev-qr.com Scan Pay link")
    evidence = {
        "settingsUrl": settings_final_url,
        "settingsSha256": hashlib.sha256(settings_raw).hexdigest(),
        "mapId": map_id,
        "author": author,
        "team": team,
        "modifiedAt": properties.get("modified_at"),
        "layers": layer_evidence,
        "paymentLinkCount": len(links),
    }
    return links, evidence


def tariff_url(link: dict[str, Any]) -> str:
    identifier = urllib.parse.quote(str(link["chargingStationId"]), safe="*")
    return TARIFF_ENDPOINT.format(
        charging_station_id=identifier,
        connector_id=int(link["connectorId"]),
    )


def fetch_tariff(link: dict[str, Any], *, timeout: int = 30, retries: int = 2) -> dict[str, Any]:
    url = tariff_url(link)
    for attempt in range(retries + 1):
        try:
            payload, _, final_url = fetch_json(url, timeout=timeout)
            return {"ok": True, "payload": payload, "url": final_url}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"ok": False, "httpStatus": 404, "error": "charge_point_not_found", "url": url}
            if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt == retries:
                return {"ok": False, "httpStatus": exc.code, "error": "http_error", "url": url}
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            if attempt == retries:
                return {"ok": False, "error": type(exc).__name__, "url": url}
        time.sleep(0.5 * (2**attempt))
    return {"ok": False, "error": "unknown_fetch_error", "url": url}


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _price_including_tax(dimension: dict[str, Any], *, per_minute: bool = False) -> float:
    price = _decimal(dimension.get("price") or 0)
    vat = _decimal(dimension.get("vat") or 0)
    result = price * (Decimal("1") + vat / Decimal("100"))
    if per_minute:
        result /= Decimal("60")
    return _money(result)


def _rule_from_item(item: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any] | None:
    dimensions = item.get("dimensions") or {}
    restrictions = item.get("restrictions") or {}
    static_restrictions = item.get("staticRestrictions") or {}
    rule: dict[str, Any] = {
        "scope": "timeWindow" if restrictions.get("timeFrom") or restrictions.get("timeTo") else "allDay",
        "start": restrictions.get("timeFrom") or "00:00",
        "end": restrictions.get("timeTo") or "24:00",
        "currency": definition.get("currencyCode") or "EUR",
        "taxIncluded": True,
        "billingDimensions": [],
    }
    field_map = {
        "flatFee": ("flat", "flatEur", False),
        "energy": ("energy", "energyEurPerKwh", False),
        "chargingTime": ("charging_time", "chargingTimeEurPerMinute", True),
        "parkingTime": ("parking_time", "parkingTimeEurPerMinute", True),
    }
    vats: dict[str, float] = {}
    for source_name, (dimension_name, target_name, per_minute) in field_map.items():
        dimension = dimensions.get(source_name)
        if not isinstance(dimension, dict) or dimension.get("active") is not True:
            continue
        rule["billingDimensions"].append(dimension_name)
        rule[target_name] = _price_including_tax(dimension, per_minute=per_minute)
        vats[dimension_name] = float(dimension.get("vat") or 0)
        if dimension.get("stepSize") is not None:
            rule.setdefault("stepSizeByDimension", {})[dimension_name] = dimension.get("stepSize")
        if dimension.get("rounding") is not None:
            rule.setdefault("roundingByDimension", {})[dimension_name] = dimension.get("rounding")
    if not rule["billingDimensions"]:
        return None
    rule["vatPercentByDimension"] = vats
    optional = {
        "daysOfWeek": restrictions.get("daysOfWeek"),
        "minEnergyKWh": restrictions.get("minEnergyKWh"),
        "maxEnergyKWh": restrictions.get("maxEnergyKWh"),
        "minPowerKw": restrictions.get("minPowerKW"),
        "maxPowerKw": restrictions.get("maxPowerKW"),
        "minDurationSeconds": restrictions.get("minDurationSecs"),
        "maxDurationSeconds": restrictions.get("maxDurationSecs"),
        "validFrom": static_restrictions.get("validFrom"),
        "validTo": static_restrictions.get("validTo"),
    }
    for key, value in optional.items():
        if value not in (None, [], ""):
            rule[key] = value
    return rule


def parse_tariff_profile(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize the exact price definitions returned to E55C Scan Pay."""
    definitions = [
        definition
        for definition in payload.get("definitions") or []
        if isinstance(definition, dict) and definition.get("isMatching") is True
    ]
    if not definitions:
        return None
    rules: list[dict[str, Any]] = []
    definition_ids: list[str] = []
    names: list[str] = []
    methods: list[str] = []
    global_scope = True
    for definition in definitions:
        definition_id = str(definition.get("_id") or "").strip()
        if definition_id:
            definition_ids.append(definition_id)
        if definition.get("name"):
            names.append(str(definition["name"]))
        if definition.get("method"):
            methods.append(str(definition["method"]))
        where = definition.get("where") or {}
        who = definition.get("who") or {}
        global_scope = global_scope and where.get("allSiteAreas") is True and who.get("allUsersAndTags") is True
        for item in definition.get("items") or []:
            rule = _rule_from_item(item, definition)
            if rule:
                rule["sourceDefinitionId"] = definition_id or None
                rule["isDiscount"] = bool((definition.get("options") or {}).get("isDiscount"))
                rules.append(rule)
    if not rules:
        return None
    normalized = {
        "displayTextFr": ((payload.get("translations") or {}).get("fr") or None),
        "rules": rules,
    }
    digest = hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "profileId": f"e55c-scanpay-{digest}",
        "channel": "E55C Scan Pay",
        "priceAuthority": "exact public pre-payment tariff display",
        "currency": "EUR",
        "taxIncluded": True,
        "displayTextFr": normalized["displayTextFr"],
        "rules": rules,
        "sourceDefinitionIds": sorted(set(definition_ids)),
        "sourceNames": sorted(set(names)),
        "sourceMethods": sorted(set(methods)),
        "globalScopeEvidence": global_scope,
        "chargingAndParkingDimensionsMustRemainSeparate": any(
            "charging_time" in rule["billingDimensions"] and "parking_time" in rule["billingDimensions"]
            for rule in rules
        ),
    }


def _all_points(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [point for station in payload.get("stations") or [] for point in station.get("chargePoints") or []]


def _previous_state(previous: dict[str, Any] | None) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not previous:
        return {}, {}
    points = {evse_key(point.get("localEvseId")): point for point in _all_points(previous)}
    profiles = {
        str(profile.get("profileId")): profile
        for profile in previous.get("directTariffProfiles") or []
        if profile.get("profileId")
    }
    return points, profiles


def _fetch_many(links: dict[str, dict[str, Any]], keys: Iterable[str], *, workers: int) -> dict[str, dict[str, Any]]:
    wanted = sorted(set(keys))
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        future_to_key = {pool.submit(fetch_tariff, links[key]): key for key in wanted}
        completed = 0
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as exc:  # pragma: no cover - defensive worker boundary
                results[key] = {"ok": False, "error": type(exc).__name__, "url": tariff_url(links[key])}
            completed += 1
            if completed % 100 == 0 or completed == len(wanted):
                print(f"E55C Scan Pay tariffs: {completed}/{len(wanted)} checked", flush=True)
    return results


def enrich(
    payload: dict[str, Any],
    *,
    links: dict[str, dict[str, Any]],
    tariff_results: dict[str, dict[str, Any]],
    map_evidence: dict[str, Any],
    previous: dict[str, Any] | None = None,
    full_refresh: bool = True,
) -> dict[str, Any]:
    previous_points, previous_profiles = _previous_state(previous)
    profiles: dict[str, dict[str, Any]] = {}
    parsed_by_key: dict[str, dict[str, Any] | None] = {}
    failed_keys: set[str] = set()
    for key, result in tariff_results.items():
        if result.get("ok") is True:
            parsed_by_key[key] = parse_tariff_profile(result.get("payload") or {})
        else:
            failed_keys.add(key)

    # During an incremental refresh, one representative per global tariff
    # profile is checked. Its new profile safely updates all EVSEs that shared
    # the previous globally-scoped profile; new EVSEs are always checked exactly.
    profile_replacements: dict[str, dict[str, Any]] = {}
    if not full_refresh:
        for key, parsed in parsed_by_key.items():
            prior = previous_points.get(key) or {}
            old_profile_id = ((prior.get("pricing") or {}).get("profileId"))
            old_profile = previous_profiles.get(str(old_profile_id))
            if parsed and old_profile and old_profile.get("globalScopeEvidence") is True and parsed.get("globalScopeEvidence") is True:
                profile_replacements[str(old_profile_id)] = parsed

    linked_points = 0
    verified_direct_points = 0
    resolved_points = 0
    no_tariff_points = 0
    current_keys: set[str] = set()
    for point in _all_points(payload):
        key = evse_key(point.get("localEvseId"))
        current_keys.add(key)
        link = links.get(key)
        if link:
            linked_points += 1
            point["directAccess"] = {
                "channel": "E55C Scan Pay",
                "available": True,
                "paymentUrl": link["paymentUrl"],
                "chargingStationId": link["chargingStationId"],
                "connectorId": link["connectorId"],
                "source": "e55c_official_public_map",
            }
            failed = tariff_results.get(key) or {}
            if failed.get("ok") is False and failed.get("httpStatus") == 404:
                point["directAccess"]["available"] = False
                point["directAccess"]["reason"] = "charge_point_not_found_in_current_e55c_tariff_endpoint"
            elif failed.get("ok") is False:
                point["directAccess"]["available"] = None
                point["directAccess"]["reason"] = "tariff_endpoint_unavailable_during_refresh"
        else:
            point["directAccess"] = {
                "channel": "E55C Scan Pay",
                "available": False,
                "reason": "no_exact_link_in_current_e55c_public_map",
            }

        profile = parsed_by_key.get(key)
        prior = previous_points.get(key) or {}
        if (
            profile is None
            and not full_refresh
            and key not in parsed_by_key
            and key not in failed_keys
        ):
            old_profile_id = str(((prior.get("pricing") or {}).get("profileId")) or "")
            profile = profile_replacements.get(old_profile_id) or previous_profiles.get(old_profile_id)
        if (
            profile is None
            and key in failed_keys
            and (tariff_results.get(key) or {}).get("httpStatus") != 404
        ):
            old_profile_id = str(((prior.get("pricing") or {}).get("profileId")) or "")
            profile = previous_profiles.get(old_profile_id)

        if profile:
            profiles[profile["profileId"]] = profile
            point["pricing"] = {
                "status": "resolved_e55c_scan_pay",
                "profileId": profile["profileId"],
                "source": "e55c_public_scan_pay_tariff_display",
            }
            resolved_points += 1
        else:
            original_raw = (point.get("pricing") or {}).get("raw")
            point["pricing"] = {
                "status": "missing_direct_tariff",
                "raw": original_raw,
                "source": "e55c_official_irve_static" if original_raw else None,
            }
            no_tariff_points += 1
        if (point.get("directAccess") or {}).get("available") is True:
            verified_direct_points += 1

    for station in payload.get("stations") or []:
        points = station.get("chargePoints") or []
        station["offers"] = offers_for_station(points)
        by_evse = {point["evseId"]: point for point in points}
        for offer in station["offers"]:
            members = [by_evse[evse_id] for evse_id in offer.get("evseIds") or []]
            profile_ids = sorted({
                (member.get("pricing") or {}).get("profileId")
                for member in members
                if (member.get("pricing") or {}).get("profileId")
            })
            direct_count = sum(
                1 for member in members if (member.get("directAccess") or {}).get("available") is True
            )
            offer.pop("pricingRules", None)
            offer.pop("tariffText", None)
            if profile_ids:
                offer["source"] = "e55c_public_scan_pay_tariff_display"
                offer["pricingProfileId"] = profile_ids[0] if len(profile_ids) == 1 else None
            offer["directPaymentAvailable"] = direct_count == len(members)

    total_points = len(_all_points(payload))
    station_count_with_pricing = sum(
        1
        for station in payload.get("stations") or []
        if any(
            (point.get("pricing") or {}).get("status") == "resolved_e55c_scan_pay"
            for point in station.get("chargePoints") or []
        )
    )
    matched_map_keys = {key for key in current_keys if key in links}
    static_priced_points = payload.get("stats", {}).get("chargePointCountWithMachineReadablePricing", 0)
    static_priced_stations = payload.get("stats", {}).get("stationCountWithMachineReadablePricing", 0)
    static_tariff_text_points = payload.get("stats", {}).get("chargePointCountWithTariffText", 0)
    endpoint_not_found = sum(
        1
        for result in tariff_results.values()
        if result.get("ok") is False and result.get("httpStatus") == 404
    )
    payload["schemaVersion"] = "1.1.0"
    payload["directTariffProfiles"] = sorted(profiles.values(), key=lambda item: item["profileId"])
    payload.setdefault("scope", {}).update({
        "directE55cScanPayTariffsIncluded": True,
        "thirdPartyEmspTariffsIncluded": False,
        "dynamicStatusIncluded": False,
    })
    checked_at = now_iso()
    previous_direct_source = (((previous or {}).get("source") or {}).get("directTariff") or {})
    last_full_refresh_at = (
        checked_at
        if full_refresh
        else previous_direct_source.get("lastFullRefreshAt")
        or (previous_direct_source.get("checkedAt") if previous_direct_source.get("fullRefresh") is True else None)
    )
    payload.setdefault("source", {})["directTariff"] = {
        "checkedAt": checked_at,
        "lastFullRefreshAt": last_full_refresh_at,
        "map": map_evidence,
        "tariffEndpointTemplate": TARIFF_ENDPOINT,
        "tariffEndpointMode": "public_read_only_exact_charge_point",
        "fullRefresh": full_refresh,
        "dynamicStatusRequested": False,
    }
    payload.setdefault("stats", {}).update({
        "stationCountWithStaticIrveMachineReadablePricing": static_priced_stations,
        "chargePointCountWithStaticIrveMachineReadablePricing": static_priced_points,
        "chargePointCountWithStaticIrveTariffText": static_tariff_text_points,
        "stationCountWithMachineReadablePricing": station_count_with_pricing,
        "chargePointCountWithDirectPaymentLink": linked_points,
        "chargePointCountWithVerifiedDirectPayment": verified_direct_points,
        "chargePointCountWithMachineReadablePricing": resolved_points,
        "chargePointCountWithTariffText": resolved_points,
        "chargePointCountWithoutResolvedDirectTariff": no_tariff_points,
        "directTariffCoverageRatio": round(resolved_points / total_points, 6) if total_points else 0,
        "directTariffProfileCount": len(profiles),
        "e55cMapPaymentLinkCount": len(links),
        "e55cMapLinksMatchedToStaticInventory": len(matched_map_keys),
        "e55cMapLinksOutsideCurrentStaticInventory": len(set(links) - current_keys),
        "directTariffFetchFailureCount": len(failed_keys),
        "directTariffEndpointNotFoundCount": endpoint_not_found,
    })
    payload.setdefault("tccIntegration", {}).update({
        "operatorDirectTariffsReady": resolved_points > 0,
        "directPaymentUrlsReady": linked_points > 0,
        "chargingAndParkingTariffDimensionsSeparated": True,
        "directTariffProfileJoin": "offer.pricingProfileId -> directTariffProfiles.profileId",
        "thirdPartyEmspTariffsMustRemainSeparate": True,
        "statusMustBeJoinedExternally": True,
    })
    return payload


def select_incremental_keys(
    payload: dict[str, Any],
    links: dict[str, dict[str, Any]],
    previous: dict[str, Any] | None,
) -> set[str]:
    current = {evse_key(point.get("localEvseId")) for point in _all_points(payload)} & set(links)
    previous_points, previous_profiles = _previous_state(previous)
    if not previous_points or not previous_profiles:
        return current
    keys: set[str] = {key for key in current if not (previous_points.get(key) or {}).get("pricing", {}).get("profileId")}
    representatives: dict[str, str] = {}
    for key in sorted(current):
        profile_id = str(((previous_points.get(key) or {}).get("pricing") or {}).get("profileId") or "")
        if profile_id and previous_profiles.get(profile_id, {}).get("globalScopeEvidence") is True:
            representatives.setdefault(profile_id, key)
        elif profile_id:
            keys.add(key)
    keys.update(representatives.values())
    return keys


def write_summary(payload: dict[str, Any], path: Path) -> None:
    stats = payload["stats"]
    text = (
        "# Base nationale E55C pour TCC\n\n"
        f"- Stations exploitées par E55C : **{stats['stationCount']}**\n"
        f"- Points de charge uniques : **{stats['chargePointCount']}**\n"
        f"- Points avec lien de paiement direct E55C : **{stats['chargePointCountWithDirectPaymentLink']}**\n"
        f"- Points de paiement confirmés par le tarif E55C : **{stats['chargePointCountWithVerifiedDirectPayment']}**\n"
        f"- Points avec tarif Scan Pay structuré : **{stats['chargePointCountWithMachineReadablePricing']}** "
        f"({stats['directTariffCoverageRatio']:.2%})\n"
        f"- Profils tarifaires directs distincts : **{stats['directTariffProfileCount']}**\n"
        f"- Lignes source hors CPO E55C exclues : **{stats['excludedNonE55cOperatorRows']}**\n"
        "- Statuts dynamiques : **non inclus** (jointure TCC via Electroverse/Electra).\n"
        "- Tarifs eMSP tiers / itinérance : **non inclus**.\n"
        f"- Empreinte IRVE statique : `{payload['source']['sha256']}`\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--map-settings-url", default=MAP_SETTINGS_URL)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--full-refresh", action="store_true")
    parser.add_argument("--min-coverage", type=float, default=0.95)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    previous = None
    if args.previous and args.previous.exists():
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
    links, map_evidence = load_official_map(args.map_settings_url)
    full_refresh = args.full_refresh or not (previous or {}).get("directTariffProfiles")
    if full_refresh:
        keys = {evse_key(point.get("localEvseId")) for point in _all_points(payload)} & set(links)
    else:
        keys = select_incremental_keys(payload, links, previous)
    print(
        f"E55C direct enrichment: {len(keys)} tariff endpoints to check "
        f"({'full' if full_refresh else 'incremental'} refresh)",
        flush=True,
    )
    results = _fetch_many(links, keys, workers=args.workers)
    enriched = enrich(
        payload,
        links=links,
        tariff_results=results,
        map_evidence=map_evidence,
        previous=previous,
        full_refresh=full_refresh,
    )
    coverage = enriched["stats"]["directTariffCoverageRatio"]
    if coverage < args.min_coverage:
        raise RuntimeError(f"E55C direct tariff coverage {coverage:.2%} < required {args.min_coverage:.2%}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(enriched), encoding="utf-8")
    if args.report:
        write_summary(enriched, args.report)
    print(
        f"E55C direct enrichment complete: {enriched['stats']['chargePointCountWithMachineReadablePricing']} "
        f"of {enriched['stats']['chargePointCount']} charge points resolved",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
