#!/usr/bin/env python3
"""Preserve the exact last validated France V9 tile generation for fallback builds."""

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


def inspect(source):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("dataset") != "france-irve-static-v9" or manifest.get("stationCount", 0) <= 0:
        raise ValueError("Unexpected France IRVE V9 manifest")
    if digest(source / manifest["allFile"]) != manifest["allSha256"]:
        raise ValueError("France IRVE all-file SHA256 mismatch")
    with gzip.open(source / manifest["allFile"], "rt", encoding="utf-8") as stream:
        stations = json.load(stream)
    if len(stations) != manifest["stationCount"]:
        raise ValueError("France IRVE station count mismatch")
    for tile in manifest["tiles"]:
        flat = source / tile["file"]
        nested = source / "tiles" / tile["file"]
        if flat.parent != source or digest(flat) != tile["sha256"]:
            raise ValueError(f"France IRVE tile SHA256 mismatch: {tile['file']}")
        if nested.exists() and digest(nested) != tile["sha256"]:
            raise ValueError(f"France IRVE nested tile SHA256 mismatch: {tile['file']}")
        with gzip.open(flat, "rt", encoding="utf-8") as stream:
            if len(json.load(stream)) != tile["count"]:
                raise ValueError(f"France IRVE tile count mismatch: {tile['file']}")
    files = sorted(path for path in source.rglob("*") if path.is_file())
    tree = hashlib.sha256()
    for path in files:
        tree.update(f"{path.relative_to(source)}\0{digest(path)}\n".encode())
    return {"stationCount": manifest["stationCount"], "pdcCount": manifest["pdcCount"],
            "tileCount": len(manifest["tiles"]), "allSha256": manifest["allSha256"],
            "manifestSha256": digest(source / "manifest.json"),
            "fileCount": len(files), "treeSha256": tree.hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--stable-sha", required=True)
    args = parser.parse_args()
    proof = inspect(args.source)
    if args.out.exists():
        raise FileExistsError("France last-good bundle already exists; refusing overwrite")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(args.source, args.out)
    if inspect(args.out) != proof:
        raise ValueError("France last-good copy differs from validated source")
    (args.out.parent / "provenance.json").write_text(json.dumps({
        "mode": "preserved_validated_france_irve_static", "sourceRepo": "tesla-charge-companion-stable",
        "sourceSha": args.stable_sha, **proof,
    }, indent=2) + "\n")
    print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()
