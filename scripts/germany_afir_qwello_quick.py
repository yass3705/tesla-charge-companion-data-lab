#!/usr/bin/env python3
"""Fast focused schema probe for the small public Qwello AFIR feed."""
from __future__ import annotations

import gzip
import json
import urllib.request
from collections import Counter

OFFER_ID = "972963216296222720"
URL = f"https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{OFFER_ID}/file/noauth"
UA = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=90) as response:
        if "gzip" in response.headers.get("Content-Encoding", "").lower():
            raw = gzip.GzipFile(fileobj=response).read()
        else:
            raw = response.read()
    return json.loads(raw.decode("utf-8-sig"))


def paths(value, prefix="$", out=None):
    out = out if out is not None else Counter()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            out[path] += 1
            paths(child, path, out)
    elif isinstance(value, list):
        for child in value:
            paths(child, prefix + "[]", out)
    return out


def scalar_hits(value, prefix="$", hits=None):
    hits = hits if hits is not None else []
    if isinstance(value, dict):
        for key, child in value.items():
            p = f"{prefix}.{key}"
            low = key.lower()
            if any(t in low for t in ("evse", "operator", "price", "tariff", "power", "connector", "refill", "station", "status", "available", "payment")):
                if isinstance(child, (str, int, float, bool)) or child is None:
                    hits.append((p, child))
            scalar_hits(child, p, hits)
    elif isinstance(value, list):
        for child in value:
            scalar_hits(child, prefix + "[]", hits)
    return hits


def main():
    data = fetch()
    pub = data["payload"]["aegiEnergyInfrastructureTablePublication"]
    tables = pub.get("energyInfrastructureTable") or []
    sites = []
    for table in tables:
        sites.extend(table.get("energyInfrastructureSite") or [])
    print(f"TCC_QWELLO_SITE_COUNT={len(sites)}")
    for idx, site in enumerate(sites[:3]):
        print(f"TCC_QWELLO_SITE_{idx}=" + json.dumps(site, ensure_ascii=False, separators=(",", ":"))[:14000])
    counter = Counter()
    hits = []
    for site in sites[:50]:
        paths(site, "$site", counter)
        hits.extend(scalar_hits(site, "$site"))
    selected = [(p, c) for p, c in counter.most_common() if any(t in p.lower() for t in (
        "evse", "operator", "price", "tariff", "power", "connector", "refill", "station", "status", "available", "payment"
    ))]
    print("TCC_QWELLO_PATHS=" + json.dumps(selected[:250], ensure_ascii=False))
    dedup = []
    seen = set()
    for p, v in hits:
        item = (p, json.dumps(v, ensure_ascii=False, sort_keys=True))
        if item in seen:
            continue
        seen.add(item)
        dedup.append((p, v))
    print("TCC_QWELLO_VALUES=" + json.dumps(dedup[:250], ensure_ascii=False))


if __name__ == "__main__":
    main()
