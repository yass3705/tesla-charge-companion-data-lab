#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import enel_italy_national_tariffs as enel

# Public Ewiva EVSE examples independently visible on public charging directories.
SAMPLES = [
    {"serial": "EW057701", "expectedEvsePrefix": "IT*EWI*", "publicPowerKw": 300},
    {"serial": "EW056301", "expectedEvsePrefix": "IT*EWI*", "publicPowerKw": 150},
    {"serial": "HPC162000087", "expectedEvsePrefix": "IT*EWI*", "publicPowerKw": 350},
]
OUT = Path("data/reports/enel_italy_ewiva_probe.json")


def summarize(detail):
    result = detail.get("result") if isinstance(detail, dict) else None
    plugs = []
    if isinstance(result, dict):
        for evse in result.get("evses") or []:
            if not isinstance(evse, dict):
                continue
            for plug in evse.get("plugs") or []:
                if not isinstance(plug, dict):
                    continue
                plugs.append({
                    "evseId": evse.get("evseId"),
                    "evseStatus": evse.get("status"),
                    "typology": plug.get("typology"),
                    "maxPower": plug.get("maxPower"),
                    "status": plug.get("status"),
                    "currency": plug.get("currency"),
                    "price": plug.get("price"),
                    "typePrice": plug.get("typePrice"),
                    "directPaymenthPrice": plug.get("directPaymenthPrice"),
                    "penaltyPrice": plug.get("penaltyPrice"),
                })
    return {
        "ok": detail.get("ok"),
        "httpStatus": detail.get("httpStatus"),
        "businessCode": detail.get("businessCode"),
        "businessMessage": detail.get("businessMessage"),
        "stationName": result.get("csName") if isinstance(result, dict) else None,
        "stationStatus": result.get("status") if isinstance(result, dict) else None,
        "plugs": plugs,
    }


def main():
    headers = enel.extract_public_headers()
    rows = []
    for sample in SAMPLES:
        detail = enel.get_detail(sample["serial"], headers)
        rows.append({**sample, **summarize(detail)})
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "samples": rows,
        "security": {"accountCredentialsUsed": False, "authorizationMaterialPersisted": False},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
