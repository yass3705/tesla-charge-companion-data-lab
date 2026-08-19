#!/usr/bin/env python3
"""Public EVSE-level Lidl direct-tariff extractor for Tesla Charge Companion Data Lab.

Inputs are intentionally limited to a sanitized EVSE-id seed. No private canonical
station database, account export, credential, cookie, or authenticated session is used.
"""
import argparse
import html as htmlmod
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

UA = "TeslaChargeCompanion-DataLab/1.0 (+public EVSE tariff research)"
ENTRY_URL = "https://m.intercharge.eu/evse/enter"
PRIORITY_EVSES = [
    "FR*LDL*E00002411",  # Saint-Cyr-l'Ecole, Rue de l'Aerostation Maritime, CCS 180 kW (manual reference)
    "FR*LDL*E00002412",
    "FR*LDL*E00002414",
    "FR*LDL*E00002027",
    "FR*LDL*E00004465",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fetch(url, method="GET", data=None, headers=None, timeout=25):
    req_headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.6",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {
                "ok": True,
                "status": getattr(r, "status", 200),
                "url": r.geturl(),
                "body": r.read(),
            }
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return {
            "ok": False,
            "status": e.code,
            "url": getattr(e, "url", url),
            "body": body,
            "error": str(e),
        }
    except Exception as e:
        return {"ok": False, "status": None, "url": url, "body": b"", "error": repr(e)}


def body_text(resp):
    return (resp.get("body") or b"").decode("utf-8", errors="replace")


def strip_html(text):
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def discover_form():
    resp = fetch(ENTRY_URL)
    if not resp.get("ok"):
        raise RuntimeError(f"Unable to load public direct-payment entry form: {resp.get('status')} {resp.get('error')}")
    page = body_text(resp)
    action = "/evse/enter"
    m = re.search(r"<form[^>]+action=[\"']([^\"']+)", page, re.I)
    if m:
        action = htmlmod.unescape(m.group(1))
    form_url = urllib.parse.urljoin(resp.get("url") or ENTRY_URL, action)
    hidden = {}
    names = []
    for im in re.finditer(r"<input\b([^>]+)>", page, re.I):
        attrs = im.group(1)
        nm = re.search(r"name=[\"']([^\"']+)", attrs, re.I)
        if not nm:
            continue
        name = nm.group(1)
        names.append(name)
        typ = re.search(r"type=[\"']([^\"']+)", attrs, re.I)
        val = re.search(r"value=[\"']([^\"']*)", attrs, re.I)
        if typ and typ.group(1).lower() == "hidden":
            hidden[name] = htmlmod.unescape(val.group(1) if val else "")
    field = next((n for n in names if n.lower() in ("evseid", "evse_id", "evse", "id")), "evseid")
    return {"formUrl": form_url, "hidden": hidden, "field": field}


def parse_direct_page(evse, resp):
    text = strip_html(body_text(resp))
    prices = []
    patterns = [
        r"Energy\s+based\s+costs\s*:\s*([0-9]+[\.,][0-9]+)\s*(?:EUR|€)\s*/\s*kW/?h",
        r"([0-9]+[\.,][0-9]+)\s*(?:EUR|€)\s*/\s*kW/?h",
        r"([0-9]+[\.,][0-9]+)\s*(?:€|EUR)\s*/?\s*kW/?h",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            try:
                prices.append(float(m.group(1).replace(",", ".")))
            except Exception:
                pass
        if prices:
            break
    prices = sorted({round(p, 6) for p in prices if 0 <= p < 10})

    station_label = None
    m = re.search(r"Station:\s*(.*?)\s*Connector:\s*" + re.escape(evse), text, re.I)
    if m:
        station_label = m.group(1).strip() or None
    elif "Station:" in text and "Connector:" in text:
        m = re.search(r"Station:\s*(.*?)\s*Connector:", text, re.I)
        if m:
            station_label = m.group(1).strip() or None

    auth_amount = None
    for pattern in [
        r"authorize\s+a\s+total\s+amount\s+of\s+([0-9]+[\.,][0-9]+)\s*EUR",
        r"pre[- ]?authori[sz]ation[^0-9]{0,30}([0-9]+[\.,][0-9]+)\s*(?:EUR|€)",
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            auth_amount = float(m.group(1).replace(",", "."))
            break

    # Never persist raw HTML, cookies, hidden form fields, response headers or session URLs.
    return {
        "ok": bool(resp.get("ok")),
        "httpStatus": resp.get("status"),
        "stationLabel": station_label,
        "pricesPerKwh": prices,
        "pricePerKwh": prices[0] if len(prices) == 1 else None,
        "currency": "EUR" if prices else None,
        "authorizationAmountEur": auth_amount,
        "multiplePrices": len(prices) > 1,
        "error": resp.get("error") if not resp.get("ok") else None,
    }


def fetch_evse(evse, form, retries):
    last = None
    for attempt in range(retries + 1):
        payload = dict(form["hidden"])
        payload[form["field"]] = evse
        data = urllib.parse.urlencode(payload).encode("utf-8")
        resp = fetch(
            form["formUrl"],
            method="POST",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        parsed = parse_direct_page(evse, resp)
        parsed["attempt"] = attempt + 1
        last = parsed
        if parsed.get("ok") and (
            parsed.get("pricePerKwh") is not None
            or parsed.get("pricesPerKwh")
            or parsed.get("stationLabel")
        ):
            return parsed
        if attempt < retries:
            time.sleep(0.7 * (attempt + 1))
    return last or {"ok": False, "httpStatus": None, "error": "unknown", "attempt": retries + 1}


def run_shard(args):
    seed = load_json(args.seed)
    evses = [str(r["evseId"]).upper() for r in seed.get("records") or []]
    if not evses or any(not x.startswith("FR*LDL*") for x in evses):
        raise SystemExit("Invalid Lidl EVSE seed")
    selected = [evse for i, evse in enumerate(sorted(evses)) if i % args.shard_count == args.shard_index]
    form = discover_form()
    out = []
    for n, evse in enumerate(selected, 1):
        checked = now_iso()
        direct = fetch_evse(evse, form, args.retries)
        out.append({"evseId": evse, "checkedAt": checked, "direct": direct})
        if n == 1 or n % 50 == 0 or n == len(selected):
            found = sum(1 for r in out if (r.get("direct") or {}).get("pricePerKwh") is not None)
            print(f"shard={args.shard_index} checked={n}/{len(selected)} one_price={found}")
        if args.delay:
            time.sleep(args.delay)
    result = {
        "schemaVersion": "1.0.0",
        "dataset": "tcc-lidl-direct-public-shard",
        "generatedAt": now_iso(),
        "shardIndex": args.shard_index,
        "shardCount": args.shard_count,
        "seedEvse": len(evses),
        "rows": out,
    }
    Path(args.out).mkdir(parents=True, exist_ok=True)
    path = Path(args.out) / f"lidl_direct_shard_{args.shard_index:02d}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(path)


def classify(direct):
    if not direct.get("ok"):
        return "http_error"
    if direct.get("pricePerKwh") is not None:
        return "one_price"
    if direct.get("multiplePrices") or len(direct.get("pricesPerKwh") or []) > 1:
        return "multiple_prices"
    return "no_price"


def run_merge(args):
    seed = load_json(args.seed)
    seed_evses = sorted({str(r["evseId"]).upper() for r in seed.get("records") or []})
    rows_by_evse = {}
    shard_files = sorted(Path(args.shards_dir).rglob("lidl_direct_shard_*.json"))
    if not shard_files:
        raise SystemExit("No shard files found")
    for path in shard_files:
        shard = load_json(path)
        for row in shard.get("rows") or []:
            rows_by_evse[str(row.get("evseId") or "").upper()] = row

    missing = [x for x in seed_evses if x not in rows_by_evse]
    counts = Counter()
    records = []
    for evse in seed_evses:
        row = rows_by_evse.get(evse)
        if not row:
            continue
        direct = row.get("direct") or {}
        status = classify(direct)
        counts[status] += 1
        if status != "one_price":
            continue
        records.append({
            "evseId": evse,
            "source": "operator_direct",
            "provider": "Lidl direct",
            "tariffSource": "public_direct_payment_flow",
            "sourceEntryUrl": ENTRY_URL,
            "pricePerKwh": direct.get("pricePerKwh"),
            "currency": direct.get("currency") or "EUR",
            "stationLabel": direct.get("stationLabel"),
            "authorizationAmountEur": direct.get("authorizationAmountEur"),
            "checkedAt": row.get("checkedAt"),
            "validationStatus": "candidate",
        })

    stats = {
        "seedEvse": len(seed_evses),
        "fetchedEvse": len(rows_by_evse),
        "missingEvse": len(missing),
        "operatorDirectRecords": len(records),
        "evseStatus": dict(sorted(counts.items())),
    }
    dataset = {
        "schemaVersion": "1.0.0",
        "dataset": "operator-direct-lidl-france-candidate",
        "generatedAt": now_iso(),
        "provider": "Lidl direct",
        "source": "operator_direct",
        "sourceEntryUrl": ENTRY_URL,
        "stats": stats,
        "records": records,
    }

    sample_status = []
    for evse in PRIORITY_EVSES:
        row = rows_by_evse.get(evse)
        if row:
            sample_status.append({"evseId": evse, "checkedAt": row.get("checkedAt"), "direct": row.get("direct")})
    priced = [r for r in records[:20]]
    non_priced = []
    for evse in seed_evses:
        row = rows_by_evse.get(evse)
        if not row:
            continue
        status = classify(row.get("direct") or {})
        if status != "one_price":
            non_priced.append({"evseId": evse, "status": status, "direct": row.get("direct")})
            if len(non_priced) >= 20:
                break

    report = {
        "schemaVersion": "1.0.0",
        "dataset": "lidl-direct-public-report",
        "generatedAt": now_iso(),
        "stats": stats,
        "missingEvseIds": missing[:100],
        "examples": {
            "priorityLocalValidation": sample_status,
            "priced": priced,
            "nonPriced": non_priced,
        },
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "lidl_operator_direct_candidate.json").write_text(
        json.dumps(dataset, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    (out / "lidl_direct_full_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = [
        "# Lidl France — public operator-direct extraction",
        "",
        f"Generated: {dataset['generatedAt']}",
        "",
        f"- Seed EVSE: {stats['seedEvse']}",
        f"- Fetched EVSE: {stats['fetchedEvse']}",
        f"- Missing EVSE: {stats['missingEvse']}",
        f"- Candidate direct-price records: {stats['operatorDirectRecords']}",
        f"- Status counts: `{json.dumps(stats['evseStatus'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "Candidate data only. Representative manual validation is required before production use.",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("shard", "merge"), required=True)
    ap.add_argument("--seed", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    ap.add_argument("--shards-dir")
    ap.add_argument("--delay", type=float, default=0.12)
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()
    if args.mode == "shard":
        if not 0 <= args.shard_index < args.shard_count:
            raise SystemExit("Invalid shard index/count")
        run_shard(args)
    else:
        if not args.shards_dir:
            raise SystemExit("--shards-dir required in merge mode")
        run_merge(args)


if __name__ == "__main__":
    main()
