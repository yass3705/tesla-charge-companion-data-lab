#!/usr/bin/env python3
"""Reconstruct immutable Tesla Mac country-batch audit evidence from Git history.

- Source snapshots are pinned to the exact public Mac commit and its parent.
- Publication timestamp is never presented as an observed tariff timestamp.
- Existing immutable per-batch records are not overwritten.
- A one-off 8/9 October verification proves the four batches reached both V9
  mirrors at the historical 10 October 00:31 Europe/Paris synchronization.
- Read-only toward the Mac source, V9, and the independent SuC dataset.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/tesla/history"
BATCH_DIR = OUT / "mac-country-batches"
MAC_REPO = "yass3705/tesla-charge-companion-stable"
RAW = "https://raw.githubusercontent.com/" + MAC_REPO + "/"
API = "https://api.github.com/repos/" + MAC_REPO
START = "2026-10-07T00:00:00Z"
TZ = ZoneInfo("Europe/Paris")
COUNTRY = {
    "france": "FR", "italy": "IT", "switzerland": "CH", "germany": "DE",
    "spain": "ES", "netherlands": "NL", "united_kingdom": "GB",
    "morocco": "MA", "belgium": "BE", "luxembourg": "LU", "portugal": "PT",
}
TCC = ("FR", "IT", "CH", "DE", "ES", "NL", "GB", "MA", "BE")
PATTERN = re.compile(r"^chore\(stations\): publish ([a-z_]+) automated lot update #(\d+)$")
OCT07_EVENTS = {
    "262f2c5e52b63c0b4312cb06fce40dea23e41a27": ("FR", "2026-10-07"),
    "5f0a6ca764789ce2443d91aa6256e8c2d68ff7b6": ("PT", "2026-10-07"),
    "ebe3a2f23aefcaf398f625cedbfe78b568cabe97": ("MA", "2026-10-07"),
}
# The Morocco update is an empty Git commit; path-filtered history omits it.
# Keep that historical SHA pinned even when a later batch supersedes the manifest.
EMPTY_COMMIT_SEEDS = ("ebe3a2f23aefcaf398f625cedbfe78b568cabe97",)
OCT_EVENTS = {
    "d2285e2c72fe2398e7a08a9e40560f5327f344e8": ("ES", "2026-10-08"),
    "f9a9bc53d87f3881ee8a0d8b2fde77fc2d4493eb": ("IT", "2026-10-09"),
    "8c3abb3ea9d1f72d5541e0e60c5f15c267214feb": ("CH", "2026-10-09"),
    "c37e7717d4a19036b49e6c129c2bd00485b900f6": ("GB", "2026-10-09"),
}
OCT_SYNC = "4877705d2cae83e0cec9e7ae474f10dfa4d78d46"


def get(url, limit=24_000_000):
    headers = {"User-Agent": "TCC-Mac-Historical-Country-Audit/1.0"}
    if url.startswith(API) and os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=100) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("Oversized remote response: " + url)
    return data


def api_json(path):
    return json.loads(get(API + path))


def catalogue(sha, path="data/tesla_stations.json"):
    data = get(RAW + sha + "/" + path)
    rows = json.loads(data)
    if not isinstance(rows, list) or len(rows) < 1000:
        raise RuntimeError("Unexpected Mac catalogue shape for " + sha)
    return rows, hashlib.sha256(data).hexdigest()


def fingerprint(st):
    obj = {
        "pricing": st.get("pricing"),
        "chargingConfigurations": [
            {"id": c.get("id"), "powerKw": c.get("powerKw"), "pricing": c.get("pricing")}
            for c in (st.get("chargingConfigurations") or []) if isinstance(c, dict)
        ],
    }
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode()).hexdigest()


def index(rows):
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("Unexpected non-object station")
        key = (row.get("countryCode"), str(row.get("id")))
        if not key[0] or not row.get("id") or key in result:
            raise RuntimeError("Missing/duplicate Mac station key " + repr(key))
        result[key] = row
    return result


def catalog_stats(rows):
    totals = collections.Counter()
    for row in rows:
        totals[row.get("countryCode") or "?"] += 1
    return dict(sorted(totals.items()))


def country_stats(rows, code):
    stations = [st for st in rows if st.get("countryCode") == code]
    modes = collections.Counter()
    no_price = 0
    configs_total = 0
    configs_priced = 0
    observed = 0
    for st in stations:
        if st.get("sourceObservedAt"):
            observed += 1
        configs = st.get("chargingConfigurations") or [st]
        for cfg in configs:
            configs_total += 1
            p = cfg.get("pricing") or st.get("pricing") or {}
            rules = p.get("rules") if isinstance(p, dict) else None
            if not isinstance(rules, list) or not rules:
                no_price += 1
                continue
            configs_priced += 1
            for rule in rules:
                if isinstance(rule, dict):
                    modes[rule.get("billing") or "unspecified"] += 1
    return {"stations": len(stations), "chargingConfigurations": configs_total,
            "pricedConfigurations": configs_priced,
            "configurationsWithoutStructuredTariff": no_price,
            "ruleBillingOccurrences": dict(modes),
            "stationsWithActualSourceObservedAt": observed}


def batch_history():
    commits = []
    for page in range(1, 12):
        arr = api_json("/commits?path=data%2Ftesla_stations.json&since=" + START +
                       "&per_page=100&page=" + str(page))
        if not isinstance(arr, list):
            raise RuntimeError("Unexpected GitHub commits response")
        commits += arr
        if len(arr) < 100:
            break
    else:
        raise RuntimeError("Mac commit pagination exceeded; revise START")
    # A published Mac lot may be an empty commit (e.g. Morocco #12).
    # Enrich path-filtered history with the current country publication manifest
    # plus permanent historical no-op seeds, verifying the actual GitHub commit.
    commit_shas = {c["sha"] for c in commits}
    manifest = json.loads(get(RAW + "main/data/tesla-mac-catalogue-publication.json"))
    listed_sha = [v.get("lastMacCountryBatch", {}).get("commitSha")
                  for v in manifest.get("countries", {}).values()]
    for sha in dict.fromkeys([*EMPTY_COMMIT_SEEDS, *listed_sha]):
        if not sha or sha in commit_shas:
            continue
        record = api_json("/commits/" + sha)
        if record.get("sha") != sha:
            raise RuntimeError("Unexpected GitHub Mac commit identity: " + str(sha))
        if record["commit"]["committer"]["date"] >= START:
            commits.append(record)
            commit_shas.add(sha)
    matches = []
    for c in commits:
        message = (c.get("commit") or {}).get("message", "").splitlines()[0]
        match = PATTERN.match(message)
        if not match:
            continue
        if match.group(1) not in COUNTRY:
            raise RuntimeError("Unrecognized Mac country in " + message)
        parents = c.get("parents") or []
        if len(parents) != 1:
            raise RuntimeError("Mac batch commit without exactly one parent")
        matches.append({"sha": c["sha"], "parent": parents[0]["sha"],
                        "message": message, "country": COUNTRY[match.group(1)],
                        "lot": int(match.group(2)),
                        "dateUTC": c["commit"]["committer"]["date"]})
    return sorted(matches, key=lambda item: (item["dateUTC"], item["sha"]))


def process_batch(c):
    sha = c["sha"]
    country = c["country"]
    dest = BATCH_DIR / country / (sha + ".json")
    if dest.exists():
        existing = json.loads(dest.read_text(encoding="utf8"))
        if existing.get("commitSha") != sha or existing.get("country") != country:
            raise RuntimeError("Existing immutable batch collision: " + str(dest))
        return existing, False
    after, digest = catalogue(sha)
    before, prior_digest = catalogue(c["parent"])
    latest = index(after)
    prior = index(before)
    old_group = {k: st for k, st in prior.items() if k[0] == country}
    new_group = {k: st for k, st in latest.items() if k[0] == country}
    old_keys, new_keys = set(old_group), set(new_group)
    common = old_keys & new_keys
    changed = [k for k in common if fingerprint(prior[k]) != fingerprint(latest[k])]
    metadata_only = [k for k in common if prior[k] != latest[k] and k not in changed]
    other_country_rows = sum(
        prior.get(k) != latest.get(k) for k in (set(prior) | set(latest))
        if k[0] != country
    )
    stamp = dt.datetime.fromisoformat(c["dateUTC"].replace("Z", "+00:00"))
    local_day = stamp.astimezone(TZ).date().isoformat()
    row = {
        "schemaVersion": 1,
        "type": "historical_mac_country_batch_audit",
        "repository": MAC_REPO,
        "commitSha": sha, "parentSha": c["parent"],
        "country": country, "lot": c["lot"],
        "publishedAtUTC": c["dateUTC"],
        "publishedAtEuropeParis": stamp.astimezone(TZ).isoformat(),
        "localDay": local_day, "commitMessage": c["message"],
        "canonicalAtCommit": {"path": "data/tesla_stations.json",
                              "sha256": digest, "stationsAllCountries": len(after),
                              "stationsByCountry": catalog_stats(after),
                              "tccCountries": list(TCC)},
        "parentCanonicalSha256": prior_digest,
        "publicationChangedCanonicalBytes": digest != prior_digest,
        "batchWithNoCatalogueChanges": digest == prior_digest,
        "countryBefore": country_stats(before, country),
        "countryAfter": country_stats(after, country),
        "delta": {"addedStations": len(new_keys - old_keys),
                  "removedStations": len(old_keys - new_keys),
                  "changedPricingStationRecords": len(changed),
                  "changedOtherStationMetadataOnly": len(metadata_only),
                  "unchangedStationRecords": len(common) - len(changed) - len(metadata_only),
                  "changedOutsideTargetCountry": other_country_rows},
        "quality": {"countryHasStations": bool(new_group),
                    "allTccCountriesPresent": all(catalog_stats(after).get(k, 0) > 0 for k in TCC),
                    "noOtherCountryRowsModified": other_country_rows == 0,
                    "sourceCataloguesParsed": True},
        "interpretation": {
            "publishedAt": "GitHub publication date, NOT an observed station tariff timestamp",
            "sourceObservedAt": "Only explicit source observation timestamp is evidence of observation",
            "sourcePreference": "Mac recent-under-10-days for the updated country as of this batch; Morocco always Mac",
            "v9": "Does not assert V9 mirrors were synchronized at this instant; checked separately",
            "suc": "SuC prices were not substituted or rewritten",
            "noOp": "A successful batch publication with an identical before/after catalogue is NOT a successful tariff data refresh"},
        "outputStatus": "historical_evidence_archived_not_tariff_publication",
    }
    if not row["quality"]["countryHasStations"] or not row["quality"]["allTccCountriesPresent"]:
        raise RuntimeError("Historical Mac batch missing mandatory country data: " + sha)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    return row, True


def verify_oct_sync(events):
    path = OUT / "2026-10-08_09-retroactive-reconciliation.json"
    if path.exists():
        return
    rows = [events.get(sha) for sha in OCT_EVENTS]
    if any(x is None for x in rows):
        raise RuntimeError("Missing one or more historical Oct 8/9 batch records")
    for sha, (cc, date) in OCT_EVENTS.items():
        row = events[sha]
        if (row["country"], row["localDay"]) != (cc, date):
            raise RuntimeError("Historical country/date mismatch for " + sha)
    mac, mac_sha = catalogue(OCT_SYNC)
    prod, prod_sha = catalogue(OCT_SYNC, "v9-production-runtime/data/tesla_stations.json")
    test, test_sha = catalogue(OCT_SYNC, "v9-test/data/tesla_stations.json")
    if mac_sha != prod_sha or mac_sha != test_sha:
        raise RuntimeError("Historical Oct 10 00:31 mirrors do not match canonical Mac")
    latest_before_sync = events["c37e7717d4a19036b49e6c129c2bd00485b900f6"]
    if latest_before_sync["canonicalAtCommit"]["sha256"] != mac_sha:
        raise RuntimeError("Unexpected Mac catalogue mutation before sync commit")
    report = {
        "schemaVersion": 1,
        "scopeLocalDays": ["2026-10-08", "2026-10-09"],
        "validatedMacCountryBatches": [
            {"country": x["country"], "lot": x["lot"], "commitSha": x["commitSha"],
             "publishedAtEuropeParis": x["publishedAtEuropeParis"],
             "stationsAfterBatch": x["countryAfter"]["stations"],
             "newStations": x["delta"]["addedStations"],
             "removedStations": x["delta"]["removedStations"],
             "changedPricingStationRecords": x["delta"]["changedPricingStationRecords"]}
            for x in rows],
        "syncEvidence": {"commitSha": OCT_SYNC,
                         "committedAtUTC": "2026-10-09T22:31:40Z",
                         "committedAtEuropeParis": "2026-10-10T00:31:40+02:00",
                         "canonicalSha256": mac_sha,
                         "productionMirrorSha256": prod_sha,
                         "testMirrorSha256": test_sha,
                         "copiesByteIdentical": True,
                         "stations": len(mac),
                         "stationCountryCounts": catalog_stats(mac)},
        "scope": "Historical audit restoration, not price recalculation or re-publication",
        "validation": {
            "allFourCountryBatchesPresent": True,
            "macAndBothV9MirrorsMatchedAtRecordedSync": True,
            "batchCountsComparedToParentSnapshots": True,
            "timestampIsPublicationNotObservedPrice": True},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def verify_oct07_sync(events):
    path = OUT / "2026-10-07-retroactive-reconciliation.json"
    rows = []
    for sha, (country, local_day) in OCT07_EVENTS.items():
        row = events.get(sha)
        if row is None or (row["country"], row["localDay"]) != (country, local_day):
            raise RuntimeError("Missing/inconsistent 7 October Mac batch: " + sha)
        rows.append(row)
    mac, mac_sha = catalogue(OCT_SYNC)
    prod, prod_sha = catalogue(OCT_SYNC, "v9-production-runtime/data/tesla_stations.json")
    test, test_sha = catalogue(OCT_SYNC, "v9-test/data/tesla_stations.json")
    if mac_sha != prod_sha or mac_sha != test_sha:
        raise RuntimeError("7 October Mac evidence is not synchronized in historical V9 mirrors")
    sync_index = index(mac)
    validations = []
    for row in rows:
        original, original_sha = catalogue(row["commitSha"])
        if original_sha != row["canonicalAtCommit"]["sha256"]:
            raise RuntimeError("Historical pinned snapshot differs from archived batch")
        source_index = index(original)
        cc = row["country"]
        before_ids = {k for k in source_index if k[0] == cc}
        after_ids = {k for k in sync_index if k[0] == cc}
        equal = before_ids == after_ids and all(
            source_index[k] == sync_index[k] for k in before_ids
        )
        if not equal:
            raise RuntimeError("Country " + cc + " changed between Oct 7 Mac lot and V9 mirror synchronization")
        delta = row["delta"]
        validations.append({
            "country": cc, "lot": row["lot"], "commitSha": row["commitSha"],
            "publishedAtEuropeParis": row["publishedAtEuropeParis"],
            "stationsBefore": row["countryBefore"]["stations"],
            "stationsAfter": row["countryAfter"]["stations"],
            "pricedConfigurations": row["countryAfter"]["pricedConfigurations"],
            "configurationsWithoutStructuredTariff": row["countryAfter"]["configurationsWithoutStructuredTariff"],
            "addedStations": delta["addedStations"],
            "removedStations": delta["removedStations"],
            "changedPricingStationRecords": delta["changedPricingStationRecords"],
            "metadataOnlyChanges": delta["changedOtherStationMetadataOnly"],
            "actualSourceObservedTimestampCount": row["countryAfter"]["stationsWithActualSourceObservedAt"],
            "changedCanonicalBytes": row["publicationChangedCanonicalBytes"],
            "batchWithNoCatalogueChanges": row["batchWithNoCatalogueChanges"],
            "macCountryRowsRetainedExactlyAtV9Sync": equal,
            "macAlwaysPreferred": cc == "MA",
        })
    assert [x["country"] for x in validations] == ["FR", "PT", "MA"]
    assert validations[2]["batchWithNoCatalogueChanges"], "Expected historical MA no-op; inspect upstream"
    report = {
        "schemaVersion": 1,
        "dateEuropeParis": "2026-10-07",
        "scope": "Pinned Mac France/Portugal/Morocco batches versus Oct 10 V9 synchronization",
        "countries": validations,
        "syncEvidence": {
            "commitSha": OCT_SYNC,
            "committedAtEuropeParis": "2026-10-10T00:31:40+02:00",
            "canonicalSha256": mac_sha,
            "productionMirrorSha256": prod_sha,
            "testMirrorSha256": test_sha,
            "copiesByteIdentical": True,
            "allThreeCountryRowsPreservedExactly": True
        },
        "notes": [
            "Timestamp of Mac publication does not establish direct observation of every charge price.",
            "The Morocco lot #12 was published as a no-op; no actual tariff data changed.",
            "Portugal is audited as a Mac/V9 country even though nine-country pricing selection audit omits PT.",
            "This report does not change tariffs, prices or sources in production."
        ]
    }
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf8"))
        if existing["syncEvidence"]["canonicalSha256"] != mac_sha:
            raise RuntimeError("Frozen Oct 7 retrospective conflicts with source data")
        return
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\\n", encoding="utf8")


def main():
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batches = batch_history()
    rows = {}
    newly_created = []
    for batch in batches:
        item, created = process_batch(batch)
        rows[batch["sha"]] = item
        if created:
            newly_created.append(batch["sha"])
    verify_oct_sync(rows)
    verify_oct07_sync(rows)
    for day in ("2026-10-07", "2026-10-08", "2026-10-09"):
        daily_path = OUT / (day + "-mac-country-batches.json")
        filtered = [x for x in rows.values() if x["localDay"] == day]
        summary = {
            "schemaVersion": 1, "dateEuropeParis": day,
            "auditType": "retroactive_immutable_country_publication_evidence",
            "batches": [{"country": x["country"], "lot": x["lot"],
                         "commitSha": x["commitSha"],
                         "publishedAtEuropeParis": x["publishedAtEuropeParis"],
                         "stations": x["countryAfter"]["stations"],
                         "changedPricingStationRecords": x["delta"]["changedPricingStationRecords"]}
                        for x in sorted(filtered, key=lambda v: v["publishedAtUTC"])],
            "canonicalSourcesArePinnedCommitSnapshots": True,
            "notAnObservedPriceTimestamp": True,
        }
        if not daily_path.exists():
            daily_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("TESLA_HISTORICAL_BATCH_BACKFILL=" + json.dumps({
        "scanned": len(batches), "new": newly_created,
        "oct07": len([x for x in rows.values() if x["localDay"] == "2026-10-07"]),
        "oct08": len([x for x in rows.values() if x["localDay"] == "2026-10-08"]),
        "oct09": len([x for x in rows.values() if x["localDay"] == "2026-10-09"]),
        "syncVerified": True}, sort_keys=True))


if __name__ == "__main__":
    main()
