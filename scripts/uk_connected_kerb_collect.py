#!/usr/bin/env python3
"""Collect operator-supplied Connected Kerb infrastructure API, without secrets in output."""
import argparse
import gzip
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.cpms.connectedkerb.co.uk/api/2.2.1/v1/"
REPORT = "reports/uk/connected-kerb-latest.json"
LOCATIONS = "data/national/uk_connected_kerb_locations.json.gz"
TARIFFS = "data/national/uk_connected_kerb_tariffs.json.gz"


class Client:
    def __init__(self, token):
        if not token or any(c in token for c in "\r\n"):
            raise ValueError("CONNECTED_KERB_TOKEN missing or invalid")
        self.token = token
        self.mode = "as_supplied"

    def get(self, path, page, limit=100):
        url = BASE + path + "?" + urllib.parse.urlencode({"page": page, "limit": limit})
        for attempt in range(5):
            auth = self.token if self.mode == "as_supplied" else "Bearer " + self.token
            req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json",
                                                       "User-Agent": "TeslaChargeCompanion/9 ConnectedKerb"})
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                # Never log the response body or request headers: they may contain credentials.
                if error.code == 401 and self.mode == "as_supplied" and not self.token.lower().startswith(("bearer ", "token ")):
                    self.mode = "bearer"
                    continue
                if error.code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(min(2 ** attempt, 16))
                    continue
                raise RuntimeError(f"Connected Kerb {path} page {page}: HTTP {error.code}") from None
            except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt < 4:
                    time.sleep(min(2 ** attempt, 16))
                    continue
                raise RuntimeError(f"Connected Kerb {path} page {page}: interrupted response after retries") from None
        raise RuntimeError("Connected Kerb request retry limit exceeded")


def collect(client, path, identity):
    rows, seen, page = [], set(), 1
    expected = None
    while page <= 2000:
        payload = client.get(path, page)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError(f"{path}: unexpected API response shape")
        pagination = payload.get("pagination") or {}
        total = pagination.get("totalCount")
        if total is not None:
            total = int(total)
            if expected is not None and total != expected:
                raise ValueError(f"{path}: inventory changed during pagination; retry full collection")
            expected = total
        batch = payload["data"]
        for row in batch:
            key = str(row.get(identity) or "")
            if not key or key in seen:
                raise ValueError(f"{path}: missing or repeated object ID on page {page}")
            seen.add(key)
            rows.append(row)
        pages = pagination.get("totalPages")
        done = (pages is not None and page >= int(pages)) or (expected is not None and len(rows) >= expected)
        if done or not batch:
            if expected is not None and len(rows) != expected:
                raise ValueError(f"{path}: collected {len(rows)} objects, expected {expected}")
            return rows, {"pages": page, "reportedTotal": expected, "count": len(rows)}
        page += 1
        time.sleep(0.1)
    raise ValueError(f"{path}: pagination limit exceeded")


def tariff_ids(conn):
    # Swagger contains the typo 'tariif_ids'; preserve and support both spellings.
    return sorted({str(v) for key in ("tariff_ids", "tariif_ids") for v in (conn.get(key) or [])})


def audit(locations, tariffs):
    tariff_map = {str(t["id"]): t for t in tariffs}
    evses = connectors = linked = resolved = 0
    refs, missing, currencies, components = set(), set(), Counter(), Counter()
    publish = Counter()
    for loc in locations:
        publish[str(loc.get("publish"))] += 1
        for evse in loc.get("evses") or []:
            evses += 1
            for conn in evse.get("connectors") or []:
                connectors += 1
                ids = tariff_ids(conn)
                refs.update(ids)
                missing.update(set(ids) - tariff_map.keys())
                linked += bool(ids)
                resolved += bool(ids) and all(i in tariff_map for i in ids)
    for tariff in tariffs:
        currencies[str(tariff.get("currency"))] += 1
        for element in tariff.get("elements") or []:
            for pc in element.get("price_components") or []:
                components[str(pc.get("type"))] += 1
    return {"evses": evses, "connectors": connectors, "connectorsWithTariffRefs": linked,
            "connectorsWithResolvedTariffRefs": resolved, "connectorsWithoutTariffRefs": connectors - linked,
            "missingTariffIds": sorted(missing), "referencedTariffs": len(refs),
            "currencies": dict(currencies), "priceComponentTypes": dict(components),
            "publishCounts": dict(publish), "countryCounts": dict(Counter(l.get("country_code") for l in locations))}


def save(path, payload):
    dest = ROOT / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if str(path).endswith(".gz"):
        with gzip.open(dest, "wt", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    else:
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_progress():
    report = json.loads((ROOT / REPORT).read_text())
    path = "docs/uk-cpo-progress-2026-09.json"
    progress = json.loads((ROOT / path).read_text())
    row = next(r for r in progress["cpos"] if r["name"] == "Connected Kerb")
    row.update({"status": "partial_api_collected_tariff_scope_pending", "access": "operator_supplied_api_token",
                "documentation": "https://api.cpms.connectedkerb.co.uk/api-docs", "baseUrl": BASE,
                "datasetLocations": LOCATIONS, "datasetTariffs": TARIFFS, "report": REPORT,
                "requestStatus": "token_received_2026-10-07", "validatedCounts": report["counts"],
                "evidence": "Authenticated API snapshot persisted with pagination and exact connector tariff-reference audit. Retail/ad-hoc tariff semantics still require verification.",
                "next": "Validate direct public tariff scope, VAT and time restrictions before V9 pricing publication."})
    progress["updatedAt"] = report["collectedAt"]
    # Preserve every other operator's current data during concurrent publishing.
    if isinstance(progress.get("currentStatusCounts"), dict):
        old_counts = progress["currentStatusCounts"]
        progress["currentStatusCounts"] = {
            "asOf": report["collectedAt"][:10],
            **dict(Counter(r.get("status") for r in progress["cpos"])),
            "canonicalEntries": len(progress["cpos"]),
            "semanticCpos": old_counts.get("semanticCpos", len(progress["cpos"])),
        }
    save(path, progress)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-progress", action="store_true")
    args = parser.parse_args()
    if args.update_progress:
        update_progress()
        return
    client = Client(os.environ.get("CONNECTED_KERB_TOKEN", "").strip())
    locations, lp = collect(client, "charging-pools", "id")
    tariffs, tp = collect(client, "tariffs", "id")
    if not locations or not tariffs:
        raise ValueError("Empty locations or tariffs; previous snapshot retained")
    counts = {"locations": len(locations), "tariffs": len(tariffs), **audit(locations, tariffs)}
    now = datetime.now(timezone.utc).isoformat()
    report = {"provider": "Connected Kerb", "country": "GB", "collectedAt": now,
              "counts": counts, "pagination": {"locations": lp, "tariffs": tp},
              "authHeader": "Authorization", "authMode": client.mode, "secretValuePersisted": False,
              "tariffScope": "operator_API_scope_pending_retail_ad_hoc_verification",
              "publishedToV9": False, "documentation": "https://api.cpms.connectedkerb.co.uk/api-docs"}
    # Prevent an API echo of the credential from entering a public snapshot.
    for payload in (locations, tariffs, report):
        if client.token in json.dumps(payload):
            raise ValueError("Credential detected in API output; publication stopped")
    for path, key, values in ((LOCATIONS, "locations", locations), (TARIFFS, "tariffs", tariffs)):
        save(path, {"source": "Connected Kerb operator API", "collectedAt": now, key: values})
    save(REPORT, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
