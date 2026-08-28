#!/usr/bin/env python3
from __future__ import annotations

import gzip
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader

PUN_DATA = Path("data/national/pun_italy_national.json.gz")
OUT = Path("data/national/plenitude_direct_stations_italy.json.gz")
REPORT = Path("data/reports/plenitude_italy_apply_report.json")
EXCLUSION_PDF = "https://eniplenitude.com/content/dam/plenitude-it/documenti/pdf/e-mobility/promo-estate-2026/potr_colonnine_conto_terzi_escluse_da_offerta_estate_2026.pdf"
PARTY_ID = "BEC"
VALID_FROM = "2026-06-01"
VALID_THROUGH = "2026-09-30T23:59:59+02:00"


def local_code_from_evse_id(evse_id: str) -> str | None:
    parts = str(evse_id or "").split("*")
    if len(parts) < 4:
        return None
    element = parts[-2].strip()
    connector = parts[-1].strip()
    if not element or not connector:
        return None
    # OCPI eMAID-style EVSE element is commonly prefixed with E; the official
    # Plenitude exception list uses the station code without that OCPI marker.
    if element.startswith("E") and len(element) > 1:
        element = element[1:]
    return f"{element}-{connector}"


def fetch_exclusion_codes() -> tuple[set[str], dict[str, Any]]:
    r = requests.get(EXCLUSION_PDF, timeout=60, headers={"User-Agent": "tesla-charge-companion-data-lab/plenitude-apply-1.0"})
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    codes: set[str] = set()
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or "Charging station code" in line:
            continue
        # Codes are printed as the final table column. Keep the parser broad
        # enough for legacy/vendor identifiers while still anchoring to the end.
        match = re.search(r"([A-Z0-9][A-Z0-9_-]*(?:-[A-Z0-9_-]+)+)$", line, re.I)
        if match:
            codes.add(match.group(1).upper())
    return codes, {"pageCount": len(reader.pages), "codeCount": len(codes)}


def station_tariff_class(max_power_kw: float | None, has_dc: bool) -> tuple[str | None, float | None, dict[str, Any] | None]:
    if max_power_kw is None:
        return None, None, None
    if not has_dc and max_power_kw <= 22.5:
        return "quick", 0.53, {"graceMinutes": 60, "eurPerMinute": 0.12, "inactiveWindow": "23:00-07:00"}
    if has_dc and max_power_kw < 75.0:
        return "fast", 0.60, {"graceMinutes": 60, "eurPerMinute": 0.20, "active": "24h"}
    if has_dc and max_power_kw >= 75.0:
        return "fast_plus_ultrafast", 0.65, {"graceMinutes": 60, "eurPerMinute": 0.30, "active": "24h"}
    return None, None, None


def main() -> None:
    pun = json.loads(gzip.decompress(PUN_DATA.read_bytes()))
    exclusion_codes, exclusion_meta = fetch_exclusion_codes()
    bec_evses = [e for e in (pun.get("evses") or []) if str(e.get("partyId") or "") == PARTY_ID]
    bec_stations = [s for s in (pun.get("stations") or []) if str(s.get("partyId") or "") == PARTY_ID]

    local_to_evses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for evse in bec_evses:
        code = local_code_from_evse_id(str(evse.get("evseId") or ""))
        if code:
            local_to_evses[code.upper()].append(evse)

    matched_exclusion_codes = exclusion_codes & set(local_to_evses)
    unmatched_exclusion_codes = exclusion_codes - set(local_to_evses)
    excluded_evse_ids = {
        str(evse.get("evseId"))
        for code in matched_exclusion_codes
        for evse in local_to_evses.get(code, [])
    }

    enriched_evses: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    rankable_count = 0
    class_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    by_station = {str(s.get("stationId") or ""): s for s in bec_stations if s.get("stationId")}
    for station in bec_stations:
        evses = station.get("evses") or []
        max_power = station.get("maxPowerKw")
        has_dc = any(
            str(c.get("powerType") or "").upper().startswith("DC")
            for e in evses for c in (e.get("connectors") or [])
        )
        tariff_class, rate, overstay = station_tariff_class(float(max_power) if max_power is not None else None, has_dc)
        out_evses = []
        for evse in evses:
            out = dict(evse)
            evse_id = str(out.get("evseId") or "")
            local_code = local_code_from_evse_id(evse_id)
            excluded = evse_id in excluded_evse_ids
            if excluded:
                blocking = "official_summer_offer_exclusion"
            elif tariff_class is None or rate is None:
                blocking = "unable_to_classify_station_tariff_band"
            else:
                blocking = None
            rankable = blocking is None
            if rankable:
                rankable_count += 1
                class_counts[tariff_class] += 1
            else:
                reason_counts[blocking or "unknown"] += 1
            out.update({
                "plenitudeLocalCode": local_code,
                "plenitudeSummerOfferExcluded": excluded,
                "directEurPerKwh": rate if rankable else None,
                "directTariffClass": tariff_class if rankable else None,
                "directTariffValidFrom": VALID_FROM if rankable else None,
                "directTariffValidThrough": VALID_THROUGH if rankable else None,
                "feePolicy": overstay if rankable else None,
                "rankableDirect": rankable,
                "blockingReason": blocking,
                "tariffSource": "Plenitude On The Road official summer 2026 tariff + official exclusion PDF" if rankable else None,
            })
            out_evses.append(out)
            enriched_evses.append(out)

        station_out = {k: v for k, v in station.items() if k != "evses"}
        station_out["evses"] = out_evses
        station_out["rankableEvseCount"] = sum(1 for e in out_evses if e.get("rankableDirect"))
        station_out["rankableDirect"] = station_out["rankableEvseCount"] > 0
        station_out["directTariffClass"] = tariff_class
        station_out["directEurPerKwh"] = rate if station_out["rankableDirect"] else None
        station_rows.append(station_out)

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "plenitude-direct-operated-evse-italy",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "country": "IT",
        "operator": "Plenitude On The Road",
        "punPartyId": PARTY_ID,
        "scope": {
            "operatorDirectOnly": True,
            "registeredAppOrRfidRequired": True,
            "summerOfferValidFrom": VALID_FROM,
            "summerOfferValidThrough": VALID_THROUGH,
            "officialExclusionsApplied": True,
            "failClosedOnUnclassifiedStations": True,
        },
        "counts": {
            "punBecEvseCount": len(bec_evses),
            "punBecStationCount": len(bec_stations),
            "officialExclusionCodeCount": len(exclusion_codes),
            "matchedExclusionCodeCount": len(matched_exclusion_codes),
            "unmatchedExclusionCodeCount": len(unmatched_exclusion_codes),
            "exclusionCodeMatchPct": round(100 * len(matched_exclusion_codes) / len(exclusion_codes), 2) if exclusion_codes else 0.0,
            "excludedPunEvseCount": len(excluded_evse_ids),
            "rankableEvseCount": rankable_count,
            "rankableCoveragePct": round(100 * rankable_count / len(bec_evses), 2) if bec_evses else 0.0,
            "rankableClassCounts": dict(class_counts),
            "blockedReasonCounts": dict(reason_counts),
        },
        "quality": {
            "officialExclusionPdfParsed": exclusion_meta,
            "unmatchedExclusionCodeSample": sorted(unmatched_exclusion_codes)[:200],
        },
        "stations": station_rows,
        "evses": enriched_evses,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    OUT.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"generatedAt": payload["generatedAt"], "counts": payload["counts"], "quality": payload["quality"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
