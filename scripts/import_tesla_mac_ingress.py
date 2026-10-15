#!/usr/bin/env python3
"""Import a Mac-validated, immutable Production ingress into Data Lab last-good.

Production is a transport escrow only. The Data Lab Git commit containing both
catalogue and manifest is the canonical pin consumed by V9.
"""
import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

INGRESS = "yass3705/tesla-charge-companion-production"
INGRESS_PATH = "data/tesla/mac/staging/catalogue.json"
READY_PATH = "data/tesla/mac/staging/ready.json"
CATALOGUE = Path("data/tesla/mac/catalogue.json")
MANIFEST = Path("data/tesla/mac/last-good.json")
COUNTRIES = {"BE", "CH", "DE", "ES", "FR", "GB", "IT", "LU", "MA", "NL", "PT"}


def fetch_ready():
    url = f"https://api.github.com/repos/{INGRESS}/contents/{READY_PATH}?ref=main"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept":"application/vnd.github+json",
                                                             "User-Agent":"tcc-datalab-tesla-import"}), timeout=45) as response:
            item = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    import base64
    return json.loads(base64.b64decode(item["content"]))


def fetch_catalogue(commit):
    url = f"https://raw.githubusercontent.com/{INGRESS}/{commit}/{INGRESS_PATH}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"tcc-datalab-tesla-import"}), timeout=90) as response:
        return response.read()


def validate(ready, raw, prior, previous_raw):
    if ready.get("schemaVersion") != 1 or ready.get("status") != "ready":
        raise ValueError("Mac ingress is not ready")
    if ready.get("sourceRepository") != INGRESS or ready.get("cataloguePath") != INGRESS_PATH:
        raise ValueError("Unexpected Mac ingress owner or path")
    commit = ready.get("catalogueCommit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Mac ingress commit is not immutable")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != ready.get("catalogueSha256") or len(raw) != ready.get("catalogueBytes"):
        raise ValueError("Mac ingress SHA-256 or byte count mismatch")
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != ready.get("stationCount") or len(rows) < 1100:
        raise ValueError("Mac ingress catalogue incomplete")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)) or any(not station_id for station_id in ids):
        raise ValueError("Mac ingress IDs missing or duplicated")
    if any(not row.get("countryCode") or not isinstance(row.get("pricing"), dict)
           or not row.get("chargingConfigurations") for row in rows):
        raise ValueError("Mac ingress station data incomplete")
    if not COUNTRIES.issubset({row["countryCode"] for row in rows}):
        raise ValueError("Mac ingress country coverage incomplete")
    old_rows = json.loads(previous_raw)
    if not {row["id"] for row in old_rows}.issubset(set(ids)):
        raise ValueError("Mac ingress deleted a last-good station")
    if len(rows) < prior.get("stationCount", 0):
        raise ValueError("Mac ingress station count fell")
    run_id = int(ready.get("updaterRunId") or 0)
    previous_run = int(prior.get("updaterRunId") or 0)
    if run_id < previous_run:
        raise ValueError("Older Mac run cannot replace last-good")
    if run_id == previous_run and digest != prior.get("catalogueSha256"):
        raise ValueError("Conflicting Mac run digest")
    dates = ready.get("countryDates")
    if not isinstance(dates, dict) or not COUNTRIES.issubset(dates):
        raise ValueError("Mac ingress country dates incomplete")
    for code, old_date in (prior.get("countryDates") or {}).items():
        if dates.get(code, "") < old_date:
            raise ValueError(f"Mac ingress date rollback for {code}")
    manifest = {
        "schemaVersion": 1, "status": "last-good", "cataloguePath": str(CATALOGUE),
        "catalogueCommit": commit, "catalogueSha256": digest,
        "catalogueBytes": len(raw), "stationCount": len(rows),
        "sourceRepository": INGRESS, "sourcePath": INGRESS_PATH,
        "sourceKind": "validated Mac lot publication via immutable ingress",
        "sourcePublishedAt": ready["sourcePublishedAt"],
        "lot": ready["lot"], "updaterRunId": run_id,
        "countryDates": dates, "countriesUpdated": ready["countriesUpdated"],
        "sucComparison": ready.get("sucComparison", "unavailable"),
        "provenance": ready["provenance"],
    }
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--ready-file")
    parser.add_argument("--catalogue-file")
    args = parser.parse_args()
    root = Path(args.root)
    ready = json.loads(Path(args.ready_file).read_text()) if args.ready_file else fetch_ready()
    if ready is None:
        print("TESLA_MAC_INGRESS_NOT_READY")
        return
    raw = Path(args.catalogue_file).read_bytes() if args.catalogue_file else fetch_catalogue(ready["catalogueCommit"])
    old = json.loads((root / MANIFEST).read_text())
    previous_raw = (root / CATALOGUE).read_bytes()
    next_manifest = validate(ready, raw, old, previous_raw)
    if raw == previous_raw and old.get("updaterRunId") == next_manifest["updaterRunId"]:
        print("TESLA_MAC_ALREADY_IMPORTED", next_manifest["catalogueSha256"])
        return
    for path, data in ((root / CATALOGUE, raw),
                       (root / MANIFEST, (json.dumps(next_manifest, ensure_ascii=False, indent=2) + "\n").encode())):
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    print("TESLA_MAC_IMPORTED", next_manifest["catalogueSha256"], next_manifest["stationCount"])


if __name__ == "__main__":
    main()
