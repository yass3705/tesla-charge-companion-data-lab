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
            archive = ROOT / route.archive
            raw = archive.read_bytes()
            manifest_sha = None
            if route.manifest:
                manifest_raw = (ROOT / route.manifest).read_bytes()
                manifest = json.loads(manifest_raw)
                if (manifest.get("allSha256") != hashlib.sha256(raw).hexdigest() or
                        manifest.get("allBytes") != len(raw)):
                    raise ValueError(f"Source manifest artifact mismatch: {source_id}")
                manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
            decoded = gzip.decompress(raw) if archive.suffix == ".gz" else raw
            normalized = route.normalizer(json.loads(decoded), artifact_sha256=hashlib.sha256(raw).hexdigest())
            if normalized["source"]["id"] != source_id:
                raise ValueError(f"Canonical route identity mismatch: {source_id}")
            target = canonical_dir / (source_id.replace(":", "__") + ".json")
            target.write_text(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            inputs[source_id] = target
            report.append({"source": source_id, "archive": route.archive,
                           "archiveSha256": hashlib.sha256(raw).hexdigest(),
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
