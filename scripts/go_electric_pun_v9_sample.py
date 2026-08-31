#!/usr/bin/env python3
"""Extract a tiny Go Electric sample from the published Italy V9 PUN catalogue.

Read-only. Downloads only the public gzipped Italy V9 physical catalogue from the
main TCC repository and writes a compact sample for exact NextCharge matching.
No charging provider API is called by this script.
"""
from __future__ import annotations

import gzip
import io
import json
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = "https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/refactor/unified-data-engine-v9/data/v9/italy-static/all.json.gz"
TARGET = "Go Electric Stations SRLS"
UA = "TeslaChargeCompanion-DataLab/1.0 (+read-only public GitHub catalogue validation)"


def load_rows() -> list[list]:
    req = urllib.request.Request(SOURCE, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    return json.loads(gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode("utf-8"))


def power_bucket(kw: float) -> str:
    if kw <= 22:
        return "AC_22_or_less"
    if kw <= 60:
        return "DC_23_60"
    if kw <= 150:
        return "DC_61_150"
    return "HPC_over_150"


def main() -> None:
    rows = load_rows()
    matches = [r for r in rows if len(r) > 11 and (str(r[5]).strip() == TARGET or str(r[11]).strip() == TARGET)]
    if not matches:
        raise SystemExit("no Go Electric rows found in published Italy V9 catalogue")

    evse_count = 0
    buckets: dict[str, list[dict]] = defaultdict(list)
    kw_counter: Counter[float] = Counter()
    for r in matches:
        station_id, name, address, lat, lon, operator, _, _, configs, generated_at, status, _ = r[:12]
        parsed_configs = []
        for c in configs or []:
            if not isinstance(c, list) or len(c) < 4:
                continue
            eid = str(c[0])
            kind = str(c[2])
            try:
                kw = float(c[3])
            except (TypeError, ValueError):
                kw = 0.0
            evse_count += 1
            kw_counter[kw] += 1
            parsed_configs.append({"evseId": eid, "kind": kind, "maxPowerKw": kw})
        station_max = max((x["maxPowerKw"] for x in parsed_configs), default=0.0)
        bucket = power_bucket(station_max)
        if len(buckets[bucket]) < 5:
            buckets[bucket].append({
                "stationId": station_id,
                "name": name,
                "address": address,
                "lat": lat,
                "lon": lon,
                "operator": operator,
                "status": status,
                "generatedAt": generated_at,
                "stationMaxPowerKw": station_max,
                "evses": parsed_configs,
            })

    report = {
        "schemaVersion": 1,
        "source": SOURCE,
        "policy": {"readOnly": True, "providerApiCalled": False, "nationalProviderScrape": False},
        "targetOperator": TARGET,
        "stationCount": len(matches),
        "evseCount": evse_count,
        "powerDistributionTop": [{"maxPowerKw": kw, "evseCount": count} for kw, count in kw_counter.most_common(30)],
        "samplesByStationMaxPowerClass": dict(buckets),
    }
    out = Path("artifacts/go_electric_pun_v9_sample.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stationCount": report["stationCount"],
        "evseCount": report["evseCount"],
        "sampleClasses": {k: len(v) for k, v in buckets.items()},
        "firstSamples": {k: v[:2] for k, v in buckets.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
