#!/usr/bin/env python3
"""Collect guest app location DETAILS for every operator location; exact QR joins only."""
import concurrent.futures
import gzip
import hashlib
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://backend.ck-app-prod.connectedkerb.co.uk"
DATA = "data/national/uk_connected_kerb_app_details.json.gz"
OFFERS = "data/national/uk_connected_kerb_app_direct_offers.json.gz"
REPORT = "reports/uk/connected-kerb-app-collection-latest.json"


class Guest:
    def __init__(self):
        self.lock = threading.Lock()
        self.token = None
        self.device = str(uuid.uuid4())
        self.login()

    def login(self, expired=None):
        with self.lock:
            if expired and expired != self.token:
                return
            req = urllib.request.Request(BASE + "/login/guest", data=json.dumps({"deviceId": self.device,
                "pushToken": None}).encode(), method="POST", headers={"Content-Type": "application/json",
                "Accept": "application/json", "X-App-Version": "4.5.1", "X-Device-ID": self.device})
            with urllib.request.urlopen(req, timeout=45) as response:
                self.token = json.load(response)["accessToken"]

    def get(self, route):
        for attempt in range(3):
            token = self.token
            req = urllib.request.Request(BASE + route, headers={"Authorization": "Bearer " + token,
                "Accept": "application/json", "X-App-Version": "4.5.1", "X-Device-ID": self.device})
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 401 and attempt < 2:
                    self.login(token)
                    continue
                if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError(f"app HTTP {error.code}") from None
            except (OSError, ValueError) as error:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError("app response interrupted or invalid") from None
        raise RuntimeError("app retry limit")


def qr(value):
    return str(value or "").strip().upper()


def distance(a, b):
    lat1, lon1 = a["coordinates"]["latitude"], a["coordinates"]["longitude"]
    lat2, lon2 = b["latitude"], b["longitude"]
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * 6371000


def choose_standard(socket):
    """Do not minimize among FAST/CHEAP/REGULAR or use search placeholders."""
    specifications = socket.get("fullTariffSpecification") or []
    regular = [t for t in specifications if t.get("tariffOption") == "REGULAR"]
    if len(regular) == 1:
        selected = regular[0]
    elif len(specifications) == 1 and specifications[0].get("tariffOption") in (None, "REGULAR"):
        selected = specifications[0]
    else:
        return None, "no_unique_standard_tariff"
    unified = [t for t in socket.get("unifiedTariffs", []) if t.get("id") == selected.get("id")]
    if len(unified) != 1 or not selected.get("id"):
        return None, "no_unique_detailed_tariff"
    slices = unified[0].get("slices") or {}
    energy = slices.get("ENERGY") or []
    if not energy or any(not isinstance(p.get("price"), (int, float)) or p["price"] < 0 for p in energy):
        return None, "missing_energy_slices"
    # Fee dimensions are preserved, but their charging unit must be verified before publication.
    if any(k != "ENERGY" and v for k, v in slices.items()):
        return None, "fee_unit_verification_pending"
    for p in energy:
        if bool(p.get("startTime")) != bool(p.get("endTime")):
            return None, "incomplete_time_window"
    if len(energy) > 1 and any(not p.get("startTime") or not p.get("endTime") for p in energy):
        return None, "multiple_energy_prices_without_windows"
    return {"currency": "GBP", "priceIncludesVat": True, "timeBasis": "UTC",
            "displayTimeZone": "Europe/London", "tariffOption": selected.get("tariffOption", "REGULAR"),
            "appTariffId": selected["id"], "energySlices": energy}, None


def main():
    with gzip.open(ROOT / "data/national/uk_connected_kerb_locations.json.gz", "rt") as f:
        baseline = json.load(f)
    with gzip.open(ROOT / "data/national/uk_connected_kerb_tariffs.json.gz", "rt") as f:
        tariffs = {t["id"]: t for t in json.load(f)["tariffs"]}
    locations = {}
    for loc in baseline["locations"]:
        if loc.get("publish"):
            old = locations.get(loc["id"])
            if old is None or loc.get("last_updated", "") > old.get("last_updated", ""):
                locations[loc["id"]] = loc
    client = Guest()
    deadline = time.monotonic() + 22 * 60
    cache, cache_lock = {}, threading.Lock()

    def fetch(loc):
        if time.monotonic() > deadline:
            return {"operatorLocationId": loc["id"], "error": "collection_budget_reached"}
        probes = list(dict.fromkeys(qr(e.get("physical_reference")) for e in loc.get("evses", []) if e.get("physical_reference")))
        errors = []
        for physical in probes[:3]:
            try:
                found = client.get("/locations/search?" + urllib.parse.urlencode({"qrCode": physical, "exactMatch": "true"}))
                candidates = [l for l in found.get("locations", []) if
                    any(qr(s.get("qrCode")) == physical for s in l.get("sockets", [])) and distance(loc, l) <= 100]
                if len(candidates) != 1:
                    errors.append("no_unique_exact_qr_and_geo_match")
                    continue
                app_id = candidates[0]["id"]
                with cache_lock:
                    detail = cache.get(app_id)
                if detail is None:
                    detail = client.get("/locations/" + urllib.parse.quote(app_id, safe=""))
                    if detail.get("id") != app_id or distance(loc, detail) > 100:
                        errors.append("detail_location_mismatch")
                        continue
                    with cache_lock:
                        cache[app_id] = detail
                return {"operatorLocationId": loc["id"], "lookupQrCode": physical, "location": detail}
            except Exception as error:
                errors.append(str(error) if isinstance(error, RuntimeError) else type(error).__name__)
        return {"operatorLocationId": loc["id"], "error": errors[-1] if errors else "no_physical_reference"}

    details = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch, loc) for loc in locations.values()]
        for future in concurrent.futures.as_completed(futures):
            details.append(future.result())
            if len(details) % 100 == 0:
                print(json.dumps({"processed": len(details), "total": len(locations),
                                  "detailedLocations": sum("location" in r for r in details)}), flush=True)
    offers, unresolved = [], []
    for result in details:
        loc = locations[result["operatorLocationId"]]
        sockets = {}
        if result.get("location"):
            for socket in result["location"].get("sockets", []):
                sockets.setdefault(qr(socket.get("qrCode")), []).append(socket)
        for evse in loc.get("evses", []):
            matches = sockets.get(qr(evse.get("physical_reference")), [])
            for conn in evse.get("connectors", []):
                key = {"locationId": loc["id"], "evseUid": evse["uid"], "evseId": evse.get("evse_id"),
                       "connectorId": conn["id"], "physicalReference": evse.get("physical_reference")}
                reason = result.get("error")
                pricing = None
                if not reason:
                    if len(matches) != 1:
                        reason = "no_unique_exact_socket_match"
                    elif result["location"].get("accessType") != "PUBLIC":
                        reason = "app_access_not_public"
                    else:
                        pricing, reason = choose_standard(matches[0])
                if pricing:
                    # Exact raw operator price concordance, allowing only source decimal rounding.
                    gross = [p["price"] * (1 + p.get("vat", 0) / 100) for tid in conn.get("tariff_ids", [])
                             for e in tariffs.get(tid, {}).get("elements", []) for p in e.get("price_components", [])
                             if p.get("type") == "ENERGY"]
                    if not gross or any(not any(abs(p["price"] - g) <= 0.0002 for g in gross) for p in pricing["energySlices"]):
                        reason = "app_operator_energy_price_disagreement"
                if reason:
                    unresolved.append({**key, "reason": reason})
                else:
                    offers.append({**key, "provider": "Connected Kerb", "source": "operator_app_guest_detail",
                                   "pricingScope": "cpo_direct_standard_guest", "appLocationId": result["location"]["id"],
                                   "appSocketId": matches[0]["id"], "pricing": pricing,
                                   "operatorBaselineCollectedAt": baseline["collectedAt"]})
    now = datetime.now(timezone.utc).isoformat()
    report = {"provider": "Connected Kerb", "collectedAt": now, "operatorBaselineCollectedAt": baseline["collectedAt"],
              "requestedLocations": len(locations), "detailedLocationMatches": sum("location" in r for r in details),
              "failedLocations": [{"id": r["operatorLocationId"], "reason": r["error"]} for r in details if "error" in r],
              "resolvedConnectors": len(offers), "unresolvedConnectors": len(unresolved),
              "unresolvedReasonCounts": dict(Counter(r["reason"] for r in unresolved)),
              "unresolved": unresolved, "searchPricesUsed": False, "credentialsPersisted": False,
              "publishedToV9": False, "resolutionRule": "Exact QR and <=100m geography; standard REGULAR or single unlabelled tariff; full detailed slices; operator gross-price concordance."}
    for path, payload in ((DATA, {"collectedAt": now, "operatorBaselineCollectedAt": baseline["collectedAt"], "records": details}),
                          (OFFERS, {"collectedAt": now, "pricingScope": "cpo_direct_standard_guest", "offers": offers})):
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(target, "wt", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    (ROOT / REPORT).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("unresolved", "failedLocations")}, indent=2))
    if not offers:
        raise SystemExit("No verified app prices; outputs retained for diagnosis")


if __name__ == "__main__":
    main()
