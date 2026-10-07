#!/usr/bin/env python3
# Batch431 national method validated: read-only FR*ZWO -> exact my.ze-watt.com terminal tariff extraction.
import argparse
import concurrent.futures
import csv
import datetime as dt
import gzip
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from itertools import chain

IRVE_URL = "https://proxy.transport.data.gouv.fr/resource/consolidation-transport-irve-statique"
ZEWATT = "https://my.ze-watt.com/api/stripe-payment/v1/charge-point/{serial}/company"
UA = "TeslaChargeCompanion/ZeWattReadOnlyAudit (+https://github.com/yass3705/tesla-stations-updater-test)"
SERIAL_RE = re.compile(r"^ZW\d+$", re.I)

def get_json(url, timeout=20, retries=2):
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            if e.code in (404, 400, 401, 403):
                return e.code, None, body
            last = f"HTTP {e.code}: {body}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(0.7 * (attempt + 1))
    return None, None, last

def fetch_irve():
    rows = []
    req = urllib.request.Request(IRVE_URL, headers={"User-Agent": UA, "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=180) as response:
        text = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
        header = text.readline()
        delimiter = max((",", ";", "\t", "|"), key=header.count)
        for row in csv.DictReader(chain([header], text), delimiter=delimiter):
            if re.sub(r"[^A-Z0-9]", "", str(row.get("id_pdc_itinerance") or "").upper()).startswith("FRZWO"):
                rows.append(row)
    return rows, len(rows)

def derive_serial(row):
    local = (row.get("id_station_local") or "").strip()
    if SERIAL_RE.fullmatch(local):
        return local.upper(), "id_station_local"
    itin = (row.get("id_station_itinerance") or "").strip().upper()
    normalized = itin.replace("*", "")
    m = re.fullmatch(r"FRZWOE(ZW\d+)", normalized)
    if m:
        return m.group(1).upper(), "id_station_itinerance"
    return None, None

def fetch_terminal(serial):
    url = ZEWATT.format(serial=urllib.parse.quote(serial, safe=""))
    status, payload, error = get_json(url, timeout=15, retries=2)
    if status == 200 and isinstance(payload, dict):
        legal = payload.get("json_ttc_price_for_legal_compliance") or {}
        return {
            "serial": serial,
            "httpStatus": status,
            "ok": True,
            "name": payload.get("name"),
            "visitorStripe": payload.get("visitor_stripe"),
            "visitorGireve": payload.get("visitor_gireve"),
            "allowRegistration": payload.get("allow_registration"),
            "priceTtcText": payload.get("price_ttc"),
            "priceMinEur": payload.get("price_min"),
            "tariffTtc": {
                "perKwhEur": legal.get("per_kwh_price"),
                "perMinuteEur": legal.get("per_minute_price"),
                "perSessionEur": legal.get("per_session_price"),
                "postChargeParkingPerMinuteEur": legal.get("per_minute_parking_price"),
                "postChargeParkingDelayMinutes": legal.get("parking_delay_in_minutes"),
                "transactionTimeParkingPerMinuteEur": legal.get("transaction_time_per_minute_parking_price"),
                "transactionTimeParkingDelayMinutes": legal.get("transaction_time_parking_delay_in_minutes"),
            },
            "connectors": [
                {
                    "ocppId": c.get("ocpp_id"),
                    "status": c.get("status"),
                    "available": c.get("available"),
                    "bookable": c.get("bookable"),
                    "connectorType": c.get("connector_type"),
                    "phase": c.get("connector_phase"),
                    "currentAmp": c.get("current_amp"),
                }
                for c in (payload.get("connectors") or [])
            ],
            "error": None,
        }
    return {"serial": serial, "httpStatus": status, "ok": False, "error": error}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/ze-watt-france-2026-09-24.json")
    ap.add_argument("--report", default="artifacts/ze-watt-france-2026-09-24-report.json")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    rows, reported_total = fetch_irve()
    stations = defaultdict(lambda: {"rows": [], "sources": Counter()})
    unmapped = []
    for row in rows:
        serial, source = derive_serial(row)
        if not serial:
            unmapped.append(row)
            continue
        stations[serial]["rows"].append(row)
        stations[serial]["sources"][source] += 1

    serials = sorted(stations)
    terminal_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(fetch_terminal, s): s for s in serials}
        for fut in concurrent.futures.as_completed(futs):
            s = futs[fut]
            try:
                terminal_results[s] = fut.result()
            except Exception as e:
                terminal_results[s] = {"serial": s, "ok": False, "httpStatus": None, "error": f"worker: {type(e).__name__}: {e}"}

    normalized = []
    for serial in serials:
        irve_rows = stations[serial]["rows"]
        by_station = {}
        for r in irve_rows:
            key = r.get("id_station_itinerance") or r.get("id_station_local") or r.get("nom_station")
            by_station[key] = {
                "idStationItinerance": r.get("id_station_itinerance"),
                "idStationLocal": r.get("id_station_local"),
                "name": r.get("nom_station"),
                "operator": r.get("nom_operateur"),
                "brand": r.get("nom_enseigne"),
                "address": r.get("adresse_station"),
                "dateMaj": r.get("date_maj"),
            }
        normalized.append({
            "serial": serial,
            "irvePdcCount": len(irve_rows),
            "irveStations": list(by_station.values()),
            "irvePowerKw": sorted({r.get("puissance_nominale") for r in irve_rows if r.get("puissance_nominale") is not None}),
            "irvePaymentCbValues": sorted({str(r.get("paiement_cb")) for r in irve_rows}),
            "zeWatt": terminal_results[serial],
        })

    ok = [x for x in normalized if x["zeWatt"].get("ok")]
    with_structured_tariff = [
        x for x in ok
        if any(v not in (None, "", "0", "0.0", "0.000")
               for v in (x["zeWatt"].get("tariffTtc") or {}).values())
    ]
    stripe = [x for x in ok if x["zeWatt"].get("visitorStripe") is True]
    no_stripe = [x for x in ok if x["zeWatt"].get("visitorStripe") is False]
    statuses = Counter(str(x["zeWatt"].get("httpStatus")) for x in normalized)
    tariff_signatures = Counter()
    for x in with_structured_tariff:
        t = x["zeWatt"].get("tariffTtc") or {}
        tariff_signatures[json.dumps(t, sort_keys=True, ensure_ascii=False)] += 1

    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    output = {
        "schemaVersion": 1,
        "generatedAt": generated,
        "source": {
            "irveUrl": IRVE_URL,
            "irveFilter": "normalized id_pdc_itinerance starts with FRZWO",
            "zeWattEndpointTemplate": "https://my.ze-watt.com/api/stripe-payment/v1/charge-point/{serial}/company",
            "readOnly": True,
            "paymentIntentEndpointCalled": False,
        },
        "counts": {
            "irveRowsReported": reported_total,
            "irveRowsFetched": len(rows),
            "mappedUniqueSerials": len(serials),
            "unmappedIrveRows": len(unmapped),
            "zeWattSuccess": len(ok),
            "zeWattFailures": len(normalized) - len(ok),
            "visitorStripeTrue": len(stripe),
            "visitorStripeFalse": len(no_stripe),
            "structuredTariff": len(with_structured_tariff),
            "uniqueStructuredTariffSignatures": len(tariff_signatures),
        },
        "stations": normalized,
        "unmappedIrveRows": unmapped,
    }
    report = {
        "schemaVersion": 1,
        "generatedAt": generated,
        "counts": output["counts"],
        "httpStatuses": dict(statuses),
        "tariffSignatures": [
            {"count": count, "tariffTtc": json.loads(sig)}
            for sig, count in tariff_signatures.most_common()
        ],
        "sampleSuccess": [
            {
                "serial": x["serial"],
                "name": x["zeWatt"].get("name"),
                "visitorStripe": x["zeWatt"].get("visitorStripe"),
                "visitorGireve": x["zeWatt"].get("visitorGireve"),
                "priceTtcText": x["zeWatt"].get("priceTtcText"),
                "tariffTtc": x["zeWatt"].get("tariffTtc"),
            }
            for x in ok[:20]
        ],
        "sampleFailures": [x["zeWatt"] for x in normalized if not x["zeWatt"].get("ok")][:20],
        "unmappedSample": unmapped[:20],
        "policy": {
            "noTariffMeansFree": False,
            "rankableDirect": "Use exact structured TTC tariff per serial/connector only; preserve visitorStripe/visitorGireve and every time/session/parking component. Missing/404/error => fail closed and TCC fallback, never free.",
            "roaming": "Do not use Ze-Watt mobility-card/eMSP roaming tariff as CPO-direct authority.",
        },
    }

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with gzip.open(args.out + ".gz", "wt", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
