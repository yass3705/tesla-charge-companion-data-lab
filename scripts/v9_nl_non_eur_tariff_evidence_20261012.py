#!/usr/bin/env python3
"""Read-only evidence for two non-EUR DOT-NL tariff references.

Never converts USD or assumes currency code XXX means a verified free tariff.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

from v9_nl_type2_ccs_scope_audit_20261012 import valid_nl, plug, ACTIVE

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/national/netherlands_dotnl/normalized.json.gz"
REFERENCES = {
    "NL:CPI:NLCPIT2QP*1*0": ("CPI", "USD"),
    "NL:NUO:Free": ("NUO", "XXX"),
}


def components(tariff):
    entries = []
    for i, element in enumerate(tariff.get("elements") or []):
        if not isinstance(element, dict):
            return [], False
        for part in element.get("priceComponents") or []:
            if not isinstance(part, dict):
                return [], False
            entries.append({
                "elementIndex": i,
                "type": part.get("type"),
                "stepSize": part.get("stepSize"),
                "priceInclVat": part.get("priceInclVat"),
                "priceExclVat": part.get("priceExclVat"),
                "restrictions": element.get("restrictions") or {},
            })
    return entries, bool(entries)


def audit(data, source_sha=None):
    tariffs = data.get("tariffs")
    if not isinstance(tariffs, dict):
        raise ValueError("Missing DOT-NL tariff catalog")
    result = {}
    for key, (party, currency) in REFERENCES.items():
        raw = tariffs.get(key)
        if not isinstance(raw, dict):
            raise ValueError("Missing targeted tariff " + key)
        found_currency = str(raw.get("currency") or "").upper()
        if found_currency != currency:
            raise ValueError("Targeted source currency drift for " + key)
        comps, exists = components(raw)
        # Lack of a component is NOT evidence of free charging.
        amounts = [c.get("priceInclVat") for c in comps]
        all_inclusive_zero = exists and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0 for v in amounts
        )
        counts = collections.Counter()
        sample = []
        for station in data.get("stations") or []:
            if not valid_nl(station) or str(station.get("partyId") or "").upper() != party:
                continue
            for evse in station.get("evses") or []:
                if str(evse.get("status") or "UNKNOWN").upper() not in ACTIVE:
                    continue
                for conn in evse.get("connectors") or []:
                    if plug(conn.get("standard")) is None or key not in (conn.get("tariffKeys") or []):
                        continue
                    counts["activeType2CcsOccurrences"] += 1
                    counts[str(conn.get("standard"))] += 1
                    if len(sample) < 100:
                        sample.append({
                            "stationId": station.get("stationId"),
                            "evseId": evse.get("evseId") or evse.get("uid"),
                            "connectorId": conn.get("id"),
                            "powerKw": conn.get("powerKw"),
                            "status": evse.get("status"),
                            "sourceAccess": station.get("access"),
                        })
        result[key] = {
            "partyId": party, "sourceCurrency": found_currency,
            "rawTariffType": raw.get("type"), "rawTariffId": raw.get("id"),
            "rawStartAt": raw.get("startDateTime"), "rawEndAt": raw.get("endDateTime"),
            "elementCount": len(raw.get("elements") or []),
            "components": comps,
            "allNonemptyInclusiveComponentAmountsZero": all_inclusive_zero,
            "zeroAmountsDoNotProvePublicFreeCharging": True,
            "counts": dict(counts), "samples": sample,
            "status": "SOURCE_CURRENCY_UNVERIFIED_DO_NOT_COMPUTE_EUR",
        }
    return {
        "schemaVersion": 1,
        "status": "READ_ONLY_SOURCE_CURRENCY_EVIDENCE",
        "dataObservedAt": data.get("generatedAt"),
        "inputCompressedSha256": source_sha,
        "tariffs": result,
        "publishedToTcc": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=SOURCE)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    with gzip.open(args.source, "rt", encoding="utf-8") as f:
        source = json.load(f)
    doc = audit(source, hashlib.sha256(args.source.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
