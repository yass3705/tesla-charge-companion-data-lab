#!/usr/bin/env python3
"""Preserve an exact validated Italy V9 runtime without promoting a new PUN build."""

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_static(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("country") != "IT" or manifest.get("stationCount", 0) <= 0:
        raise ValueError("Invalid Italy static manifest")
    entries = [(manifest["allFile"], manifest["allSha256"])]
    entries += [(tile["file"], tile["sha256"]) for tile in manifest["tiles"]]
    for name, expected in entries:
        path = directory / name
        if path.parent != directory or digest(path) != expected:
            raise ValueError(f"Italy static tile SHA256 mismatch: {name}")
    with gzip.open(directory / manifest["allFile"], "rt", encoding="utf-8") as stream:
        stations = json.load(stream)
    if len(stations) != manifest["stationCount"]:
        raise ValueError("Italy station count mismatch")
    return manifest["stationCount"]


def validate_offers(path):
    with path.open("rb") as stream:
        offers = json.load(stream)
    if offers.get("country") != "IT":
        raise ValueError("Invalid Italy offer country")
    counts = {key: len(offers[key]) for key in ("directOffers", "subscriptionOffers", "emspOffers")}
    if not all(counts.values()):
        raise ValueError("Italy offer category disappeared")
    return counts


def seed(source, out):
    if out.exists():
        raise FileExistsError("Validated Italy runtime already exists; refusing overwrite")
    static = source / "italy-static"
    offers = source / "italy-offers.json"
    stations = validate_static(static)
    counts = validate_offers(offers)
    out.mkdir(parents=True)
    shutil.copytree(static, out / "italy-static")
    archive = out / "italy-offers.json.gz"
    with offers.open("rb") as raw, archive.open("wb") as compressed:
        with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9) as stream:
            shutil.copyfileobj(raw, stream)
    evidence = {
        "country": "IT", "mode": "preserved_validated_v9_runtime",
        "sourceOffersSha256": digest(offers), "compressedOffersSha256": digest(archive),
        "staticManifestSha256": digest(out / "italy-static" / "manifest.json"),
        "stations": stations, **counts,
    }
    (out / "bundle.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    print(json.dumps(seed(args.source, args.out), sort_keys=True))


if __name__ == "__main__":
    main()
