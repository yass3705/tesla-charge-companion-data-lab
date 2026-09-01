#!/usr/bin/env python3
"""Build the exact-EVSE Neogy and Alperia EasyCharge Italy V9 candidate.

The upstream Italy consolidation supplies the physical PUN inventory.  This
builder applies only tariff distinctions explicitly supported by first-party
Neogy and Alperia pages:

* direct payment is split by South Tyrol, current type and the documented
  Fast/Hyper boundary evidence;
* 43 kW AC is deliberately not assigned a direct Quick price;
* EasyCharge Light and Plus remain separate, opt-in subscription products;
* all offers retain the published 60-minute post-charge grace period.

No price is inferred for non-Neogy roaming partners.
"""
from __future__ import annotations

import argparse
import gzip
import html as html_lib
import json
import math
import re
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


DIRECT_URL = "https://www.neogy.it/en/public-network-charging/direct-payment.html"
STATIONS_URL = "https://www.neogy.it/en/public-charging-stations.html"
EASYCHARGE_URL = "https://www.alperia.eu/de/easycharge/"
HYPER_100_URL = (
    "https://www.alperiagroup.eu/it/"
    "auto-elettriche-33-nuove-stazioni-di-ricarica-veloce-alto-adige"
)
HYPER_400_URL = (
    "https://www.alperiagroup.eu/it/"
    "neogy-centro-di-ricarica-allavanguardia-presso-fiera-bolzano"
)
USER_AGENT = "tesla-charge-companion-data-lab/neogy-alperia-italy-v9"
OPERATOR = "NEOGY SRL"
ALLOWED_EVSE_PARTIES = {"ASM", "CGR", "ECO", "GAU", "SCA"}
SOUTH_TYROL_PROVINCES = {"bolzano", "bozen"}
QUICK_MAX_POWER_KW = 22.2
HYPER_MIN_POWER_KW = 100.0
PLUS_VALID_FROM = "2025-03-01"
PLUS_VALID_THROUGH = "2027-02-28"
ACTIVATION_FEE_EUR = 25.0


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("expected object Italy consolidation payload")
    return value


def save_gz(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP {response.status} for {url}")
        return response.read().decode("utf-8", errors="replace")


def read_text(path: str | None, url: str) -> str:
    return Path(path).read_text(encoding="utf-8") if path else fetch_text(url)


def visible_text(raw: str) -> str:
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    without_styles = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_scripts, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", without_styles)
    return " ".join(html_lib.unescape(without_tags).replace("\xa0", " ").split())


def normalized_text(raw: str) -> str:
    value = unicodedata.normalize("NFKD", visible_text(raw)).encode("ascii", "ignore").decode("ascii")
    return " ".join(value.casefold().replace(",", ".").split())


def require_patterns(label: str, raw: str, patterns: tuple[str, ...]) -> None:
    text = normalized_text(raw)
    missing = [pattern for pattern in patterns if re.search(pattern, text) is None]
    if missing:
        raise RuntimeError(f"official {label} source changed; missing patterns {missing}")


def validate_sources(
    direct_html: str,
    stations_html: str,
    easycharge_html: str,
    hyper_100_html: str,
    hyper_400_html: str,
) -> None:
    require_patterns(
        "Neogy direct tariff",
        direct_html,
        (
            r"italy excluding south tyrol",
            r"neogy quick.{0,80}alternating current.{0,80}0\.67\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"neogy fast.{0,80}direct current.{0,80}0\.79\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"neogy hyper.{0,80}direct current.{0,80}0\.98\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"south tyrol",
            r"neogy quick.{0,80}alternating current.{0,80}0\.45\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"neogy fast and hyper.{0,80}direct current.{0,80}0\.55\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"no fixed costs",
            r"credit card",
        ),
    )
    require_patterns(
        "Neogy post-charge tariff",
        stations_html,
        (
            r"more than 60 minutes after the end of charging",
            r"alternating current \(ac\).{0,80}maximum power of 22 kw.{0,40}0\.08\s*/?\s*min",
            r"7 a\.m\. to 11 p\.m\.",
            r"maximum power of 43 kw and all direct current \(dc\) stations.{0,40}0\.15\s*/?\s*min",
            r"24 hours a day",
        ),
    )
    require_patterns(
        "Alperia EasyCharge",
        easycharge_html,
        (
            r"easycharge plus",
            r"0\.35\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"0\.79\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"aktivierungskosten.{0,20}25",
            r"01\.03\.2025.{0,40}28\.02\.2027",
            r"cronenergy",
            r"easycharge light",
            r"0\.45\s*(?:eur|euro|€)?\s*/?\s*kwh",
            r"0\.55\s*(?:eur|euro|€)?\s*/?\s*kwh",
        ),
    )
    require_patterns(
        "Alperia 100 kW Hypercharger evidence",
        hyper_100_html,
        (r"hypercharger", r"100 kw.{0,30}150 kw"),
    )
    require_patterns(
        "Alperia 400 kW Hypercharger evidence",
        hyper_400_html,
        (r"hypercharger.{0,80}400 kw",),
    )


def key_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return normalized.encode("ascii", "ignore").decode("ascii").strip().casefold()


def connector_kind(evse: dict[str, Any]) -> str:
    kinds: set[str] = set()
    for connector in evse.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        power_type = str(connector.get("powerType") or "").upper()
        if power_type.startswith("AC"):
            kinds.add("AC")
        elif power_type.startswith("DC"):
            kinds.add("DC")
    if len(kinds) != 1:
        raise RuntimeError(f"unresolved or mixed connector current for {evse.get('evseId')}: {sorted(kinds)}")
    return next(iter(kinds))


def max_power_kw(evse: dict[str, Any]) -> float:
    candidates: list[float] = []
    for raw in [evse.get("maxPowerKw"), *[(connector or {}).get("maxPowerKw") for connector in evse.get("connectors") or []]]:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            candidates.append(value)
    if not candidates:
        raise RuntimeError(f"missing positive power for {evse.get('evseId')}")
    return max(candidates)


def post_charge_policy(kind: str, power_kw: float) -> dict[str, Any]:
    if kind == "AC" and power_kw <= QUICK_MAX_POWER_KW:
        return {
            "graceMinutes": 60,
            "eurPerMinute": 0.08,
            "trigger": "once_vehicle_is_charged",
            "billableLocalWindow": {"start": "07:00", "end": "23:00"},
            "exemptLocalWindows": [{"start": "23:00", "end": "07:00"}],
            "source": STATIONS_URL,
        }
    return {
        "graceMinutes": 60,
        "eurPerMinute": 0.15,
        "trigger": "once_vehicle_is_charged",
        "billableLocalWindow": {"start": "00:00", "end": "24:00"},
        "exemptLocalWindows": [],
        "source": STATIONS_URL,
    }


def direct_tariff(south_tyrol: bool, kind: str, power_kw: float) -> tuple[str, dict[str, Any] | None, str | None]:
    if kind == "AC" and power_kw > QUICK_MAX_POWER_KW:
        return "AC_43_UNRESOLVED", None, "direct_quick_scope_does_not_explicitly_cover_ac_above_22kw"
    if south_tyrol and kind == "AC":
        tariff_class, rate = "SOUTH_TYROL_QUICK", 0.45
    elif south_tyrol and kind == "DC":
        tariff_class, rate = "SOUTH_TYROL_DC", 0.55
    elif kind == "AC":
        tariff_class, rate = "OTHER_ITALY_QUICK", 0.67
    elif power_kw < HYPER_MIN_POWER_KW:
        tariff_class, rate = "OTHER_ITALY_FAST", 0.79
    else:
        tariff_class, rate = "OTHER_ITALY_HYPER", 0.98
    return tariff_class, {
        "pricingType": "flat",
        "energyEurPerKwh": rate,
        "currency": "EUR",
        "paymentMethod": "qr_credit_card",
        "rankable": True,
        "source": DIRECT_URL,
    }, None


def light_tariff(south_tyrol: bool, kind: str) -> dict[str, Any]:
    if south_tyrol:
        rate = 0.45 if kind == "AC" else 0.55
        tariff_class = f"SOUTH_TYROL_{kind}"
    else:
        rate = 0.79
        tariff_class = "NEOGY_OUTSIDE_SOUTH_TYROL"
    return {
        "selectionId": "alperia_easycharge_light",
        "energyEurPerKwh": rate,
        "currency": "EUR",
        "tariffClass": tariff_class,
        "activationFeeEur": ACTIVATION_FEE_EUR,
        "rankableWhenSelected": True,
        "source": EASYCHARGE_URL,
    }


def plus_tariff() -> dict[str, Any]:
    return {
        "selectionId": "alperia_easycharge_plus",
        "energyEurPerKwh": 0.35,
        "currency": "EUR",
        "validFrom": PLUS_VALID_FROM,
        "validThrough": PLUS_VALID_THROUGH,
        "activationFeeEur": ACTIVATION_FEE_EUR,
        "requiresAlperiaCronEnergyOrBenElectricityCustomer": True,
        "rankableWhenSelected": True,
        "source": EASYCHARGE_URL,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consolidated", required=True)
    parser.add_argument("--out", default="data/national/neogy_alperia_italy_v9_candidate.json.gz")
    parser.add_argument("--report", default="data/reports/neogy_alperia_italy_v9_report.json")
    parser.add_argument("--direct-html")
    parser.add_argument("--stations-html")
    parser.add_argument("--easycharge-html")
    parser.add_argument("--hyper-100-html")
    parser.add_argument("--hyper-400-html")
    args = parser.parse_args()

    validate_sources(
        read_text(args.direct_html, DIRECT_URL),
        read_text(args.stations_html, STATIONS_URL),
        read_text(args.easycharge_html, EASYCHARGE_URL),
        read_text(args.hyper_100_html, HYPER_100_URL),
        read_text(args.hyper_400_html, HYPER_400_URL),
    )

    consolidated = load_gz(Path(args.consolidated))
    if consolidated.get("country") != "IT" or consolidated.get("backbone") != "GSE PUN":
        raise RuntimeError("unexpected Italy consolidation identity")
    stations = [
        station
        for station in consolidated.get("stations") or []
        if isinstance(station, dict) and key_text(station.get("operator")) == key_text(OPERATOR)
    ]
    entries: list[dict[str, Any]] = []
    direct_classes: Counter[str] = Counter()
    blocked_reasons: Counter[str] = Counter()
    geography_counts: Counter[str] = Counter()
    connector_counts: Counter[str] = Counter()
    party_counts: Counter[str] = Counter()

    for station in stations:
        station_id = str(station.get("stationId") or "").strip()
        if not station_id:
            raise RuntimeError("Neogy station without stationId")
        province = str(station.get("province") or "").strip()
        south_tyrol = key_text(province) in SOUTH_TYROL_PROVINCES
        geography = "south_tyrol" if south_tyrol else "other_italy"
        for evse in station.get("evses") or []:
            if not isinstance(evse, dict):
                raise RuntimeError(f"invalid EVSE row under {station_id}")
            evse_id = str(evse.get("evseId") or "").strip()
            match = re.match(r"^IT\*([A-Z0-9]{3})\*E", evse_id)
            if not match or match.group(1) not in ALLOWED_EVSE_PARTIES:
                raise RuntimeError(f"unexpected Neogy EVSE identity {evse_id!r}")
            kind = connector_kind(evse)
            power_kw = max_power_kw(evse)
            tariff_class, direct, blocking_reason = direct_tariff(south_tyrol, kind, power_kw)
            post_charge = post_charge_policy(kind, power_kw)
            direct_classes[tariff_class] += 1
            geography_counts[geography] += 1
            connector_counts[f"{geography}:{kind}"] += 1
            party_counts[match.group(1)] += 1
            if blocking_reason:
                blocked_reasons[blocking_reason] += 1
            entries.append(
                {
                    "evseId": evse_id,
                    "stationId": station_id,
                    "operator": OPERATOR,
                    "evsePartyPrefix": match.group(1),
                    "stationPartyId": station.get("partyId"),
                    "stationName": station.get("name"),
                    "address": station.get("address"),
                    "city": station.get("city"),
                    "postalCode": station.get("postalCode"),
                    "region": station.get("region"),
                    "province": province,
                    "geography": geography,
                    "connectorKind": kind,
                    "maxPowerKw": round(power_kw, 6),
                    "sourceStatus": evse.get("sourceStatus"),
                    "operationalState": evse.get("operationalState"),
                    "tariffClass": tariff_class,
                    "rankableDirectTariff": direct is not None,
                    "directTariff": direct,
                    "directBlockingReason": blocking_reason,
                    "easyChargeLight": light_tariff(south_tyrol, kind),
                    "easyChargePlus": plus_tariff(),
                    "postChargePolicy": post_charge,
                }
            )

    entries.sort(key=lambda row: row["evseId"])
    evse_ids = [row["evseId"] for row in entries]
    direct_count = sum(row["rankableDirectTariff"] is True for row in entries)
    expected_classes = {
        "AC_43_UNRESOLVED": 26,
        "OTHER_ITALY_FAST": 85,
        "OTHER_ITALY_HYPER": 20,
        "OTHER_ITALY_QUICK": 789,
        "SOUTH_TYROL_DC": 241,
        "SOUTH_TYROL_QUICK": 402,
    }
    counts = {
        "punStations": int((consolidated.get("counts") or {}).get("punStationCount") or 0),
        "punEvse": int((consolidated.get("counts") or {}).get("punEvseCount") or 0),
        "neogyStations": len(stations),
        "neogyEvse": len(entries),
        "rankableDirectEvse": direct_count,
        "unresolvedDirectEvse": len(entries) - direct_count,
        "easyChargeLightExactEvse": len(entries),
        "easyChargePlusExactEvse": len(entries),
        "geographyCounts": dict(sorted(geography_counts.items())),
        "connectorCounts": dict(sorted(connector_counts.items())),
        "directClassCounts": dict(sorted(direct_classes.items())),
        "directBlockedReasons": dict(sorted(blocked_reasons.items())),
        "evsePartyPrefixCounts": dict(sorted(party_counts.items())),
    }
    gates = {
        "officialSourcesValidated": True,
        "punSnapshotExact": counts["punStations"] == 29696 and counts["punEvse"] == 75025,
        "neogyInventoryExact": len(stations) == 724 and len(entries) == 1563,
        "neogyIdentityUnique": len(evse_ids) == len(set(evse_ids)) == 1563,
        "expectedPartyPrefixesExact": dict(sorted(party_counts.items()))
        == {"ASM": 1343, "CGR": 56, "ECO": 38, "GAU": 108, "SCA": 18},
        "geographyExact": dict(geography_counts) == {"other_italy": 901, "south_tyrol": 662},
        "connectorClassesExact": dict(connector_counts)
        == {"other_italy:AC": 796, "other_italy:DC": 105, "south_tyrol:AC": 421, "south_tyrol:DC": 241},
        "directClassesExact": dict(direct_classes) == expected_classes,
        "directScopeExact": direct_count == 1537 and len(entries) - direct_count == 26,
        "ac43DirectFailsClosed": all(
            row["directTariff"] is None and row["directBlockingReason"]
            for row in entries
            if row["tariffClass"] == "AC_43_UNRESOLVED"
        ),
        "subscriptionsExactEvseOnly": all(
            row["easyChargeLight"]["rankableWhenSelected"] is True
            and row["easyChargePlus"]["rankableWhenSelected"] is True
            for row in entries
        ),
        "allPostChargePoliciesResolved": all(
            row["postChargePolicy"]["graceMinutes"] == 60
            and row["postChargePolicy"]["eurPerMinute"] in {0.08, 0.15}
            for row in entries
        ),
        "allStationsOperationalInSourceSnapshot": all(
            station.get("operationalState") == "operational" for station in stations
        ),
    }
    if not all(gates.values()):
        raise RuntimeError(f"Neogy/Alperia candidate gates failed: {gates}")

    generated_at = str(consolidated.get("generatedAt") or "")
    if not generated_at:
        raise RuntimeError("Italy consolidation has no generatedAt")
    payload = {
        "schemaVersion": 1,
        "dataset": "neogy-alperia-italy-v9-candidate",
        "generatedAt": generated_at,
        "country": "IT",
        "operator": OPERATOR,
        "sources": {
            "directTariffs": DIRECT_URL,
            "postChargeFees": STATIONS_URL,
            "easyCharge": EASYCHARGE_URL,
            "hypercharger100To150Kw": HYPER_100_URL,
            "hypercharger400Kw": HYPER_400_URL,
        },
        "policy": {
            "operatorDirectOnly": True,
            "exactPunEvseIdentityOnly": True,
            "directQrCreditCardOnly": True,
            "southTyrolFromExactPunProvince": True,
            "southTyrolProvinceValues": ["Bolzano", "Bozen"],
            "punNominalQuickCeilingKw": QUICK_MAX_POWER_KW,
            "otherItalyHyperMinimumKw": HYPER_MIN_POWER_KW,
            "acAboveQuickCeilingDirectFailsClosed": True,
            "easyChargeSubscriptionsOptIn": True,
            "easyChargeActivationFeeExcludedFromSessionCost": True,
            "easyChargePartnerRoamingScopeFailsClosed": True,
            "postChargeFeesIncludedInSessionCost": True,
        },
        "counts": counts,
        "safetyGates": gates,
        "entries": entries,
    }
    save_gz(Path(args.out), payload)
    report = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "sources": payload["sources"],
        "policy": payload["policy"],
        "counts": counts,
        "safetyGates": gates,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
