"""Immutable local handoff bundles; no collector or branch mutation."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

from v9_rebuild.canonical import SCHEMA_VERSION, validate


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_name(source_id: str) -> str:
    if not re.fullmatch(r"[A-Z]{2}:[a-z0-9_]+", source_id):
        raise ValueError("Unsafe source ID")
    return source_id.replace(":", "__")


def prepare(inputs: dict[str, Path], destination: Path) -> Path:
    """Write one content addressed bundle from validated canonical inputs."""
    if not inputs:
        raise ValueError("No canonical inputs")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v9-snapshot-", dir=destination) as temporary:
        stage = Path(temporary)
        entries = []
        for source_id, path in sorted(inputs.items()):
            name = _source_name(source_id) + ".json"
            raw = path.read_bytes()
            payload = json.loads(raw)
            validate(payload)
            if payload["source"]["id"] != source_id:
                raise ValueError("Source ID mismatch")
            artifact_hash = payload["source"].get("artifactSha256")
            if not isinstance(artifact_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_hash):
                raise ValueError("Source artifact SHA invalid")
            (stage / name).write_bytes(raw)
            entries.append({"source": source_id, "path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                            "sourceArtifactSha256": artifact_hash, "canonicalSchemaVersion": SCHEMA_VERSION})
        manifest = {"schemaVersion": 1, "state": "prepared", "sources": entries}
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (stage / "manifest.json").write_bytes(manifest_bytes)
        bundle_id = hashlib.sha256(manifest_bytes).hexdigest()
        target = destination / bundle_id
        if target.exists():
            verify(target)
            if target.joinpath("manifest.json").read_bytes() != manifest_bytes:
                raise ValueError("Existing snapshot identity collision")
            return target
        try:
            stage.rename(target)
        except OSError:
            if not target.exists():
                raise
        verify(target)
        return target


def verify(bundle: Path) -> dict:
    manifest_path = bundle / "manifest.json"
    raw = manifest_path.read_bytes()
    if bundle.name != hashlib.sha256(raw).hexdigest():
        raise ValueError("Snapshot manifest SHA mismatch")
    manifest = json.loads(raw)
    if manifest.get("schemaVersion") != 1 or manifest.get("state") != "prepared" or not isinstance(manifest.get("sources"), list):
        raise ValueError("Snapshot manifest invalid")
    seen = set()
    declared = {"manifest.json"}
    for entry in manifest["sources"]:
        source_id = entry["source"]
        name = _source_name(source_id) + ".json"
        if source_id in seen or entry.get("path") != name or entry.get("canonicalSchemaVersion") != SCHEMA_VERSION:
            raise ValueError("Snapshot source entry invalid")
        seen.add(source_id)
        declared.add(name)
        path = bundle / name
        if _hash(path) != entry.get("sha256"):
            raise ValueError("Snapshot source SHA mismatch")
        payload = json.loads(path.read_bytes())
        validate(payload)
        if payload["source"].get("id") != source_id or payload["source"].get("artifactSha256") != entry.get("sourceArtifactSha256"):
            raise ValueError("Snapshot source provenance mismatch")
    if {path.name for path in bundle.iterdir()} != declared:
        raise ValueError("Snapshot file set mismatch")
    return manifest
