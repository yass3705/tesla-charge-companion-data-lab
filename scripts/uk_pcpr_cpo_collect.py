#!/usr/bin/env python3
"""Collect an operator-scoped UK Eco-Movement PCPR feed and stage exact EVSE tariffs.

Never promote an eMSP/other-operator tariff, guess an unreferenced price, or
expose a credential in output. This stages evidence; V9 activation is separate.
"""
from __future__ import annotations

import collections
import copy
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://open-chargepoints.com/api/ocpi/cpo/2.2.1/"
PROVIDERS = {
    "allego_uk": {"name": "Allego UK", "aliases": ("allego",),
                  "secret": "ALLEGO_UK_PCPR_TOKEN", "slug": "allego_uk",
                  "id": "allego-uk-pcpr-direct"},
    "source_ev": {"name": "Source EV", "aliases": ("sourceev",),
                  "secret": "SOURCE_EV_PCPR_TOKEN", "slug": "source_ev",
                  "id": "source-ev-uk-pcpr-direct"},
}
ALLOWED_COMPONENTS = {"ENERGY", "TIME", "PARKING_TIME", "FLAT"}
ALLOWED_RESTRICTIONS = {"start_time", "end_time", "day_of_week", "min_duration",
                        "max_duration", "min_power", "max_power", "start_date", "end_date"}
PRIVATE_FIELDS = ("PRIVATE", "STAFF", "EMPLOYEE", "FLEET", "RESIDENT_ONLY",
                  "AUTHORIZED_ONLY", "PERMIT_HOLDERS_ONLY")
NONPUBLIC_NAME = re.compile(
    r"\b(staff only|employees only|fleet depot|private charging|internal test|"
    r"not for public use|car dealership|vehicle dealership|showroom only)\b", re.I
)


def provider(key):
    if key not in PROVIDERS:
        raise ValueError("Unsupported UK PCPR provider")
    return PROVIDERS[key]


def write_json(path, data):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n").encode("utf-8")
    if path.endswith(".gz"):
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as stream:
            stream.write(raw)
        raw = buffer.getvalue()
    target.write_bytes(raw)


def collect(endpoint, authorization, call_budget):
    result = []
    offset = 0
    while True:
        if call_budget[0] >= 28:  # PCPR 30 requests/hour per credential.
            raise RuntimeError("PCPR shared request budget reached; keeping previous snapshot")
        url = BASE + endpoint + "?" + urllib.parse.urlencode({"limit": 1000, "offset": offset})
        retries = 0
        while True:
            if call_budget[0] >= 28:
                raise RuntimeError("PCPR shared request budget reached; keeping previous snapshot")
            call_budget[0] += 1
            req = urllib.request.Request(url, headers={
                "Authorization": authorization, "Accept": "application/json",
                "User-Agent": "TeslaChargeCompanion/9 UK-CPO-PCPR",
            })
            try:
                with urllib.request.urlopen(req, timeout=90) as response:
                    data = json.load(response)
                break
            except urllib.error.HTTPError as err:
                if err.code in (429, 500, 502, 503, 504) and retries < 2:
                    delay = min(120, 15 * 2 ** retries)
                    retry_after = (err.headers or {}).get("Retry-After")
                    if retry_after and str(retry_after).isdigit():
                        delay = max(delay, min(300, int(retry_after)))
                    retries += 1
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"{endpoint}: HTTP {err.code}; keeping previous snapshot") from None
        if not isinstance(data, dict) or data.get("status_code", 1000) != 1000 \
                or not isinstance(data.get("data"), list):
            raise RuntimeError(f"{endpoint}: invalid PCPR envelope; keeping previous snapshot")
        page = data["data"]
        result.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
        time.sleep(1)
    return result


def label(item):
    return str(item.get("name") or "").strip() if isinstance(item, dict) else str(item or "").strip()


def normalized(text):
    return re.sub(r"[^a-z0-9]", "", str(text).casefold())


def eligible_location(loc, cfg):
    if loc.get("country_code") != "GB" or str(loc.get("country") or "").upper() not in ("GB", "GBR"):
        return "outside_UK"
    operator = normalized(label(loc.get("operator")))
    if not operator or not any(operator == alias or operator.startswith(alias)
                               for alias in cfg["aliases"]):
        return "wrong_declared_CPO"
    if loc.get("publish") is not True:
        return "not_explicitly_published"
    for key in ("access_type", "access", "parking_type"):
        value = str(loc.get(key) or "").upper()
        if any(flag in value for flag in PRIVATE_FIELDS):
            return "nonpublic_access"
    if NONPUBLIC_NAME.search(str(loc.get("name") or "")):
        return "nonpublic_location_name"
    for facility in loc.get("facilities") or []:
        name = str(facility.get("code") if isinstance(facility, dict) else facility).upper()
        if "DEALERSHIP" in name:
            return "dealership"
    try:
        coords = loc["coordinates"]
        lat, lon = float(coords["latitude"]), float(coords["longitude"])
    except (KeyError, ValueError, TypeError):
        return "missing_coordinates"
    if not (49 <= lat <= 61 and -9 <= lon <= 3):
        return "outside_UK_bounds"
    return None


def make_tariff(raw):
    if raw.get("country_code") != "GB" or raw.get("currency") != "GBP":
        return None, "non_GBP_UK_tariff"
    if not isinstance(raw.get("elements"), list) or not raw["elements"]:
        return None, "missing_elements"
    result = copy.deepcopy(raw)
    for el in result["elements"]:
        if not isinstance(el, dict):
            return None, "malformed_element"
        restrictions = el.get("restrictions") or {}
        if not isinstance(restrictions, dict) or set(restrictions) - ALLOWED_RESTRICTIONS:
            return None, "unsupported_restrictions"
        pcs = el.get("price_components")
        if not isinstance(pcs, list) or not pcs:
            return None, "missing_components"
        for component in pcs:
            if not isinstance(component, dict) or component.get("type") not in ALLOWED_COMPONENTS:
                return None, "unsupported_component"
            try:
                price = Decimal(str(component["price"]))
                vat = Decimal(str(component["vat"])) if component.get("vat") is not None else Decimal("20")
                step = Decimal(str(component.get("step_size", 1)))
                if not all(x.is_finite() for x in (price, vat, step)) \
                        or price < 0 or vat < 0 or vat > 100 or step < 0 \
                        or (step == 0 and component["type"] != "FLAT"):
                    raise ValueError("invalid price/VAT/step")
            except (ValueError, KeyError, TypeError, InvalidOperation):
                return None, "invalid_component_values"
            component["sourcePriceExVat"] = float(price)
            component["tccVatRateAppliedPct"] = float(vat)
            component["tccVatOrigin"] = "explicit_OCPI" if component.get("vat") is not None else "UK_public_20_default"
            component["price"] = float((price * (Decimal(1) + vat / 100)).quantize(Decimal("0.000001")))
            component["vat"] = None  # already included; do not charge again
    result["tccPriceBasis"] = "GBP_including_public_UK_VAT"
    result["tccSourcePriceBasis"] = "OCPI_2.2.1_excluding_VAT"
    return result, None


def stage(locations, tariffs, stamp, cfg):
    keys = collections.defaultdict(list)
    for tariff in tariffs:
        if isinstance(tariff, dict):
            keys[(tariff.get("country_code"), tariff.get("party_id"), str(tariff.get("id") or ""))].append(tariff)
    operator_names = collections.Counter(label(x.get("operator")) for x in locations if isinstance(x, dict))
    excluded = collections.Counter()
    rejected = collections.Counter()
    missing = set()
    safe_locs = []
    used = {}
    seen_locs, seen_connectors = set(), set()
    connector_count, priced_count = 0, 0
    for raw in locations:
        if not isinstance(raw, dict):
            excluded["malformed_location"] += 1
            continue
        reason = eligible_location(raw, cfg)
        if reason:
            excluded[reason] += 1
            continue
        key = (raw.get("country_code"), raw.get("party_id"), str(raw.get("id") or ""))
        if not key[1] or not key[2] or key in seen_locs:
            excluded["duplicate_or_missing_location_identity"] += 1
            continue
        seen_locs.add(key)
        loc = copy.deepcopy(raw)
        kept_evses = []
        for evse in loc.get("evses") or []:
            if not isinstance(evse, dict) or str(evse.get("status") or "").upper() == "REMOVED":
                excluded["removed_or_invalid_evse"] += 1
                continue
            eid = str(evse.get("evse_id") or evse.get("uid") or "").strip()
            if not eid:
                excluded["missing_evse_identity"] += 1
                continue
            e = copy.deepcopy(evse)
            kept_connectors = []
            for conn in e.get("connectors") or []:
                if not isinstance(conn, dict) or not str(conn.get("id") or ""):
                    excluded["missing_connector_identity"] += 1
                    continue
                identity = (key, eid, str(conn["id"]))
                if identity in seen_connectors:
                    excluded["duplicate_connector"] += 1
                    continue
                seen_connectors.add(identity)
                c = copy.deepcopy(conn)
                rawrefs = c.get("tariff_ids") or []
                refs = [str(r) for r in rawrefs if r is not None] if isinstance(rawrefs, list) else []
                c["sourceTariffIds"] = refs
                verified = []
                if len(refs) != len(set(refs)):
                    rejected["duplicate_tariff_reference"] += 1
                else:
                    for ref in refs:
                        matches = keys.get((key[0], key[1], ref), [])
                        if len(matches) != 1:
                            rejected["missing_or_ambiguous_exact_tariff"] += 1
                            missing.add(ref)
                            continue
                        tariff, why = make_tariff(matches[0])
                        if why:
                            rejected[why] += 1
                        else:
                            used[(key[0], key[1], ref)] = tariff
                            verified.append(ref)
                # A connector with one unresolved tariff reference is unpriced.
                c["tariff_ids"] = verified if len(verified) == len(refs) else []
                connector_count += 1
                priced_count += bool(c["tariff_ids"])
                kept_connectors.append(c)
            if kept_connectors:
                e["connectors"] = kept_connectors
                kept_evses.append(e)
        if kept_evses:
            loc["evses"] = kept_evses
            safe_locs.append(loc)
        else:
            excluded["no_valid_evses"] += 1
    if not safe_locs:
        raise RuntimeError(f"No public {cfg['name']} CPO stations confirmed; operators: {dict(operator_names)}")
    used_keys = {(loc["country_code"], loc["party_id"], tid)
                 for loc in safe_locs for evse in loc["evses"]
                 for c in evse["connectors"] for tid in c["tariff_ids"]}
    slug = cfg["slug"]
    staged = {
        "country": "GB", "collectedAt": stamp, "source": f"{cfg['name']} official PCPR",
        "integrationStatus": "cpo_direct_exact_connector_vat_inclusive_staged",
        "sources": [{"id": cfg["id"], "name": cfg["name"], "country": "GB",
                     "pricingScope": "cpo_direct_pcpr", "locations": safe_locs,
                     "tariffs": [used[key] for key in sorted(used_keys)]}],
    }
    report = {
        "country": "GB", "provider": cfg["name"], "collectedAt": stamp,
        "sourceLocations": len(locations), "sourceTariffs": len(tariffs),
        "publicCpoLocations": len(safe_locs), "publicConnectors": connector_count,
        "pricedExactConnectors": priced_count,
        "unpricedPublicConnectors": connector_count - priced_count,
        "operatorNamesInTokenFeed": dict(operator_names),
        "excluded": dict(excluded), "blockedTariffReasons": dict(rejected),
        "missingOrAmbiguousTariffRefs": sorted(missing)[:100],
        "credentialPersisted": False, "publishedToV9": False,
        "readyForV9Review": bool(priced_count), "status": "staged_for_audit_not_live",
        "rawPath": f"data/national/uk_{slug}_pcpr.json.gz",
        "stagedPath": f"data/national/uk_{slug}_pcpr_v9.json.gz",
    }
    return staged, report


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uk_pcpr_cpo_collect.py allego_uk|source_ev")
    cfg = provider(sys.argv[1])
    token = os.environ.get(cfg["secret"], "").strip()
    if not token:
        raise SystemExit(f"Missing Actions secret {cfg['secret']} (never print credentials)")
    authorization = token if token.lower().startswith(("token ", "bearer ")) else "Token " + token
    budget = [0]  # budget shared across locations and tariffs
    locations = collect("locations", authorization, budget)
    tariffs = collect("tariffs", authorization, budget)
    if not locations:
        raise RuntimeError(f"{cfg['name']} feed contained no locations; prior snapshot retained")
    stamp = datetime.now(timezone.utc).isoformat()
    staged, audit = stage(locations, tariffs, stamp, cfg)
    audit["apiRequests"] = {"total": budget[0], "maxPerHour": 30}
    slug = cfg["slug"]
    write_json(f"data/national/uk_{slug}_pcpr.json.gz",
               {"source": f"{cfg['name']} PCPR", "collectedAt": stamp,
                "locations": locations, "tariffs": tariffs})
    write_json(f"data/national/uk_{slug}_pcpr_v9.json.gz", staged)
    write_json(f"reports/uk/{slug}-pcpr-latest.json", audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
