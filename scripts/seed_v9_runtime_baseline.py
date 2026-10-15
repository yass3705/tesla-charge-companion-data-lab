#!/usr/bin/env python3
"""Preserve the public validated V9 runtime inputs as a pinned Data Lab archive."""

import argparse
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess
import tarfile


PATHS = ("data", "assets", "index.html", "v9-production-runtime/data", "v9-production-runtime/assets")
KEYS = (
    "index.html", "data/exchange_rates.json", "data/tesla_stations.json",
    "v9-production-runtime/data/v9/france-static/manifest.json",
    "v9-production-runtime/data/v9/italy-static/manifest.json",
    "v9-production-runtime/assets/v9/pricing-engine.js",
)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(archive):
    files = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = pathlib.PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or member.issym() or member.islnk():
                raise ValueError(f"Unsafe baseline archive entry: {member.name}")
            if member.isdir():
                continue
            if not member.isfile() or member.name in files:
                raise ValueError(f"Unexpected baseline archive entry: {member.name}")
            h = hashlib.sha256()
            size = 0
            with tar.extractfile(member) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
                    size += len(chunk)
            if size != member.size:
                raise ValueError(f"Baseline archive size mismatch: {member.name}")
            files[member.name] = {"sha256": h.hexdigest(), "bytes": size}
    if not set(KEYS) <= set(files):
        raise ValueError(f"Baseline archive missing required files: {sorted(set(KEYS)-set(files))}")
    if len(files) < 1200:
        raise ValueError("Baseline archive unexpectedly small")
    return files


def build(stable, source_sha, output):
    stable = pathlib.Path(stable)
    output = pathlib.Path(output)
    actual = subprocess.check_output(["git", "-C", str(stable), "rev-parse", "HEAD"], text=True).strip()
    if actual != source_sha:
        raise ValueError(f"Stable source pin differs: {actual}")
    if output.exists():
        raise FileExistsError("Validated baseline archive already exists")
    output.mkdir(parents=True)
    archive = output / "runtime-baseline.tar.gz"
    proc = subprocess.Popen(["git", "-C", str(stable), "archive", "--format=tar", source_sha, *PATHS], stdout=subprocess.PIPE)
    with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as compressed:
        shutil.copyfileobj(proc.stdout, compressed)
    if proc.wait() != 0:
        raise RuntimeError("Git archive failed")
    files = inspect(archive)
    manifest = {
        "mode": "preserved_public_v9_runtime_baseline", "sourceRepo": "tesla-charge-companion-stable",
        "sourceSha": source_sha, "archiveSha256": sha256(archive),
        "archiveBytes": archive.stat().st_size, "fileCount": len(files), "files": files,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {key: manifest[key] for key in ("sourceSha", "archiveSha256", "archiveBytes", "fileCount")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stable", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.stable, args.source_sha, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
