#!/usr/bin/env python3
"""Read-only active Type 2/CCS price census after the keep-station policy."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

from dotnl_netherlands_runtime import choose_tariff, date_of
from v9_nl_type2_ccs_scope_audit_20261012 import ACTIVE, plug, valid_nl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/national/netherlands_dotnl/normalized.json.gz"


def scan(data):
    tariffs = data.get("tariffs") or {}
    today = date_of(data.get("generatedAt"))
    if today is None:
        raise ValueError("Missing source date")
    selection_stats = {"unsupportedReasons": collections.Counter(), "ambiguousTariffConnectors": 0}
    compiled, selected = {}, {}
    counts = collections.Counter()
    by_cpo = collections.defaultdict(collections.Counter)
    samples = []
    station_ids = set()
    for station in data.get("stations") or []:
        if not valid_nl(station):
            continue
        sid = str(station.get("stationId") or "")
        if not sid:
            continue
        party = str(station.get("partyId") or "UNKNOWN").upper()
        for evse in station.get("evses") or []:
            if str(evse.get("status") or "").upper() not in ACTIVE:
                continue
            for connector in evse.get("connectors") or []:
                if plug(connector.get("standard")) is None:
                    continue
                station_ids.add(sid)
                key, rules, reason = choose_tariff(connector.get("tariffKeys") or [], tariffs,
                                                   today, selection_stats, compiled, selected)
                if not key:
                    category = "NO_COMPUTABLE_SOURCE_TARIFF"
                else:
                    raw_currency = str(tariffs[key].get("currency") or "").upper()
                    wire_currencies = {str(r[4] or "").upper() for r in rules}
                    category = ("EUR_OFFER" if raw_currency == "EUR" and wire_currencies == {"EUR"}
                                else "CURRENCY_UNVERIFIED")
                    if category == "CURRENCY_UNVERIFIED" and len(samples) < 40:
                        samples.append({"stationId": sid, "evseId": evse.get("evseId"),
                                        "partyId": party, "tariffKey": key,
                                        "sourceCurrency": raw_currency,
                                        "wireCurrencies": sorted(wire_currencies)})
                counts[category] += 1
                by_cpo[party][category] += 1
    counts["totalActiveType2Ccs"] = sum(counts[k] for k in
                                       ("NO_COMPUTABLE_SOURCE_TARIFF", "CURRENCY_UNVERIFIED", "EUR_OFFER"))
    return {
        "schemaVersion": 1,
        "status": "READ_ONLY_NL_POST_POLICY_CENSUS",
        "dataObservedAt": data.get("generatedAt"),
        "uniqueActiveStationIds": len(station_ids),
        "counts": dict(counts),
        "byCpo": {k: dict(v) for k, v in sorted(by_cpo.items())},
        "nonEurSamples": samples,
        "stationsPreservedWhenPriceUnavailable": True,
        "publicAccessIndividuallyVerified": False,
        "publishedToTcc": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blob = args.source.read_bytes()
    with gzip.open(args.source, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    report = scan(data)
    report["inputCompressedSha256"] = hashlib.sha256(blob).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dataObservedAt", "inputCompressedSha256",
                                             "uniqueActiveStationIds", "counts", "byCpo")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
