#!/usr/bin/env python3
"""Probe exact Allego Italy direct prices for the current PUN IT*ALL EVSE set.

Reuses the public DXP client-key capture and parser already validated for France.
No secret is stored: only a SHA-256 fingerprint of the transient public client
configuration is logged by the shared helper.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import allego_dxp_national as base

EVSE_IDS = [
    "IT*ALL*EITALLEGO0100011","IT*ALL*EITALLEGO0100012",
    "IT*ALL*EITALLEGO0100021","IT*ALL*EITALLEGO0100022",
    "IT*ALL*EITALLEGO0100051","IT*ALL*EITALLEGO0100052",
    "IT*ALL*EITALLEGO0100141","IT*ALL*EITALLEGO0100142",
    "IT*ALL*EITALLEGO0100071","IT*ALL*EITALLEGO0100072",
    "IT*ALL*EITALLEGO0100081","IT*ALL*EITALLEGO0100082",
    "IT*ALL*EITALLEGO0100121","IT*ALL*EITALLEGO0100122",
    "IT*ALL*EITALLEGO0100211","IT*ALL*EITALLEGO0100212",
    "IT*ALL*EITALLEGO0100171","IT*ALL*EITALLEGO0100172",
    "IT*ALL*EITALLEGO0100191","IT*ALL*EITALLEGO0100192",
    "IT*ALL*EITALLEGO0100181","IT*ALL*EITALLEGO0100182",
    "IT*ALL*EITALLEGO0100201","IT*ALL*EITALLEGO0100202",
    "IT*ALL*EITALLEGO0100151","IT*ALL*EITALLEGO0100152",
    "IT*ALL*EITALLEGO0100161","IT*ALL*EITALLEGO0100162",
]

OUT = Path("data/national/allego_direct_stations_italy_20260925.json.gz")
REPORT = Path("data/reports/allego_italy_exact_20260925.json")

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def dxp_candidates(evse_id: str) -> list[str]:
    # OCPI IT*ALL*EITALLEGO0100011 -> DXP ITALLEGO0100011 (+ group fallback).
    parts = evse_id.split("*")
    tail = parts[-1]
    if tail.startswith("E") and len(tail) > 1:
        tail = tail[1:]
    vals = [tail]
    if tail and tail[-1:].isdigit():
        vals.append(tail[:-1])
    return list(dict.fromkeys(vals))

def resolve(evse_id: str, key: str) -> dict:
    attempts=[]
    status=0; body=""; chosen=None
    for cid in dxp_candidates(evse_id):
        status,body=base.call_dxp(cid,key)
        attempts.append({"id":cid,"status":status})
        if status==200:
            chosen=cid
            break
    obj={}
    if status==200:
        try:
            parsed=json.loads(body)
            if isinstance(parsed,dict): obj=parsed
        except Exception:
            pass
    info=base.extract_price_info(obj)
    rates,fees=base.parse_price_text(info)
    own=obj.get("isOwnNetwork")
    direct=rates[0] if len(rates)==1 else None
    max_power=base._float(obj.get("maxPowerKw"))
    normalized_fee_rates=[]
    for fee in fees:
        try:
            v=float(fee.get("value"))
        except Exception:
            continue
        unit=str(fee.get("unit") or "").lower()
        if unit in {"min","minute"}:
            normalized_fee_rates.append(round(v,6))
        elif unit in {"hour","heure"}:
            normalized_fee_rates.append(round(v/60.0,6))
    normalized_fee_rates=sorted(set(normalized_fee_rates))
    fee_policy=None
    fee_error=None
    if normalized_fee_rates:
        if max_power and max_power > 22.5 and normalized_fee_rates == [0.253]:
            fee_policy={
                "type":"idle_after_charging",
                "ratePerMinuteEur":0.253,
                "notBeforeSessionMinute":45,
                "onlyAfterChargingStops":True,
                "country":"IT",
                "vatIncluded":True,
                "source":"https://www.allego.eu/overstay-fee/",
            }
        else:
            fee_error="unparsed_time_or_blocking_fee"
    rankable=bool(status==200 and own is not False and direct is not None and fee_error is None)
    return {
        "evseId":evse_id,
        "dxpChargePointId":chosen,
        "attempts":attempts,
        "status":status,
        "brand":obj.get("brand"),
        "isOwnNetwork":own,
        "maxPowerKw":max_power,
        "directEurPerKwh":direct if rankable else None,
        "rateCandidatesEurPerKwh":rates,
        "feeCandidates":fees,
        "feePolicy":fee_policy,
        "priceTextPresent":bool(info),
        "rankableDirect":rankable,
        "blockingReason":None if rankable else (
            "not_allego_own_network" if own is False else
            "unparsed_time_or_blocking_fee" if fee_error else
            "ambiguous_or_missing_direct_kwh_rate" if status==200 else
            f"dxp_http_{status}"
        ),
    }

def main():
    key=base.capture_public_client_key()
    rows=[resolve(e,key) for e in EVSE_IDS]
    rankable=[x for x in rows if x["rankableDirect"]]
    blocked=[x for x in rows if not x["rankableDirect"]]
    payload={
        "schemaVersion":"1.0.0",
        "dataset":"allego-direct-evse-italy-pun20260920",
        "generatedAt":now_iso(),
        "operator":"Allego Italy S.r.l.",
        "partyId":"ALL",
        "country":"IT",
        "scope":{"operatorDirectOnly":True,"roamingIncluded":False,"exactEvsePriceRequiredForRanking":True,"countryDefaultsAreRankable":False},
        "sources":{"inventory":"PUN artifact 10597588294 / run192","tariffBackend":"Allego DXP public web client"},
        "counts":{"punEvse":len(rows),"rankableEvse":len(rankable),"blockedEvse":len(blocked),"distinctRates":dict(Counter(str(x["directEurPerKwh"]) for x in rankable))},
        "evses":rows,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n").encode(),compresslevel=9,mtime=0))
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({
        "generatedAt":payload["generatedAt"],"counts":payload["counts"],
        "blockedReasonCounts":dict(Counter(x["blockingReason"] for x in blocked)),
        "blocked":blocked,
    },ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(payload["counts"],indent=2))

if __name__=="__main__":
    main()
