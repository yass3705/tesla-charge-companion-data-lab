#!/usr/bin/env python3
"""Build a research-grade national A2A direct-tariff candidate joined to PUN.

Source of current direct consumer price/status: A2A public e-moving map/detail API.
Geographic/technical backbone: normalized official PUN artifact.

Fail-closed rules:
- exact OCPI EVSE-ID joins are preferred;
- a legacy-provider fallback is rankable only when the plug suffix resolves to
  exactly one PUN EVSE, that PUN EVSE belongs to A2A (partyId A2M), and the A2A
  map coordinate is within 250 m of the PUN EVSE coordinate;
- malformed/missing price or penalty is retained but not guessed;
- duplicate A2A representations of the same PUN EVSE are accepted only when the
  direct tariff components agree; conflicts are blocked;
- source power differences never overwrite PUN technical power.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE_PAGE = "https://e-movinghub.a2a.it/acEicp/publicMapCMS.action"
MAP_ENDPOINT = "jsonGetMapDashboard"
DETAIL_ENDPOINT = "jsonGetCuFromAlias"
DEFAULT_OUT = Path("data/national/a2a_direct_stations_italy.json.gz")
DEFAULT_REPORT = Path("data/reports/a2a_italy_national_report.json")
PRICE_RE = re.compile(r"(?P<value>\d+(?:[\.,]\d+)?)\s*€\s*/\s*kWh", re.I)
MINUTE_RE = re.compile(r"(?P<value>\d+(?:[\.,]\d+)?)\s*€\s*/\s*min(?:\.|uto|ute)?", re.I)
LEGACY_GEO_MAX_M = 250.0


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fnum(value):
    try:
        x = float(str(value).replace(",", "."))
        return x if math.isfinite(x) else None
    except Exception:
        return None


def parse_rate(text, rx):
    if text in (None, ""):
        return None
    m = rx.search(str(text))
    return round(float(m.group("value").replace(",", ".")), 6) if m else None


def is_a2a_owned(item):
    ap = item.get("assetProvider") if isinstance(item.get("assetProvider"), dict) else {}
    operator = str(ap.get("operatore") or item.get("operator") or "").upper()
    return ap.get("external") is False or "A2A" in operator


def browser_post(driver, endpoint, payload, timeout_s=45):
    script = """
      const endpoint=arguments[0], payload=arguments[1], done=arguments[2];
      fetch(endpoint,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json;charset=utf-8'},body:JSON.stringify(payload)})
        .then(async r=>{const t=await r.text(); let d=null; try{d=JSON.parse(t)}catch(_){}; done({ok:r.ok,status:r.status,data:d,error:d===null?t.slice(0,300):null});})
        .catch(e=>done({ok:false,status:null,data:null,error:String(e)}));
    """
    driver.set_script_timeout(timeout_s)
    return driver.execute_async_script(script, endpoint, payload)


def browser_detail_batch(driver, aliases, concurrency=12, timeout_s=180):
    script = """
      const endpoint=arguments[0], aliases=arguments[1], concurrency=arguments[2], done=arguments[3];
      let idx=0; const out=new Array(aliases.length);
      async function worker(){
        while(true){
          const i=idx++; if(i>=aliases.length) return;
          const alias=aliases[i];
          try{
            const r=await fetch(endpoint,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json;charset=utf-8'},body:JSON.stringify({aliasCu:alias})});
            const t=await r.text(); let d=null; try{d=JSON.parse(t)}catch(_){}
            out[i]={alias,ok:r.ok,status:r.status,data:d,error:d===null?t.slice(0,200):null};
          }catch(e){out[i]={alias,ok:false,status:null,data:null,error:String(e)}}
        }
      }
      Promise.all(Array.from({length:Math.min(concurrency,aliases.length)},()=>worker())).then(()=>done(out));
    """
    driver.set_script_timeout(timeout_s)
    result = driver.execute_async_script(script, DETAIL_ENDPOINT, aliases, concurrency)
    return result if isinstance(result, list) else []


def evse_suffix(evse_id):
    parts = str(evse_id or "").split("*", 2)
    return parts[2] if len(parts) == 3 else None


def load_pun(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    evses = {str(e.get("evseId")): e for e in data.get("evses", []) if e.get("evseId")}
    suffix_idx = defaultdict(list)
    for e in evses.values():
        suffix = evse_suffix(e.get("evseId"))
        if suffix:
            suffix_idx[suffix].append(e)
    stations = {str(s.get("stationId")): s for s in data.get("stations", []) if s.get("stationId")}
    return evses, suffix_idx, stations, data.get("counts", {})


def evse_candidates(provider_id, plug_id):
    provider = str(provider_id or "").strip().upper()
    plug = str(plug_id or "").strip()
    out = []
    if provider and plug:
        out.append(f"IT*{provider}*{plug}")
    if plug and (not provider or provider != "A2M"):
        out.append(f"IT*A2M*{plug}")
    return out


def coords_from_map(item):
    lat = fnum(item.get("lat"))
    lon = fnum(item.get("long"))
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return [lat, lon]


def haversine_m(a, b):
    if not a or not b or len(a) < 2 or len(b) < 2:
        return None
    lat1, lon1 = map(math.radians, [float(a[0]), float(a[1])])
    lat2, lon2 = map(math.radians, [float(b[0]), float(b[1])])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def resolve_pun(pun_idx, suffix_idx, provider_id, plug_id, a2a_coords):
    ids = evse_candidates(provider_id, plug_id)
    for candidate in ids:
        if candidate in pun_idx:
            return pun_idx[candidate], "exact_ocpi_evse_id", None, ids, []

    suffix_hits = [e for e in suffix_idx.get(str(plug_id), []) if str(e.get("partyId") or "").upper() == "A2M"]
    diagnostics = [e.get("evseId") for e in suffix_hits[:10]]
    if len(suffix_hits) == 1 and a2a_coords:
        pun = suffix_hits[0]
        dist = haversine_m(a2a_coords, pun.get("coordinates"))
        if dist is not None and dist <= LEGACY_GEO_MAX_M:
            return pun, "unique_suffix_a2a_party_geo", round(dist, 3), ids, diagnostics
    return None, None, None, ids, diagnostics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pun", required=True)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--batch-size", type=int, default=120)
    ap.add_argument("--concurrency", type=int, default=12)
    args = ap.parse_args()
    pun_idx, pun_suffix_idx, pun_station_idx, pun_counts = load_pun(Path(args.pun))

    opts = Options()
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1600", "--lang=it-IT"):
        opts.add_argument(arg)
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(BASE_PAGE)
        time.sleep(5)
        map_res = browser_post(driver, MAP_ENDPOINT, {"userNation": "IT"}, timeout_s=60)
        if not isinstance(map_res, dict) or not map_res.get("ok") or not isinstance(map_res.get("data"), list):
            raise RuntimeError(f"A2A map failed: {map_res}")
        map_items = [x for x in map_res["data"] if isinstance(x, dict)]
        owned = [x for x in map_items if is_a2a_owned(x) and str(x.get("alias") or "").strip()]
        aliases = list(dict.fromkeys(str(x.get("alias")).strip() for x in owned))
        map_by_alias = {str(x.get("alias")).strip(): x for x in owned}
        detail_results, failures = [], []
        for i in range(0, len(aliases), args.batch_size):
            batch = aliases[i:i + args.batch_size]
            rows = browser_detail_batch(driver, batch, args.concurrency)
            if len(rows) != len(batch):
                got = {str(r.get("alias")) for r in rows if isinstance(r, dict)}
                for alias in batch:
                    if alias not in got:
                        r = browser_post(driver, DETAIL_ENDPOINT, {"aliasCu": alias})
                        rows.append({"alias": alias, **(r if isinstance(r, dict) else {"ok": False, "error": "unexpected"})})
            for r in rows:
                if isinstance(r, dict) and r.get("ok") and isinstance(r.get("data"), dict):
                    detail_results.append(r)
                else:
                    failures.append({"alias": r.get("alias") if isinstance(r, dict) else None, "status": r.get("status") if isinstance(r, dict) else None, "error": r.get("error") if isinstance(r, dict) else "unexpected"})
            print(f"A2A detail progress {min(i + len(batch), len(aliases))}/{len(aliases)} success={len(detail_results)} failed={len(failures)}")
    finally:
        driver.quit()

    raw_candidates, unmatched, malformed_price = [], [], []
    type_counts, status_counts, provider_counts = Counter(), Counter(), Counter()
    match_method_counts = Counter()
    legacy_provider_pairs = Counter()
    for r in detail_results:
        alias = str(r.get("alias") or "")
        d = r["data"]
        m = map_by_alias.get(alias, {})
        a2a_coords = coords_from_map(m)
        apv = d.get("assetProvider") if isinstance(d.get("assetProvider"), dict) else {}
        provider_id = apv.get("providerId")
        type_counts[str(d.get("type") or m.get("type") or "UNKNOWN")] += 1
        status_counts[str(d.get("statusCu") or m.get("statusCu") or "UNKNOWN")] += 1
        provider_counts[str(provider_id or "UNKNOWN")] += 1
        for evse in d.get("evseData") or []:
            if not isinstance(evse, dict):
                continue
            for plug in evse.get("plugs") or []:
                if not isinstance(plug, dict):
                    continue
                plug_id = str(plug.get("plugId") or plug.get("id") or "").strip()
                if not plug_id:
                    continue
                pun, match_method, match_distance_m, ids, suffix_diagnostics = resolve_pun(
                    pun_idx, pun_suffix_idx, provider_id, plug_id, a2a_coords
                )
                energy = parse_rate(plug.get("priceList"), PRICE_RE)
                penalty = parse_rate(plug.get("penaltyList"), MINUTE_RE)
                base = {
                    "a2aAlias": alias,
                    "providerId": provider_id,
                    "plugId": plug_id,
                    "candidateEvseIds": ids,
                    "a2aCoordinates": a2a_coords,
                    "a2aStationType": d.get("type") or m.get("type"),
                    "a2aStationStatus": d.get("statusCu") or m.get("statusCu"),
                    "a2aPlugStatus": plug.get("status"),
                    "a2aPlugType": plug.get("plugType") or plug.get("type"),
                    "a2aMaxPowerKw": fnum(plug.get("maxPower")),
                    "directEnergyEurPerKwh": energy,
                    "directPenaltyEurPerMin": penalty,
                    "rawPriceList": plug.get("priceList"),
                    "rawPenaltyList": plug.get("penaltyList"),
                    "matchMethod": match_method,
                    "matchDistanceM": match_distance_m,
                    "suffixA2aPartyCandidates": suffix_diagnostics,
                }
                if pun is None:
                    unmatched.append(base)
                    continue
                match_method_counts[match_method] += 1
                if match_method == "unique_suffix_a2a_party_geo":
                    source_provider = str(provider_id or "UNKNOWN").upper()
                    target_prefix = str(pun.get("evseId") or "").split("*")[1] if "*" in str(pun.get("evseId") or "") else "UNKNOWN"
                    legacy_provider_pairs[(source_provider, target_prefix)] += 1
                if energy is None:
                    malformed_price.append({**base, "punEvseId": pun.get("evseId")})
                    continue
                raw_candidates.append({
                    **base,
                    "punEvseId": pun.get("evseId"),
                    "punStationId": pun.get("stationId"),
                    "punPartyId": pun.get("partyId"),
                    "punOperator": pun.get("operator"),
                    "punCoordinates": pun.get("coordinates"),
                    "punMaxPowerKw": pun.get("maxPowerKw"),
                    "punOperationalState": pun.get("operationalState"),
                    "punOccupancyState": pun.get("occupancyState"),
                    "punSourceStatus": pun.get("sourceStatus"),
                })

    grouped = defaultdict(list)
    for row in raw_candidates:
        grouped[row["punEvseId"]].append(row)
    evses, conflicts, duplicate_same = [], [], 0
    for evse_id, rows in sorted(grouped.items()):
        signatures = {(r["directEnergyEurPerKwh"], r["directPenaltyEurPerMin"]) for r in rows}
        if len(signatures) > 1:
            conflicts.append({"punEvseId": evse_id, "signatures": sorted([list(x) for x in signatures], key=str), "sourceAliases": sorted({r["a2aAlias"] for r in rows})})
            continue
        if len(rows) > 1:
            duplicate_same += len(rows) - 1
        r = rows[0]
        methods = sorted({str(x.get("matchMethod")) for x in rows if x.get("matchMethod")})
        evses.append({
            "evseId": evse_id,
            "stationId": r["punStationId"],
            "operator": "A2A",
            "partyId": r["punPartyId"],
            "coordinates": r["punCoordinates"],
            "maxPowerKw": r["punMaxPowerKw"],
            "operationalState": r["punOperationalState"],
            "occupancyState": r["punOccupancyState"],
            "sourceStatus": r["punSourceStatus"],
            "directTariff": {
                "energyEurPerKwh": r["directEnergyEurPerKwh"],
                "occupancyEurPerMin": r["directPenaltyEurPerMin"],
                "source": "A2A public e-moving station detail",
                "priceListRaw": r["rawPriceList"],
                "penaltyListRaw": r["rawPenaltyList"],
            },
            "rankableDirectTariff": True,
            "matchMethod": methods[0] if len(methods) == 1 else "+".join(methods),
            "a2aSourceAliases": sorted({x["a2aAlias"] for x in rows}),
        })

    station_ids = sorted({e["stationId"] for e in evses if e.get("stationId")})
    stations = [pun_station_idx[s] for s in station_ids if s in pun_station_idx]
    total_plugs = len(raw_candidates) + len(unmatched) + len(malformed_price)
    safe_matches = len(raw_candidates) + len(malformed_price)
    exact_matches = match_method_counts.get("exact_ocpi_evse_id", 0)
    legacy_matches = match_method_counts.get("unique_suffix_a2a_party_geo", 0)
    exact_rate = exact_matches / total_plugs if total_plugs else 0.0
    safe_rate = safe_matches / total_plugs if total_plugs else 0.0
    rankable_rate = len(evses) / len(grouped) if grouped else 0.0
    legacy_pair_json = {f"{a}->{b}": n for (a, b), n in sorted(legacy_provider_pairs.items())}
    report = {
        "generatedAt": now_iso(),
        "source": {"page": BASE_PAGE, "mapEndpoint": MAP_ENDPOINT, "detailEndpoint": DETAIL_ENDPOINT, "punInput": str(args.pun)},
        "security": {"accountCredentialsUsed": False, "authorizationMaterialPersisted": False, "cookiesPersisted": False, "rechargeOrAuthEndpointsCalled": False},
        "counts": {
            "punInput": pun_counts,
            "a2aMapRecords": len(map_items),
            "a2aOwnedMapRecords": len(owned),
            "uniqueA2aAliases": len(aliases),
            "successfulDetails": len(detail_results),
            "failedDetails": len(failures),
            "parsedPlugs": total_plugs,
            "exactPunMatches": exact_matches,
            "exactPunMatchRate": round(exact_rate, 6),
            "legacySafeSuffixMatches": legacy_matches,
            "safePunMatches": safe_matches,
            "safePunMatchRate": round(safe_rate, 6),
            "unmatchedPlugs": len(unmatched),
            "malformedPriceMatches": len(malformed_price),
            "rawMatchedPricedRows": len(raw_candidates),
            "uniqueMatchedPricedEvse": len(grouped),
            "duplicateSameTariffRows": duplicate_same,
            "conflictingTariffEvse": len(conflicts),
            "rankableEvse": len(evses),
            "rankableStations": len(stations),
            "rankableResolutionRate": round(rankable_rate, 6),
        },
        "a2aTypeCounts": dict(sorted(type_counts.items())),
        "a2aStatusCounts": dict(sorted(status_counts.items())),
        "a2aProviderCounts": dict(sorted(provider_counts.items())),
        "matchMethodCounts": dict(sorted(match_method_counts.items())),
        "legacyProviderPrefixPairs": legacy_pair_json,
        "legacyFallbackPolicy": {"punPartyId": "A2M", "uniqueSuffixRequired": True, "maxGeoDistanceM": LEGACY_GEO_MAX_M},
        "qualityGates": {
            "detailsSuccessRateGte99pct": len(detail_results) >= max(1, int(len(aliases) * 0.99)),
            "safePunJoinRateGte95pct": safe_rate >= 0.95,
            "conflictingTariffEvseZero": len(conflicts) == 0,
            "rankableEvseNonzero": len(evses) > 0,
        },
        "failures": failures[:200],
        "unmatched": unmatched,
        "malformedPriceSample": malformed_price[:100],
        "conflicts": conflicts[:200],
    }
    dataset = {
        "schemaVersion": 2,
        "dataset": "a2a_direct_stations_italy",
        "generatedAt": report["generatedAt"],
        "operator": "A2A",
        "country": "IT",
        "scope": "research-candidate-national-direct-tariff",
        "sources": [BASE_PAGE, "PUN normalized national artifact"],
        "counts": report["counts"],
        "matchPolicy": {
            "rankable": "exact OCPI EVSE ID, or unique suffix + PUN partyId A2M + <=250m coordinate agreement",
            "duplicatePolicy": "same tariff accepted; conflicting tariff blocked",
            "technicalTruth": "PUN power/coordinates/status retained",
        },
        "stations": stations,
        "evses": evses,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        json.dump(dataset, fh, ensure_ascii=False, separators=(",", ":"))
    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(report["qualityGates"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
