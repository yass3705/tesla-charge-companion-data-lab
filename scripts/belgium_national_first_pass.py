#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/belgium/nap-belgium-full.json")
    ap.add_argument("--report", default="reports/belgium-national-first-pass-2026-09-28.json")
    ap.add_argument("--progress", default="docs/belgium-cpo-progress-2026-09.json")
    args = ap.parse_args()

    data = load(args.input)
    locations = data.get("locations") or []

    location_ids = Counter()
    station_ids = Counter()
    evse_ids = Counter()
    external_ids = Counter()

    op = defaultdict(lambda: {
        "sites": 0,
        "stations": 0,
        "evses": 0,
        "connectors": 0,
        "pricedEvses": 0,
        "adHocPricedEvses": 0,
        "missingPriceEvses": 0,
        "acEvses": 0,
        "dcEvses": 0,
        "priceComponents": Counter(),
        "taxIncludedTrue": 0,
        "taxIncludedFalse": 0,
        "taxIncludedNull": 0,
        "currencies": Counter(),
        "rateIds": Counter(),
    })

    missing_price = []
    locations_missing_coords = []
    locations_missing_address = []
    evses_missing_external_id = []

    total_stations = total_evses = total_connectors = 0
    priced_evses = adhoc_priced_evses = 0

    for loc in locations:
        lid = str(loc.get("id") or "")
        location_ids[lid] += 1
        operator = str(loc.get("operator") or "UNKNOWN")
        op[operator]["sites"] += 1

        if loc.get("latitude") is None or loc.get("longitude") is None:
            locations_missing_coords.append(lid)
        if not loc.get("city") and not loc.get("addressLines"):
            locations_missing_address.append(lid)

        for st in loc.get("stations") or []:
            sid = str(st.get("id") or "")
            station_ids[sid] += 1
            total_stations += 1
            op[operator]["stations"] += 1

            for evse in st.get("evses") or []:
                eid = str(evse.get("id") or "")
                evse_ids[eid] += 1
                total_evses += 1
                op[operator]["evses"] += 1

                ctype = str(evse.get("currentType") or "").lower()
                if ctype == "ac":
                    op[operator]["acEvses"] += 1
                elif ctype == "dc":
                    op[operator]["dcEvses"] += 1

                ext = evse.get("externalIdentifiers") or []
                if not ext:
                    evses_missing_external_id.append(eid)
                for x in ext:
                    external_ids[str(x)] += 1

                connectors = evse.get("connectors") or []
                total_connectors += len(connectors)
                op[operator]["connectors"] += len(connectors)

                prices = evse.get("prices") or []
                if prices:
                    priced_evses += 1
                    op[operator]["pricedEvses"] += 1
                    if any(p.get("ratePolicy") == "adHoc" for p in prices):
                        adhoc_priced_evses += 1
                        op[operator]["adHocPricedEvses"] += 1
                    for p in prices:
                        ptype = str(p.get("priceType") or "UNKNOWN")
                        op[operator]["priceComponents"][ptype] += 1
                        ti = p.get("taxIncluded")
                        if ti is True:
                            op[operator]["taxIncludedTrue"] += 1
                        elif ti is False:
                            op[operator]["taxIncludedFalse"] += 1
                        else:
                            op[operator]["taxIncludedNull"] += 1
                        if p.get("currency"):
                            op[operator]["currencies"][str(p["currency"])] += 1
                        if p.get("rateId"):
                            op[operator]["rateIds"][str(p["rateId"])] += 1
                else:
                    op[operator]["missingPriceEvses"] += 1
                    missing_price.append({
                        "operator": operator,
                        "locationId": lid,
                        "brand": loc.get("brand"),
                        "city": loc.get("city"),
                        "stationId": sid,
                        "evseId": eid,
                        "externalIdentifiers": ext,
                        "powerW": evse.get("availableChargingPowerW"),
                        "currentType": evse.get("currentType"),
                    })

    def dups(counter: Counter) -> list[str]:
        return sorted([k for k, n in counter.items() if k and n > 1])

    operators = {}
    progress_cpos = []
    for operator in sorted(op):
        s = op[operator]
        evses = s["evses"]
        priced = s["pricedEvses"]
        coverage = round(priced / evses * 100, 2) if evses else 0.0
        state = "complete" if evses > 0 and s["missingPriceEvses"] == 0 else "partial"
        operators[operator] = {
            "sites": s["sites"],
            "stations": s["stations"],
            "evses": evses,
            "connectors": s["connectors"],
            "pricedEvses": priced,
            "adHocPricedEvses": s["adHocPricedEvses"],
            "missingPriceEvses": s["missingPriceEvses"],
            "priceCoveragePct": coverage,
            "acEvses": s["acEvses"],
            "dcEvses": s["dcEvses"],
            "priceComponents": dict(s["priceComponents"].most_common()),
            "taxIncluded": {
                "trueComponents": s["taxIncludedTrue"],
                "falseComponents": s["taxIncludedFalse"],
                "nullComponents": s["taxIncludedNull"],
            },
            "currencies": dict(s["currencies"].most_common()),
            "distinctRateIds": len(s["rateIds"]),
            "state": state,
        }
        progress_cpos.append({
            "name": operator,
            "state": state,
            "sites": s["sites"],
            "evses": evses,
            "pricedEvses": priced,
            "missingPriceEvses": s["missingPriceEvses"],
            "priceCoveragePct": coverage,
            "firstPassDone": True,
            "source": "Belgium NAP DATEX II /datex2/v1/locations",
        })

    total_locations = len(locations)
    report = {
        "country": "BE",
        "source": data.get("source"),
        "phase": "national-first-pass",
        "scope": "Complete current Belgium NAP snapshot before any gap-filling",
        "totals": {
            "locations": total_locations,
            "stations": total_stations,
            "evses": total_evses,
            "connectors": total_connectors,
            "pricedEvses": priced_evses,
            "adHocPricedEvses": adhoc_priced_evses,
            "missingPriceEvses": total_evses - priced_evses,
            "priceCoveragePct": round(priced_evses / total_evses * 100, 2) if total_evses else 0.0,
            "operators": len(operators),
        },
        "operators": operators,
        "integrity": {
            "declaredLocationCount": data.get("locationCount"),
            "actualLocationCount": total_locations,
            "locationCountMatches": data.get("locationCount") == total_locations,
            "duplicateLocationIds": dups(location_ids),
            "duplicateStationIds": dups(station_ids),
            "duplicateEvseIds": dups(evse_ids),
            "duplicateExternalEvseIds": dups(external_ids),
            "locationsMissingCoordinates": locations_missing_coords,
            "locationsMissingAddress": locations_missing_address,
            "evsesMissingExternalIdentifier": evses_missing_external_id,
        },
        "missingPriceEvses": missing_price,
    }

    progress = {
        "country": "BE",
        "asOf": "2026-09-28",
        "canonicalSource": "data/belgium/nap-belgium-full.json",
        "firstPass": {
            "done": True,
            "operatorsSeen": len(progress_cpos),
            "locations": total_locations,
            "evses": total_evses,
            "connectors": total_connectors,
        },
        "counts": {
            "complete": sum(1 for x in progress_cpos if x["state"] == "complete"),
            "partial": sum(1 for x in progress_cpos if x["state"] == "partial"),
            "blocked": 0,
            "total": len(progress_cpos),
        },
        "cpos": sorted(progress_cpos, key=lambda x: (-x["sites"], x["name"])),
        "rules": [
            "The national first pass covers every CPO present in the current Belgium NAP snapshot before any second-pass gap resolution.",
            "complete means all EVSEs for that CPO in the current NAP snapshot have at least one price component; it does not assert that the NAP contains every physical charger in Belgium.",
            "No missing tariff is invented or extrapolated.",
        ],
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.progress).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.progress).write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "totals": report["totals"],
        "progressCounts": progress["counts"],
        "operators": operators,
        "missingPriceEvses": missing_price,
        "integritySummary": {
            "locationCountMatches": report["integrity"]["locationCountMatches"],
            "duplicateLocationIds": len(report["integrity"]["duplicateLocationIds"]),
            "duplicateStationIds": len(report["integrity"]["duplicateStationIds"]),
            "duplicateEvseIds": len(report["integrity"]["duplicateEvseIds"]),
            "duplicateExternalEvseIds": len(report["integrity"]["duplicateExternalEvseIds"]),
            "locationsMissingCoordinates": len(locations_missing_coords),
            "locationsMissingAddress": len(locations_missing_address),
            "evsesMissingExternalIdentifier": len(evses_missing_external_id),
        }
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
