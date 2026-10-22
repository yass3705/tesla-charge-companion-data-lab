#!/usr/bin/env python3
"""Run the preserved France Electra platform builder in an isolated directory."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from v9_rebuild.electroverse import ROOT

OUTPUT = Path("data/platforms/electra/france")
NATIONAL = Path("data/national/france-irve-static-v9/all.json.gz")
ASSOCIATIONS = Path("data/platforms/electra/irve-associations-batch-01.json")
ASSOCIATION_DIR = Path("data/platforms/electra/irve-association-batches")
VERIFIED = Path("data/platforms/electra/verified-app-evse-tariff-map.json")
SCRIPT = Path("scripts/electra_france_platform_snapshot.mjs")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_output(out: Path) -> dict:
    folder = out / OUTPUT
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schemaVersion") != 1
            or manifest.get("dataset") != "electra-france-platform-national-evse-overlay"
            or manifest.get("country") != "FR"):
        raise ValueError("Electra France manifest contract invalid")
    source = manifest.get("source") or {}
    total = source.get("globalTotalCount")
    pages = source.get("totalPages")
    if (not isinstance(total, int) or total < 0 or not isinstance(pages, int)
            or pages != (total + 99) // 100):
        raise ValueError("Electra France pagination contract invalid")
    tiles = manifest.get("tiles")
    archive = manifest.get("sourceArchive") or {}
    stats = manifest.get("stats") or {}
    if (not isinstance(tiles, list) or manifest.get("tileCount") != len(tiles)
            or archive.get("file") != "source-locations.json.gz"):
        raise ValueError("Electra France output files missing")
    with gzip.open(folder / archive["file"], "rt", encoding="utf-8") as stream:
        raw = json.load(stream)
    if (_digest(folder / archive["file"]) != archive.get("sha256")
            or not isinstance(raw.get("locations"), list)
            or raw.get("country") != "FR"
            or len(raw["locations"]) != archive.get("locationCount")
            or sum(len(loc.get("evses") or []) for loc in raw["locations"]) != archive.get("evseCount")
            or stats.get("sourceLocationCount") != len(raw["locations"])):
        raise ValueError("Electra France source archive invalid")
    seen_tiles, seen_offers = set(), set()
    for tile in tiles:
        name = tile.get("file")
        if not isinstance(name, str) or Path(name).name != name or name in seen_tiles:
            raise ValueError("Electra France duplicate or unsafe tile")
        seen_tiles.add(name)
        path = folder / name
        if path.stat().st_size != tile.get("bytes") or _digest(path) != tile.get("sha256"):
            raise ValueError("Electra France tile digest invalid")
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
        offers = payload.get("emspOffers")
        if payload.get("country") != "FR" or not isinstance(offers, list) or len(offers) != tile.get("count"):
            raise ValueError("Electra France tile count invalid")
        for offer in offers:
            identity = offer.get("id")
            evse_ids = offer.get("evseIds")
            if (not identity or identity in seen_offers or not isinstance(evse_ids, list)
                    or len(evse_ids) != 1 or offer.get("provider") != "Electra"
                    or offer.get("metadata", {}).get("verifiedScope") != "exact_evse"):
                raise ValueError("Electra France offer scope invalid")
            seen_offers.add(identity)
    if stats.get("publishedOffers") != len(seen_offers):
        raise ValueError("Electra France offer count mismatch")
    with gzip.open(folder / "residuals.json.gz", "rt", encoding="utf-8") as stream:
        residuals = json.load(stream)
    if residuals.get("country") != "FR" or not isinstance(residuals.get("locations"), list):
        raise ValueError("Electra France residual archive invalid")
    return manifest


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Electra France builder must run outside checkout")
    for relative in (NATIONAL, ASSOCIATIONS, VERIFIED, SCRIPT):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    if (ROOT / ASSOCIATION_DIR).is_dir():
        shutil.copytree(ROOT / ASSOCIATION_DIR, out / ASSOCIATION_DIR, dirs_exist_ok=True)
    result = runner(["node", str(out / SCRIPT), str(out / OUTPUT), str(out / NATIONAL),
                     str(out / ASSOCIATIONS), str(out / ASSOCIATION_DIR), str(out / VERIFIED)],
                    cwd=out, capture_output=True, text=True, timeout=3000, check=False)
    if result.returncode:
        raise RuntimeError("Historical Electra France builder failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
