#!/usr/bin/env python3
import argparse, gzip, json, re, sys, time, urllib.request, urllib.parse, urllib.error, http.cookiejar
from datetime import datetime, timezone
from pathlib import Path

FEED_URL = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
BASE = "https://adhoc.swisscharge.ch"
TENANT = "Swisscharge_CH"
EVSE_RE = re.compile(r"CH\*SUI\*E(.+)$", re.I)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

def download_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
        encoding = (r.headers.get("Content-Encoding") or "").lower()
    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))

def collect_refs(obj):
    refs = []
    def walk(v):
        if isinstance(v, dict):
            for val in v.values():
                if isinstance(val, str):
                    m = EVSE_RE.search(val)
                    if m:
                        refs.append(m.group(1))
                walk(val)
        elif isinstance(v, list):
            for z in v:
                walk(z)
    walk(obj)
    return list(dict.fromkeys(refs))

def opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get(op, url, headers=None, timeout=35):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with op.open(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, dict(r.headers.items()), raw
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()), e.read()
    except Exception as e:
        msg = (type(e).__name__ + ": " + str(e)).encode("utf-8", "replace")
        return 0, {}, msg

def parse_payload(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None

def tariff_row(ref, payload):
    data = (payload or {}).get("data") or {}
    cp = data.get("chargePoint") or {}
    evses = data.get("evses") or []
    evse = next((e for e in evses if str(e.get("physicalReference")) == str(ref)), evses[0] if evses else {})
    tariff = evse.get("tariff") or {}
    pricing = tariff.get("pricing") or {}
    restrictions = tariff.get("restrictions") or {}
    power = evse.get("powerOptions") or {}
    connectors = evse.get("connectors") or []
    return {
        "physicalReference": str(ref),
        "emi3Id": evse.get("emi3Id"),
        "internalEvseId": evse.get("id"),
        "chargePointId": cp.get("id"),
        "locationName": cp.get("locationName"),
        "address": cp.get("address"),
        "city": cp.get("city"),
        "region": cp.get("region"),
        "country": cp.get("country"),
        "networkStatus": cp.get("networkStatus"),
        "hardwareStatus": evse.get("hardwareStatus"),
        "currentType": evse.get("currentType"),
        "maxPowerW": power.get("maxPower"),
        "connectors": [
            {"id": c.get("id"), "type": c.get("type"), "format": c.get("format"), "status": c.get("status")}
            for c in connectors
        ],
        "tariff": {
            "id": tariff.get("id"),
            "name": tariff.get("name"),
            "type": tariff.get("type"),
            "currency": tariff.get("currency"),
            "minPrice": pricing.get("minPrice"),
            "connectionFee": pricing.get("connectionFee"),
            "pricePerKwh": pricing.get("pricePerKwh"),
            "pricePerPeriod": pricing.get("pricePerPeriod"),
            "pricePeriodInMinutes": pricing.get("pricePeriodInMinutes"),
            "idleFeePerMinute": pricing.get("idleFeePerMinute"),
            "idleFeeGracePeriodMinutes": pricing.get("idleFeeGracePeriodMinutes"),
            "connectionFeeMinimumSessionDuration": pricing.get("connectionFeeMinimumSessionDuration"),
            "connectionFeeMinimumSessionEnergy": pricing.get("connectionFeeMinimumSessionEnergy"),
            "durationFeeGracePeriod": pricing.get("durationFeeGracePeriod"),
            "adHocPreAuthorizeAmount": restrictions.get("adHocPreAuthorizeAmount"),
            "applyToAdHocUsers": restrictions.get("applyToAdHocUsers"),
            "stopSession": tariff.get("stopSession"),
        },
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="swisscharge-tariffs.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    ap.add_argument("--delay", type=float, default=0.72, help="Minimum delay between tariff API requests")
    args = ap.parse_args()

    feed = download_json(FEED_URL)
    refs_all = collect_refs(feed)
    if args.shard_count < 1 or args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise SystemExit("Invalid shard arguments")
    refs = refs_all[args.shard_index::args.shard_count]
    if args.limit > 0:
        refs = refs[:args.limit]

    op = opener()
    results, unresolved = [], []
    counts = {"http200": 0, "http4xx": 0, "http5xx": 0, "transport": 0, "noTariff": 0}
    last_api = 0.0

    # Establish one anonymous tenant session. Per-EVSE bootstrap is used only as retry fallback.
    if refs:
        first_page = f"{BASE}/tenant/{TENANT}/session-start/{urllib.parse.quote(refs[0], safe='')}"
        get(op, first_page, {"User-Agent": UA}, 30)

    for idx, ref in enumerate(refs, 1):
        page = f"{BASE}/tenant/{TENANT}/session-start/{urllib.parse.quote(ref, safe='')}"
        api = f"{BASE}/api/v1/charge-points?evsePhysicalReference={urllib.parse.quote(ref, safe='')}"
        headers = {
            "Accept": "application/json",
            "Tenant": TENANT,
            "tenant-path": page,
            "Referer": page,
            "User-Agent": UA,
        }

        wait = args.delay - (time.monotonic() - last_api)
        if wait > 0:
            time.sleep(wait)
        status, resp_headers, raw = get(op, api, headers, 35)
        last_api = time.monotonic()

        # If context/session-specific failure occurs, bootstrap this EVSE once and retry.
        if status in (0, 401, 403, 409, 422, 429):
            get(op, page, {"User-Agent": UA}, 30)
            wait = args.delay - (time.monotonic() - last_api)
            if wait > 0:
                time.sleep(wait)
            status, resp_headers, raw = get(op, api, headers, 20)
            last_api = time.monotonic()

        if status == 200:
            payload = parse_payload(raw)
            row = tariff_row(ref, payload)
            row["httpStatus"] = status
            if row["tariff"]["id"] is None:
                counts["noTariff"] += 1
                unresolved.append({"physicalReference": ref, "reason": "no_tariff", "httpStatus": status})
            else:
                counts["http200"] += 1
                results.append(row)
        else:
            if 400 <= status < 500:
                counts["http4xx"] += 1
            elif status >= 500:
                counts["http5xx"] += 1
            else:
                counts["transport"] += 1
            body = raw.decode("utf-8", "replace")[:400] if raw else ""
            unresolved.append({"physicalReference": ref, "reason": "http_error", "httpStatus": status, "body": body})

        if idx % 100 == 0 or idx == len(refs):
            print(f"progress={idx}/{len(refs)} resolved={len(results)} unresolved={len(unresolved)}", flush=True)

        rem = resp_headers.get("RateLimit-Remaining") or resp_headers.get("ratelimit-remaining")
        reset = resp_headers.get("RateLimit-Reset") or resp_headers.get("ratelimit-reset")
        try:
            if rem is not None and int(rem) <= 5:
                time.sleep(max(float(reset or 1), 1.0))
        except Exception:
            pass

    unique_tariffs = {}
    for r in results:
        t = r["tariff"]
        key = str(t.get("id"))
        if key not in unique_tariffs:
            unique_tariffs[key] = t

    out = {
        "schemaVersion": 1,
        "source": {
            "nationalFeed": FEED_URL,
            "tariffApi": f"{BASE}/api/v1/charge-points?evsePhysicalReference={{physicalReference}}",
            "tenant": TENANT,
            "authentication": "none",
            "retrievedAt": datetime.now(timezone.utc).isoformat(),
        },
        "scope": {
            "selector": "unique EVSE identifiers matching CH*SUI*E* in the Swiss national OICP feed",
            "nationalEvseCount": len(refs_all),
            "shardIndex": args.shard_index,
            "shardCount": args.shard_count,
            "evseCount": len(refs),
        },
        "summary": {
            "resolvedTariffEvseCount": len(results),
            "unresolvedEvseCount": len(unresolved),
            "uniqueTariffCount": len(unique_tariffs),
            **counts,
        },
        "tariffsById": unique_tariffs,
        "evses": results,
        "unresolved": unresolved,
    }
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
