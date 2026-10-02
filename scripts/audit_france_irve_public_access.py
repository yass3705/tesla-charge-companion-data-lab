#!/usr/bin/env python3
"""Audit France IRVE static data for stations that may not actually be public.

Non-destructive: this script only emits audit artifacts. It never removes stations.

The national IRVE schema is intended for public charging points, but the schema also
contains access fields that can reveal restricted/conditional access. In particular,
"Accès réservé" is NOT synonymous with "non public": it also covers barriers and toll
roads. We therefore combine structured fields with explicit text signals and keep
ambiguous cases in review buckets.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = "https://www.data.gouv.fr/api/1/datasets/r/eb76d20a-8501-400e-b336-d85724de5435"
DEFAULT_JSON = ROOT / "reports/france/irve-public-access-audit.json"
DEFAULT_CSV = ROOT / "reports/france/irve-public-access-suspects.csv"

HIGH_PATTERNS = {
    "explicit_non_public": [
        r"non ouvert(?:e)? au public",
        r"non accessible au public",
        r"interdit(?:e)? au public",
        r"acc[eè]s priv[eé]",
        r"site priv[eé]",
    ],
    "staff_only": [
        r"r[eé]serv[eé](?:e|es)? (?:au|aux) personnel",
        r"r[eé]serv[eé](?:e|es)? (?:au|aux) salari[eé]s?",
        r"r[eé]serv[eé](?:e|es)? (?:au|aux) employ[eé]s?",
        r"personnel uniquement",
        r"salari[eé]s? uniquement",
        r"employ[eé]s? uniquement",
    ],
    "residents_only": [
        r"r[eé]serv[eé](?:e|es)? (?:aux )?r[eé]sidents?",
        r"r[eé]serv[eé](?:e|es)? (?:aux )?copropri[eé]taires?",
        r"copropri[eé]t[eé]",
        r"r[eé]sidence priv[eé]e",
    ],
    "fleet_only": [
        r"flotte(?:s)? (?:interne|priv[eé]e|entreprise)",
        r"v[eé]hicules? de service",
        r"v[eé]hicules? d[' ]entreprise",
        r"r[eé]serv[eé](?:e|es)? (?:aux )?v[eé]hicules? de service",
    ],
}

CONDITIONAL_PATTERNS = {
    "customers_only": [
        r"client[eè]le uniquement",
        r"clients? uniquement",
        r"r[eé]serv[eé](?:e|es)? (?:aux )?clients?",
        r"r[eé]serv[eé](?:e|es)? (?:à la )?client[eè]le",
    ],
    "controlled_access": [
        r"badge",
        r"barri[eè]re",
        r"portail",
        r"digicode",
        r"code d[' ]acc[eè]s",
        r"autorisation",
        r"sur demande",
    ],
    "hospitality": [
        r"h[oô]tel",
        r"camping",
        r"restaurant",
    ],
    "toll_or_paid_road": [
        r"p[eé]age",
        r"autoroute",
        r"aire de service",
    ],
}

def norm(value: object) -> str:
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKC", s).strip().lower()
    return re.sub(r"\s+", " ", s)

def detect_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","

def open_source(source: str):
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "TCC-IRVE-public-access-audit/1.0"})
        return urllib.request.urlopen(req, timeout=120)
    return open(source, "rb")

def iter_rows(source: str) -> Iterable[dict[str, str]]:
    with open_source(source) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        sample = text.read(32768)
        delimiter = detect_delimiter(sample)
        buffered = io.StringIO(sample + text.read())
        reader = csv.DictReader(buffered, delimiter=delimiter)
        for row in reader:
            yield {str(k).strip(): (v or "").strip() for k, v in row.items() if k is not None}

def match_groups(text: str, groups: dict[str, list[str]]) -> list[str]:
    hits = []
    for label, patterns in groups.items():
        if any(re.search(p, text, flags=re.I) for p in patterns):
            hits.append(label)
    return hits

def station_key(row: dict[str, str]) -> str:
    return (
        row.get("id_station_itinerance")
        or row.get("id_station_local")
        or "|".join(
            [
                row.get("nom_station", ""),
                row.get("adresse_station", ""),
                row.get("code_insee_commune", ""),
            ]
        )
    ).strip()

def cpo_name(row: dict[str, str]) -> str:
    return (
        row.get("nom_operateur")
        or row.get("nom_enseigne")
        or row.get("nom_amenageur")
        or "INCONNU"
    ).strip()

def classify(row: dict[str, str]) -> tuple[str, list[str]]:
    access = norm(row.get("condition_acces"))
    implantation = norm(row.get("implantation_station"))
    joined = " | ".join(
        norm(row.get(k))
        for k in [
            "nom_station",
            "adresse_station",
            "observations",
            "tarification",
            "nom_enseigne",
            "nom_operateur",
            "nom_amenageur",
        ]
    )
    high = match_groups(joined, HIGH_PATTERNS)
    conditional = match_groups(joined, CONDITIONAL_PATTERNS)

    reserved = "réserv" in access or "reserve" in access
    customer_parking = "parking privé réservé à la clientèle" in implantation or "parking prive reserve a la clientele" in implantation

    if high:
        if reserved:
            return "high_confidence_non_public", sorted(set(high + ["structured_access_reserved"]))
        return "possible_non_public_schema_inconsistency", sorted(set(high + ["structured_access_not_reserved"]))

    if reserved or customer_parking or conditional:
        reasons = conditional[:]
        if reserved:
            reasons.append("structured_access_reserved")
        if customer_parking:
            reasons.append("customer_only_parking_type")
        return "restricted_or_conditional_review", sorted(set(reasons))

    return "public_or_no_private_signal", []

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--json-out", default=str(DEFAULT_JSON))
    ap.add_argument("--csv-out", default=str(DEFAULT_CSV))
    args = ap.parse_args()

    stations: dict[str, dict] = {}
    pdc_rows = 0

    for row in iter_rows(args.source):
        pdc_rows += 1
        key = station_key(row)
        if not key:
            continue
        status, reasons = classify(row)
        cpo = cpo_name(row)
        rec = stations.setdefault(
            key,
            {
                "stationId": key,
                "stationName": row.get("nom_station", ""),
                "address": row.get("adresse_station", ""),
                "insee": row.get("code_insee_commune", ""),
                "operator": cpo,
                "brand": row.get("nom_enseigne", ""),
                "developer": row.get("nom_amenageur", ""),
                "conditionAccess": row.get("condition_acces", ""),
                "implantation": row.get("implantation_station", ""),
                "hours": row.get("horaires", ""),
                "observations": row.get("observations", ""),
                "pdcCountObserved": 0,
                "statuses": set(),
                "reasons": set(),
            },
        )
        rec["pdcCountObserved"] += 1
        rec["statuses"].add(status)
        rec["reasons"].update(reasons)

    priority = {
        "high_confidence_non_public": 3,
        "possible_non_public_schema_inconsistency": 2,
        "restricted_or_conditional_review": 1,
        "public_or_no_private_signal": 0,
    }

    flattened = []
    by_status = Counter()
    by_cpo: dict[str, Counter] = defaultdict(Counter)
    pdc_by_status = Counter()

    for rec in stations.values():
        status = max(rec["statuses"], key=lambda x: priority[x])
        out = dict(rec)
        out["status"] = status
        out["reasons"] = sorted(rec["reasons"])
        out.pop("statuses", None)
        by_status[status] += 1
        pdc_by_status[status] += out["pdcCountObserved"]
        by_cpo[out["operator"]][status] += 1
        flattened.append(out)

    suspects = [
        x for x in flattened
        if x["status"] != "public_or_no_private_signal"
    ]
    suspects.sort(key=lambda x: (-priority[x["status"]], x["operator"].casefold(), x["stationName"].casefold()))

    cpo_rows = []
    for cpo, counts in by_cpo.items():
        total_flagged = sum(v for k, v in counts.items() if k != "public_or_no_private_signal")
        high = counts["high_confidence_non_public"]
        inconsistent = counts["possible_non_public_schema_inconsistency"]
        restricted = counts["restricted_or_conditional_review"]
        if total_flagged:
            cpo_rows.append({
                "operator": cpo,
                "flaggedStations": total_flagged,
                "highConfidenceNonPublic": high,
                "schemaInconsistency": inconsistent,
                "restrictedConditionalReview": restricted,
            })
    cpo_rows.sort(key=lambda x: (-x["highConfidenceNonPublic"], -x["flaggedStations"], x["operator"].casefold()))

    report = {
        "schemaVersion": "1.0.0",
        "dataset": "france-irve-public-access-audit",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": args.source,
        "policy": {
            "nonDestructive": True,
            "accessReservedIsNotEquivalentToNonPublic": True,
            "automaticProductionExclusion": False,
            "stationLevelDeduplication": True,
            "highConfidenceRequiresExplicitPrivateAudienceSignal": True,
        },
        "counts": {
            "pdcRowsRead": pdc_rows,
            "uniqueStations": len(stations),
            "flaggedStations": len(suspects),
            "byStatusStations": dict(by_status),
            "byStatusPdcRows": dict(pdc_by_status),
            "operatorsWithFlags": len(cpo_rows),
        },
        "operatorRanking": cpo_rows,
        "flaggedStations": suspects,
    }

    json_out = Path(args.json_out)
    csv_out = Path(args.csv_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fields = [
        "status", "operator", "brand", "developer", "stationId", "stationName",
        "address", "insee", "conditionAccess", "implantation", "hours",
        "pdcCountObserved", "reasons", "observations",
    ]
    with csv_out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in suspects:
            copy = {k: row.get(k, "") for k in fields}
            copy["reasons"] = "|".join(row["reasons"])
            w.writerow(copy)

    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    print("Top flagged operators:")
    for item in cpo_rows[:30]:
        print(json.dumps(item, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
