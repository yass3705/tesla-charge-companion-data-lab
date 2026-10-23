#!/usr/bin/env python3
"""Build an immutable prepared bundle from preserved V9 source archives.

The output is a new directory outside Git. A failed source aborts the batch
before the output appears; its earlier prepared bundle stays untouched.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from v9_rebuild.canonical_registry import BY_SOURCE
from v9_rebuild.snapshot import prepare, verify


def read_route(route, source_id: str) -> tuple[object, str, str | None]:
    archive = ROOT / route.archive
    raw = archive.read_bytes()
    if route.page_manifest:
        manifest = json.loads(raw)
        pages = manifest.get("pages")
        size = manifest.get("pageSize")
        if (manifest.get("country") != source_id[:2] or not isinstance(pages, list) or
                not pages or manifest.get("pageCount") != len(pages) or
                not isinstance(size, int) or size <= 0):
            raise ValueError(f"Page manifest invalid: {source_id}")
        locations, hashes = [], []
        for index, entry in enumerate(pages):
            relative = entry.get("canonicalPath")
            if (entry.get("pageIndex") != index or entry.get("offset") != index * size or
                    not isinstance(relative, str) or
                    not relative.startswith("data/belgium/pages/") or
                    ".." in Path(relative).parts):
                raise ValueError(f"Page sequence or path invalid: {source_id}")
            page_raw = (ROOT / relative).read_bytes()
            page = json.loads(gzip.decompress(page_raw) if relative.endswith(".gz") else page_raw)
            rows = page.get("locations")
            if (page.get("country") != source_id[:2] or not isinstance(rows, list) or
                    page.get("locationCount") != len(rows) or entry.get("locationCount") != len(rows) or
                    (rows and (rows[0].get("id") != entry.get("firstLocationId") or
                               rows[-1].get("id") != entry.get("lastLocationId")))):
                raise ValueError(f"Page contents or boundaries invalid: {source_id}")
            locations.extend(rows)
            hashes.append(hashlib.sha256(page_raw).hexdigest())
        identity = hashlib.sha256((hashlib.sha256(raw).hexdigest() + ":" + ":".join(hashes)).encode()).hexdigest()
        return {"country": manifest["country"], "source": manifest.get("source"),
                "locations": locations}, identity, hashlib.sha256(raw).hexdigest()
    manifest_sha = None
    if route.manifest:
        manifest_raw = (ROOT / route.manifest).read_bytes()
        manifest = json.loads(manifest_raw)
        if (manifest.get("allSha256") != hashlib.sha256(raw).hexdigest() or
                manifest.get("allBytes") != len(raw)):
            raise ValueError(f"Source manifest artifact mismatch: {source_id}")
        manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    decoded = gzip.decompress(raw) if archive.suffix == ".gz" else raw
    return json.loads(decoded), hashlib.sha256(raw).hexdigest(), manifest_sha


def build(destination: Path, selected: list[str] | None = None) -> dict:
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents or destination.exists():
        raise ValueError("Canonical output must be a new directory outside Git checkout")
    ids = sorted(set(selected or BY_SOURCE))
    if not ids or any(source_id not in BY_SOURCE for source_id in ids):
        raise ValueError("Unknown or empty canonical source selection")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tcc-v9-canonical-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "output"
        canonical_dir = stage / "canonical"
        canonical_dir.mkdir(parents=True)
        inputs, report = {}, []
        for source_id in ids:
            route = BY_SOURCE[source_id]
            payload, archive_sha, manifest_sha = read_route(route, source_id)
            normalized = route.normalizer(payload, artifact_sha256=archive_sha)
            if normalized["source"]["id"] != source_id:
                raise ValueError(f"Canonical route identity mismatch: {source_id}")
            target = canonical_dir / (source_id.replace(":", "__") + ".json")
            target.write_text(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            inputs[source_id] = target
            report.append({"source": source_id, "archive": route.archive,
                           "archiveSha256": archive_sha,
                           "sourceManifestSha256": manifest_sha,
                           "canonicalSha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        bundle = prepare(inputs, stage / "bundles")
        verify(bundle)
        result = {"status": "prepared", "bundleId": bundle.name, "sources": report}
        (stage / "build-report.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        stage.rename(destination)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source", action="append", dest="sources")
    args = parser.parse_args()
    result = build(args.out, args.sources)
    print(json.dumps({"status": result["status"], "bundleId": result["bundleId"],
                      "sourceCount": len(result["sources"]),
                      "bundle": str(args.out.resolve() / "bundles" / result["bundleId"])}))


if __name__ == "__main__":
    main()
