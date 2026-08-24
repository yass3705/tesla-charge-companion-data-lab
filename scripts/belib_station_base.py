#!/usr/bin/env python3
"""Build the strict Belib'-operated Paris station base used by TCC V8.

The official Paris Open Data static IRVE export is the sole inventory source.
A row is retained only when both the legal operator and the Belib' network brand
match their dedicated schema fields.  Roaming-only stations, fictitious rows,
motorcycle points and connectors incompatible with a European Tesla are
excluded.  Parking prices are deliberately absent from the generated payload.

Live availability is not embedded: TCC reads the official dynamic Paris Open
Data endpoint at runtime and joins it with ``id_pdc_local``.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


STATIC_EXPORT_URL = (
    "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
    "belib-points-de-recharge-pour-vehicules-electriques-donnees-statiques/exports/json"
)
LIVE_EXPORT_URL = (
    "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
    "belib-points-de-recharge-pour-vehicules-electriques-disponibilite-temps-reel/exports/json"
)
CANONICAL_OPERATOR = "TOTALENERGIES"
CANONICAL_BRAND = "Belib'"
CANONICAL_DISPLAY = "Belib'"
UA = "Tesla-Charge-Companion-Belib-Builder/1.0 (+official-public-data-only)"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("’", "'").lower()


def parse_bool(value: Any) -> bool:
    return normalize(value) in {"true", "1", "oui", "yes", "vrai"}


def parse_number(value: Any) -> float | None:
    match = re.search(r"-?\d+(?:[.,]\d+)?", clean(value))
    if not match:
        return None
    number = float(match.group(0).replace(",", "."))
    return number if number == number else None


def coordinates(row: dict[str, Any]) -> tuple[float, float] | None:
    value = row.get("coordonneesxy")
    if isinstance(value, dict):
        lat, lon = parse_number(value.get("lat")), parse_number(value.get("lon"))
    else:
        numbers = re.findall(r"-?\d+(?:[.,]\d+)?", clean(value))
        if len(numbers) < 2:
            return None
        lon = float(numbers[0].replace(",", "."))
        lat = float(numbers[1].replace(",", "."))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 7), round(lon, 7)


def is_strict_belib(row: dict[str, Any]) -> bool:
    return (
        clean(row.get("nom_operateur")).upper() == CANONICAL_OPERATOR
        and normalize(row.get("nom_enseigne")) == normalize(CANONICAL_BRAND)
    )


def tesla_connector_kinds(row: dict[str, Any]) -> list[tuple[str, str]]:
    """Return the TCC kind / connector pairs usable by a European Tesla."""
    if parse_bool(row.get("station_deux_roues")):
        return []
    kinds: list[tuple[str, str]] = []
    if parse_bool(row.get("prise_type_2")):
        kinds.append(("AC", "TYPE_2"))
    if parse_bool(row.get("prise_type_combo_ccs")):
        kinds.append(("DC", "CCS"))
    return kinds


def service_class(power_kw: float) -> str:
    if power_kw <= 7.5:
        return "flex"
    if power_kw < 43:
        return "boost"
    return "boostPlus"


def per_minute(amount: float, minutes: float = 1.0) -> float:
    return round(float(amount) / float(minutes), 9)


def tariff_profiles(tariffs: dict[str, Any]) -> list[dict[str, Any]]:
    if tariffs.get("dataset") != "belib-official-paris":
        raise ValueError("unexpected Belib tariff dataset")
    visitor = tariffs.get("visitor") or {}
    subscriptions = tariffs.get("subscriptions") or {}
    non_resident = subscriptions.get("nonResident") or {}
    resident = subscriptions.get("residentParis") or {}
    long_fee = ((tariffs.get("fees") or {}).get("longConnection") or {})
    threshold = round(float(long_fee.get("thresholdHours") or 14) * 60)
    long_rate = per_minute(float(long_fee.get("eurPerHourAfterThreshold") or 10), 60)

    def rule(
        *,
        scope: str = "allDay",
        start: str = "00:00",
        end: str = "24:00",
        energy: float = 0.0,
        connected: float = 0.0,
        charge: float = 0.0,
        idle: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "scope": scope,
            "start": start,
            "end": end,
            "currency": "EUR",
            "energyEurPerKwh": round(float(energy), 9),
            "connectedTimeEurPerMinute": round(float(connected), 9),
            "chargeTimeEurPerMinute": round(float(charge), 9),
            "idleTimeEurPerMinute": round(float(idle), 9),
            "longConnectionThresholdMinutes": threshold,
            "longConnectionEurPerMinute": long_rate,
        }

    def profile(
        plan: str,
        plan_label: str,
        subscription_id: str | None,
        annual_fee: float,
        klass: str,
        rules: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "profileId": f"belib-{plan}-{klass}",
            "channel": "Belib direct",
            "customerPlan": plan,
            "customerPlanLabelFr": plan_label,
            "subscriptionId": subscription_id,
            "annualFeeEur": annual_fee,
            "serviceClass": klass,
            "parkingFeesIncluded": False,
            "reservationFeesIncluded": False,
            "taxIncluded": True,
            "rules": rules,
        }

    annual = float(subscriptions.get("annualFeeEur") or 7)
    result: list[dict[str, Any]] = []

    for plan, label, selection, fee, data in (
        ("visitor", "Visiteur", None, 0.0, visitor),
        ("nonresident", "Abonne non-resident", "belib-nonresident", annual, non_resident),
    ):
        flex = data.get("flex") or {}
        boost = data.get("boost") or {}
        boost_plus = data.get("boostPlus") or {}
        result.extend([
            profile(
                plan, label, selection, fee, "flex",
                [rule(
                    energy=float(flex.get("eurPerKwh") or 0),
                    connected=per_minute(float(flex.get("eurPer15MinConnected") or 0), 15),
                )],
            ),
            profile(
                plan, label, selection, fee, "boost",
                [rule(
                    charge=per_minute(float(boost.get("eurPer15MinConnected") or 0), 15),
                    idle=per_minute(float(boost.get("eurPer15MinConnected") or 0), 15),
                )],
            ),
            profile(
                plan, label, selection, fee, "boostPlus",
                [rule(
                    charge=float(boost_plus.get("eurPerMinuteConnected") or 0),
                    idle=float(boost_plus.get("eurPerMinuteConnected") or 0),
                )],
            ),
        ])

    resident_day = resident.get("day") or {}
    resident_peak = resident.get("night2000To2300") or {}
    resident_offpeak = resident.get("night2300To0800") or {}
    result.append(profile(
        "resident", "Abonne resident Paris", "belib-resident", annual, "flex",
        [
            rule(
                scope="timeWindow", start="08:00", end="20:00",
                energy=float((resident_day.get("flex") or {}).get("eurPerKwh") or 0),
                connected=per_minute(float((resident_day.get("flex") or {}).get("eurPer15MinConnected") or 0), 15),
            ),
            rule(
                scope="timeWindow", start="20:00", end="23:00",
                energy=float((resident_peak.get("flex") or {}).get("eurPerKwh") or 0),
            ),
            rule(
                scope="timeWindow", start="23:00", end="08:00",
                energy=float((resident_offpeak.get("flex") or {}).get("eurPerKwh") or 0),
            ),
        ],
    ))
    for klass, key, unit in (
        ("boost", "boost", "eurPer15MinConnected"),
        ("boostPlus", "boostPlus", "eurPerMinuteConnected"),
    ):
        item = resident_day.get(key) or {}
        rate = float(item.get(unit) or 0)
        if unit == "eurPer15MinConnected":
            rate = per_minute(rate, 15)
        result.append(profile(
            "resident", "Abonne resident Paris", "belib-resident", annual, klass,
            [rule(charge=rate, idle=rate)],
        ))

    for item in result:
        if not item["rules"]:
            raise ValueError(f"empty Belib profile {item['profileId']}")
        if "parking" in json.dumps(item, ensure_ascii=False).lower():
            # Only the explicit false guard is allowed, no monetary parking dimension.
            if set(k for k in item if "parking" in k.lower()) != {"parkingFeesIncluded"}:
                raise ValueError(f"parking dimension leaked into {item['profileId']}")
    return sorted(result, key=lambda item: item["profileId"])


def build(
    rows: Iterable[dict[str, Any]],
    tariffs: dict[str, Any],
    *,
    source: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    source_rows = list(rows)
    strict_rows = [row for row in source_rows if is_strict_belib(row)]
    missing_identifiers = [
        row for row in strict_rows
        if not clean(row.get("id_station_local")) or not clean(row.get("id_pdc_local"))
    ]
    identified = [row for row in strict_rows if row not in missing_identifiers]
    motorcycle = [row for row in identified if parse_bool(row.get("station_deux_roues"))]
    incompatible = [
        row for row in identified
        if row not in motorcycle and not tesla_connector_kinds(row)
    ]
    compatible = [
        row for row in identified
        if row not in motorcycle and row not in incompatible and tesla_connector_kinds(row)
    ]

    stations: dict[str, dict[str, Any]] = {}
    groups: dict[str, dict[tuple[str, float, str], set[str]]] = defaultdict(lambda: defaultdict(set))
    group_connectors: dict[str, dict[tuple[str, float, str], set[str]]] = defaultdict(lambda: defaultdict(set))
    point_meta: dict[str, dict[str, Any]] = {}

    for row in compatible:
        station_id = clean(row.get("id_station_local"))
        evse_id = clean(row.get("id_pdc_local"))
        coords = coordinates(row)
        power = parse_number(row.get("puissance_nominale"))
        if coords is None or power is None or power <= 0:
            continue
        if station_id not in stations:
            address = clean(row.get("adresse_station"))
            postal_match = re.search(r"\b(\d{5})\b", address)
            postal = postal_match.group(1) if postal_match else ""
            city = clean(address[postal_match.end():]) if postal_match else "Paris"
            stations[station_id] = {
                "stationId": station_id,
                "roamingStationId": clean(row.get("id_station_itinerance")),
                "name": clean(row.get("nom_station")) or f"Station Belib {station_id}",
                "address": address,
                "postalCode": postal,
                "city": city or "Paris",
                "coordinates": {"latitude": coords[0], "longitude": coords[1]},
                "operator": CANONICAL_DISPLAY,
                "operatorSourceValue": CANONICAL_OPERATOR,
                "brandSourceValue": CANONICAL_BRAND,
                "access": {
                    "hours": clean(row.get("horaires")) or "24/7",
                    "condition": clean(row.get("condition_acces")) or "Acces libre",
                },
                "payment": {
                    "card": parse_bool(row.get("paiement_cb")),
                    "adHoc": parse_bool(row.get("paiement_acte")),
                    "other": parse_bool(row.get("paiement_autre")),
                },
                "lastUpdated": clean(row.get("date_maj")),
            }
        point_meta[evse_id] = {
            "evseId": evse_id,
            "roamingEvseId": clean(row.get("id_pdc_itinerance")),
        }
        klass = service_class(power)
        for kind, connector in tesla_connector_kinds(row):
            key = (kind, round(power, 3), klass)
            groups[station_id][key].add(evse_id)
            group_connectors[station_id][key].add(connector)

    output_stations: list[dict[str, Any]] = []
    all_evses: set[str] = set()
    configuration_evse_links = 0
    for station_id in sorted(stations):
        base = stations[station_id]
        configurations: list[dict[str, Any]] = []
        station_evses: set[str] = set()
        connectors: set[str] = set()
        for (kind, power, klass), evses in sorted(groups[station_id].items()):
            ids = sorted(evses)
            station_evses.update(ids)
            all_evses.update(ids)
            connector_values = sorted(group_connectors[station_id][(kind, power, klass)])
            connectors.update(connector_values)
            configuration_evse_links += len(ids)
            configurations.append({
                "kind": kind,
                "powerKw": power,
                "serviceClass": klass,
                "stalls": len(ids),
                "connectorTypes": connector_values,
                "evseIds": ids,
                "roamingEvseIds": sorted(
                    point_meta[evse]["roamingEvseId"]
                    for evse in ids if point_meta[evse]["roamingEvseId"]
                ),
            })
        if not configurations:
            continue
        output_stations.append({
            **base,
            "chargePointCount": len(station_evses),
            "maxPowerKw": max(config["powerKw"] for config in configurations),
            "connectorTypes": sorted(connectors),
            "configurations": configurations,
        })

    profiles = tariff_profiles(tariffs)
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "belib-operated-stations-paris",
        "generatedAt": generated_at or now_iso(),
        "operator": CANONICAL_DISPLAY,
        "country": "FR",
        "city": "Paris",
        "source": source or {"url": STATIC_EXPORT_URL},
        "scope": {
            "strictOperatorField": "nom_operateur",
            "strictOperatorValue": CANONICAL_OPERATOR,
            "strictBrandField": "nom_enseigne",
            "strictBrandValue": CANONICAL_BRAND,
            "thirdPartyRoamingStationsExcluded": True,
            "missingIdentifierRowsExcluded": True,
            "motorcycleOnlyPointsExcluded": True,
            "teslaCompatibleConnectorsOnly": True,
            "parkingFeesIncluded": False,
            "reservationFeesIncluded": False,
            "dynamicStatusIncluded": False,
            "liveStatusRuntimeSource": LIVE_EXPORT_URL,
        },
        "stats": {
            "sourceRowCount": len(source_rows),
            "strictOperatorBrandRowCount": len(strict_rows),
            "excludedNonBelibRows": len(source_rows) - len(strict_rows),
            "excludedMissingIdentifierRows": len(missing_identifiers),
            "excludedMotorcycleRows": len(motorcycle),
            "excludedTeslaIncompatibleRows": len(incompatible),
            "stationCount": len(output_stations),
            "chargePointCount": len(all_evses),
            "configurationEvseLinkCount": configuration_evse_links,
            "tariffProfileCount": len(profiles),
        },
        "directTariffProfiles": profiles,
        "stations": output_stations,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if "parkingper" in serialized.lower() or "parkingcost" in serialized.lower():
        raise ValueError("parking cost leaked into Belib station base")
    return payload


def fetch_json(url: str) -> tuple[Any, bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
        if normalize(response.headers.get("Content-Encoding")) == "gzip":
            raw = gzip.decompress(raw)
        final_url = response.geturl()
    return json.loads(raw.decode("utf-8")), raw, final_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tariffs", default="data/operator_direct/belib_official_paris.json")
    parser.add_argument("--input", help="Optional local static export for deterministic tests")
    parser.add_argument("--out", default="data/national/belib_stations_paris.json")
    parser.add_argument("--report", default="reports/belib/station_base_summary.md")
    args = parser.parse_args()

    if args.input:
        raw = Path(args.input).read_bytes()
        rows = json.loads(raw.decode("utf-8"))
        final_url = str(Path(args.input))
    else:
        rows, raw, final_url = fetch_json(STATIC_EXPORT_URL)
    if not isinstance(rows, list):
        raise SystemExit("Belib static export is not a JSON array")
    tariffs = json.loads(Path(args.tariffs).read_text(encoding="utf-8"))
    payload = build(
        rows,
        tariffs,
        source={
            "url": final_url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "officialParisOpenData": True,
        },
    )

    out = Path(args.out)
    report = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats = payload["stats"]
    summary = (
        "# Base Belib directe pour TCC V8\n\n"
        f"- Stations strictement Belib / TotalEnergies : **{stats['stationCount']}**\n"
        f"- Points Tesla-compatibles : **{stats['chargePointCount']}**\n"
        f"- Profils tarifaires directs : **{stats['tariffProfileCount']}**\n"
        f"- Lignes fictives sans identifiant exclues : **{stats['excludedMissingIdentifierRows']}**\n"
        f"- Points moto exclus : **{stats['excludedMotorcycleRows']}**\n"
        f"- Points sans Type 2/CCS exclus : **{stats['excludedTeslaIncompatibleRows']}**\n"
        "- Frais de parking intégrés : **non**\n"
        f"- Statut dynamique : **joint à l’exécution depuis {LIVE_EXPORT_URL}**\n"
    )
    report.write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
