#!/usr/bin/env python3
"""Compare Electra and Electroverse France EVSE IDs with the refreshed static IRVE bundle."""
import gzip
import itertools
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(".")
STATIC = ROOT / "data/national/france-irve-static-v9"
PLATFORMS = {
    "Electra": ROOT / "data/platforms/electra/france",
    "ELECTROVERSE": ROOT / "data/platforms/electroverse/france-evse",
}
OUT = ROOT / "reports/france/irve/electra-electroverse-static-match-audit.json"


def norm(value):
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().upper())


def lev_cutoff(a, b, limit=2):
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        lo, hi = max(1, i - limit), min(len(b), i + limit)
        for j in range(1, lo):
            cur[j] = limit + 1
        row_min = limit + 1
        for j in range(lo, hi + 1):
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != b[j - 1]))
            row_min = min(row_min, cur[j])
        for j in range(hi + 1, len(b) + 1):
            cur[j] = limit + 1
        if row_min > limit:
            return limit + 1
        prev = cur
    return prev[len(b)]


def read_json_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    manifest = json.loads((STATIC / "manifest.json").read_text())
    stations = read_json_gz(STATIC / manifest["allFile"])
    national = defaultdict(list)
    for row in stations:
        for group in row[8] or []:
            for evse in group[6] or []:
                key = norm(evse)
                if key:
                    national[key].append({
                        "evseId": evse, "stationId": row[0], "name": row[1],
                        "address": row[2], "operator": row[5], "lat": row[3], "lon": row[4],
                        "powerKw": group[3], "connector": group[1]
                    })
    national_ids = set(national)
    result = {
        "generatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "method": {
            "strict": "uppercase alphanumeric normalization only (case/separator formatting ignored)",
            "near": "Levenshtein distance 1 or 2 after normalization; accepted only when one-to-one and unique on both bases; Electra also requires CPO name agreement when available",
            "coverageUnit": "distinct normalized EVSE identifiers in each published France eMSP overlay",
            "staticSourceSha256": manifest.get("sourceSha256"),
            "staticSourceRetrievedAt": manifest.get("sourceRetrievedAt"),
            "staticStationCount": manifest.get("stationCount"),
            "staticPdcCount": manifest.get("pdcCount"),
        },
        "bases": {}
    }
    for label, base in PLATFORMS.items():
        platform_manifest = json.loads((base / "manifest.json").read_text())
        platform_meta = {}
        for tile in platform_manifest["tiles"]:
            doc = read_json_gz(base / tile["file"])
            for offer in doc.get("emspOffers", []):
                for original in offer.get("evseIds", []):
                    key = norm(original)
                    if key:
                        metadata = offer.get("metadata", {})
                        info = platform_meta.setdefault(key, {"originalIds": set(), "cpos": set(), "modes": set()})
                        info["originalIds"].add(original)
                        if metadata.get("cpo"):
                            info["cpos"].add(str(metadata["cpo"]))
                        for field in ("identityMode", "verifiedScope"):
                            if metadata.get(field):
                                info["modes"].add(str(metadata[field]))
        platform_ids = set(platform_meta)
        exact = platform_ids & national_ids
        misses = platform_ids - exact
        near_candidates = {}
        # Search the same prefix/suffix buckets first, then verify exact Levenshtein distance.
        by_prefix = defaultdict(list)
        by_suffix = defaultdict(list)
        for key in national_ids:
            by_prefix[key[:6]].append(key)
            by_suffix[key[-6:]].append(key)
        for key in misses:
            possible = set()
            if len(key) >= 6:
                possible.update(by_prefix.get(key[:6], ()))
                possible.update(by_suffix.get(key[-6:], ()))
            if not possible:
                possible = national_ids
            matches = []
            for other in possible:
                if abs(len(key) - len(other)) not in (1, 2):
                    continue
                distance = lev_cutoff(key, other, 2)
                if distance in (1, 2):
                    matches.append((other, distance))
            if matches:
                near_candidates[key] = matches
        inverse = defaultdict(set)
        for source, matches in near_candidates.items():
            for target, _ in matches:
                inverse[target].add(source)
        accepted, rejected = [], []
        for source, matches in near_candidates.items():
            for target, distance in matches:
                reasons = []
                if len(matches) != 1:
                    reasons.append("multiple_static_candidates")
                if len(inverse[target]) != 1:
                    reasons.append("multiple_source_ids_to_same_static_evse")
                source_meta = platform_meta[source]
                target_rows = national[target]
                if len(target_rows) != 1:
                    reasons.append("static_evse_not_unique")
                if label == "Electra" and source_meta["cpos"] and target_rows:
                    src_cpos = {norm(x) for x in source_meta["cpos"]}
                    target_cpo = norm(target_rows[0]["operator"])
                    if not any(cpo and (cpo in target_cpo or target_cpo in cpo) for cpo in src_cpos):
                        reasons.append("cpo_name_mismatch")
                item = {
                    "sourceIds": sorted(source_meta["originalIds"]),
                    "normalizedSource": source,
                    "irveEvse": target_rows[0]["evseId"] if target_rows else target,
                    "normalizedIrve": target,
                    "editDistance": distance,
                    "irveStation": target_rows[0] if target_rows else None,
                    "sourceCpo": sorted(source_meta["cpos"]),
                    "identityModes": sorted(source_meta["modes"]),
                }
                (rejected if reasons else accepted).append({**item, "rejectionReasons": reasons} if reasons else item)
        result["bases"][label] = {
            "generatedAt": platform_manifest.get("generatedAt"),
            "denominatorDistinctEvseIds": len(platform_ids),
            "rawPublishedEvseIdCount": platform_manifest.get("stats", {}).get("publishedEvseIds", platform_manifest.get("stats", {}).get("publishedEvses")),
            "strictNormalizedExactCount": len(exact),
            "strictNormalizedExactRatePercent": round(100 * len(exact) / len(platform_ids), 4) if platform_ids else 0,
            "unmatchedAfterExact": len(misses),
            "uniqueVerifiedOneOrTwoCharacterNearMatchCount": len(accepted),
            "nearMatchRatePercentIncludingVerifiedNear": round(100 * (len(exact) + len(accepted)) / len(platform_ids), 4) if platform_ids else 0,
            "nearCandidateCountNotAccepted": len(rejected),
            "remainingUnmatched": len(misses) - len({x["normalizedSource"] for x in accepted}),
            "nearMatchesAccepted": accepted,
            "nearMatchesRejected": rejected[:300],
            "platformManifestStats": platform_manifest.get("stats", {}),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for label, data in result["bases"].items():
        print(f"{label}: exact={data['strictNormalizedExactCount']}/{data['denominatorDistinctEvseIds']} ({data['strictNormalizedExactRatePercent']}%), verifiedNear={data['uniqueVerifiedOneOrTwoCharacterNearMatchCount']}, remaining={data['remainingUnmatched']}")


if __name__ == "__main__":
    main()
