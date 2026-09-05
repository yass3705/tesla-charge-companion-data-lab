#!/usr/bin/env python3
"""Resolve exact IONITY Italy ad-hoc prices from the public IONITY payment API.

The input is the Italy V9 consolidated candidate. Only exact PUN party IOY EVSE IDs
are queried. Missing resolver/location/price data remains fail-closed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://adhoc-bff.ionity.cloud"
PARTY = "IOY"


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            return e.code, {"error": e.read().decode(errors="replace")[:1000]}
        except Exception as e:
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            return 0, {"error": repr(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--sleep", type=float, default=0.08)
    a = ap.parse_args()

    src = load(a.input)
    source_rows = [e for e in src.get("evses", []) if e.get("partyId") == PARTY]
    evse_ids = sorted({str(e.get("evseId") or "").strip() for e in source_rows if e.get("evseId")})
    if not evse_ids:
        raise SystemExit("No Italian IONITY EVSE IDs found")

    headers = {
        "Accept": "application/json",
        "x-adhoc-platform": "WEB",
        "x-adhoc-user-reference": str(uuid.uuid4()),
        "User-Agent": "Mozilla/5.0",
    }

    resolved = {}
    locations = {}
    failures = []
    for idx, evse_id in enumerate(evse_ids, 1):
        url = BASE + "/api/v1/evse/uuids-by-evse-id?" + urllib.parse.urlencode({"evseid": evse_id})
        status, obj = get_json(url, headers)
        loc = obj.get("locationUuid") if isinstance(obj, dict) else None
        conn = obj.get("connectorUuid") if isinstance(obj, dict) else None
        if status != 200 or not loc or not conn:
            failures.append({"evseId": evse_id, "stage": "resolve", "httpStatus": status, "response": obj})
            continue
        resolved[evse_id] = {"locationUuid": loc, "connectorUuid": conn}
        if loc not in locations:
            st, data = get_json(BASE + "/api/v3/location/" + urllib.parse.quote(loc), headers)
            if st == 200 and isinstance(data, dict) and data.get("country") == "IT":
                locations[loc] = data
            else:
                failures.append({"evseId": evse_id, "locationUuid": loc, "stage": "location", "httpStatus": st, "response": data})
        if idx % 25 == 0:
            print("progress", idx, "/", len(evse_ids), "locations", len(locations), "failures", len(failures))
        time.sleep(a.sleep)

    source_by_id = {str(e.get("evseId")): e for e in source_rows}
    rows = []
    missing_prices = []
    variants = {}
    for evse_id in evse_ids:
        src_evse = source_by_id.get(evse_id) or {}
        r = resolved.get(evse_id)
        tariff = None
        connector_info = None
        reason = None
        if not r:
            reason = "ionity_evse_resolver_failed"
        else:
            loc = locations.get(r["locationUuid"])
            if not loc:
                reason = "ionity_location_fetch_failed_or_not_italy"
            else:
                conn = next((c for c in (loc.get("connectors") or []) if c.get("uuid") == r["connectorUuid"]), None)
                if not conn:
                    reason = "ionity_connector_not_found_in_location"
                else:
                    connector_info = {
                        "connectorUuid": conn.get("uuid"),
                        "number": conn.get("number"),
                        "type": conn.get("type"),
                        "maxPowerW": conn.get("maxPower"),
                        "status": conn.get("status"),
                        "blockingFee": conn.get("blockingFee"),
                    }
                    price = conn.get("adhocPrice")
                    if isinstance(price, dict) and price.get("amount") is not None and price.get("unit"):
                        try:
                            amount = float(price.get("amount"))
                        except Exception:
                            amount = None
                        if amount is not None and str(price.get("currency") or "EUR").upper() == "EUR":
                            tariff = {
                                "pricingType": "flat",
                                "currency": "EUR",
                                "unit": str(price.get("unit")),
                                "energyEurPerKwh": amount if str(price.get("unit")).lower() in ("kwh", "kw/h") else None,
                                "rawAdhocPrice": price,
                                "blockingFee": conn.get("blockingFee"),
                                "rankable": str(price.get("unit")).lower() in ("kwh", "kw/h"),
                            }
                            if not tariff["rankable"]:
                                reason = "ionity_price_unit_not_kwh"
                                tariff = None
                            else:
                                key = (amount, "EUR", str(price.get("unit")), conn.get("type"), conn.get("maxPower"))
                                variants[key] = variants.get(key, 0) + 1
                        else:
                            reason = "ionity_price_not_numeric_eur"
                    else:
                        reason = "ionity_exact_adhoc_price_missing"
        if reason:
            missing_prices.append({"evseId": evse_id, "reason": reason})
        rows.append({
            "evseId": evse_id,
            "stationId": src_evse.get("stationId"),
            "partyId": PARTY,
            "operator": src_evse.get("operator"),
            "operationalState": src_evse.get("operationalState"),
            "sourceStatus": src_evse.get("sourceStatus"),
            "locationUuid": r.get("locationUuid") if r else None,
            "connector": connector_info,
            "directTariff": tariff,
            "rankableDirectTariff": bool(tariff),
            "blockingReason": reason,
            "source": "IONITY public adhoc-bff",
        })

    rankable = sum(bool(x["rankableDirectTariff"]) for x in rows)
    coverage = rankable / len(rows) if rows else 0.0
    payload = {
        "schemaVersion": 1,
        "dataset": "ionity-exact-italy-direct-candidate",
        "generatedAt": now_iso(),
        "country": "IT",
        "partyId": PARTY,
        "source": "IONITY public adhoc-bff",
        "sourceEndpoints": ["/api/v1/evse/uuids-by-evse-id", "/api/v3/location/{uuid}"],
        "policy": {"exactEvseScope": True, "failClosed": True, "stationSpecificPricing": True},
        "counts": {
            "sourceEvse": len(rows),
            "resolvedEvse": len(resolved),
            "locations": len(locations),
            "rankableDirectEvse": rankable,
            "unresolvedEvse": len(rows) - rankable,
            "coverage": round(coverage, 6),
        },
        "priceVariants": [
            {"amount": k[0], "currency": k[1], "unit": k[2], "type": k[3], "maxPowerW": k[4], "evse": v}
            for k, v in sorted(variants.items(), key=lambda x: str(x[0]))
        ],
        "failures": failures,
        "unresolved": missing_prices,
        "evses": rows,
    }
    if coverage < 0.90:
        raise SystemExit(f"IONITY Italy exact-price coverage too low: {rankable}/{len(rows)}")

    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(gzip.compress((json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(), compresslevel=9, mtime=0))
    report = {k: v for k, v in payload.items() if k != "evses"}
    rp = Path(a.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
