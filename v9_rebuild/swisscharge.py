#!/usr/bin/env python3
"""Four preserved Swisscharge shards with isolated restart state and exact merge."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/collect_swisscharge_cloud.py")
DATA = Path("data/swisscharge/swisscharge-tariffs.json")
REPORT = Path("docs/switzerland-swisscharge-finalization-2026-09-27.json")
PARTITIONS = 4


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_part(path: Path, index: int) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    scope = data.get("scope") or {}
    summary = data.get("summary") or {}
    rows, missing = data.get("evses"), data.get("unresolved")
    if not isinstance(rows, list) or not isinstance(missing, list):
        raise ValueError("Swisscharge shard rows missing")
    ids = [row.get("physicalReference") for row in rows + missing]
    if (data.get("schemaVersion") != 1 or scope.get("shardIndex") != index
            or scope.get("shardCount") != PARTITIONS
            or not isinstance(scope.get("nationalEvseCount"), int)
            or scope["nationalEvseCount"] < 0
            or scope.get("evseCount") != len(ids)
            or len(ids) != len(set(ids)) or any(not value for value in ids)
            or summary.get("resolvedTariffEvseCount") != len(rows)
            or summary.get("unresolvedEvseCount") != len(missing)
            or summary.get("uniqueTariffCount") != len(data.get("tariffsById") or {})
            or summary.get("http200") != len(rows)
            or any(row.get("tariff", {}).get("id") is None for row in rows)):
        raise ValueError("Swisscharge shard incomplete or mismatched")
    return data


def validate_checkpoint(checkpoint: Path) -> dict[int, dict]:
    valid = {}
    for index in range(PARTITIONS):
        path = checkpoint / f"shard-{index}.json"
        marker = checkpoint / f"shard-{index}.sha256"
        if not path.exists() and not marker.exists():
            continue
        if path.is_file() and not marker.exists():
            # Crash after the atomic shard rename: validate before sealing it.
            validate_part(path, index)
            marker.write_text(digest(path) + "\n", encoding="ascii")
        if not path.is_file() or not marker.is_file() or marker.read_text().strip() != digest(path):
            raise ValueError("Swisscharge checkpoint shard SHA invalid")
        valid[index] = validate_part(path, index)
    return valid


def classify(row: dict) -> str:
    status = row.get("httpStatus")
    reason = row.get("reason")
    body = (row.get("body") or "").lower()
    if reason == "no_tariff":
        return "noTariff"
    if status == 404 and ("not found" in body or "no charge points found" in body):
        return "notFound"
    if isinstance(status, int) and 400 <= status < 500:
        return "other4xx"
    if isinstance(status, int) and status >= 500:
        return "serverError"
    if status in (0, None) and reason == "http_error":
        return "transport"
    return "other"


def validate_output(out: Path) -> dict:
    parts = [validate_part(out / f"shards/shard-{index}.json", index)
             for index in range(PARTITIONS)]
    national = {p["scope"]["nationalEvseCount"] for p in parts}
    ids = [row["physicalReference"] for p in parts
           for row in p["evses"] + p["unresolved"]]
    if len(national) != 1 or len(ids) != next(iter(national)) or len(ids) != len(set(ids)):
        raise ValueError("Swisscharge four-shard national scope incomplete")
    merged = json.loads((out / DATA).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    resolved = [row for p in parts for row in p["evses"]]
    unresolved = [row for p in parts for row in p["unresolved"]]
    tariffs = {}
    for part in parts:
        tariffs.update(part["tariffsById"])
    classes = {name: [] for name in ("notFound", "noTariff", "other4xx", "serverError", "transport", "other")}
    for row in unresolved:
        classes[classify(row)].append(row)
    summary = merged.get("summary") or {}
    scope = merged.get("scope") or {}
    if (merged.get("schemaVersion") != 1 or scope.get("nationalEvseCount") != len(ids)
            or scope.get("shardCount") != PARTITIONS or scope.get("evseCount") != len(ids)
            or merged.get("evses") != resolved or merged.get("unresolved") != unresolved
            or merged.get("tariffsById") != tariffs or merged.get("unresolvedByClass") != classes
            or summary.get("resolvedTariffEvseCount") != len(resolved)
            or summary.get("unresolvedEvseCount") != len(unresolved)
            or summary.get("uniqueTariffCount") != len(tariffs)
            or summary.get("unresolvedClassification") != {key: len(value) for key, value in classes.items()}
            or report.get("nationalEvseCount") != len(ids)
            or report.get("resolvedTariffEvseCount") != len(resolved)
            or report.get("unresolvedEvseCount") != len(unresolved)
            or report.get("semanticScopePending") is not True
            or report.get("productionSource") != str(DATA)):
        raise ValueError("Swisscharge merged artifact differs from validated shards")
    return merged


def run(out: Path, checkpoint: Path, *, runner=subprocess.run, parallel: bool = True) -> None:
    out, checkpoint = out.resolve(), checkpoint.resolve()
    if (out == ROOT or ROOT in out.parents or checkpoint == ROOT or ROOT in checkpoint.parents
            or out == checkpoint or out in checkpoint.parents or checkpoint in out.parents):
        raise ValueError("Swisscharge workspace/checkpoint must be separate and off checkout")
    checkpoint.mkdir(parents=True, exist_ok=True)
    existing = validate_checkpoint(checkpoint)
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)

    def collect(index: int) -> None:
        if index in existing:
            return
        tmp = checkpoint / f"shard-{index}.json.tmp"
        result = runner([sys.executable, str(script), "--output", str(tmp),
                         "--shard-index", str(index), "--shard-count", str(PARTITIONS),
                         "--delay", "0.72"], cwd=out, capture_output=True,
                        text=True, timeout=2400, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Swisscharge shard {index} failed")
        validate_part(tmp, index)
        final = checkpoint / f"shard-{index}.json"
        tmp.replace(final)
        marker = checkpoint / f"shard-{index}.sha256.tmp"
        marker.write_text(digest(final) + "\n", encoding="ascii")
        marker.replace(checkpoint / f"shard-{index}.sha256")

    pending = [index for index in range(PARTITIONS) if index not in existing]
    failures = []
    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=PARTITIONS) as pool:
            futures = [pool.submit(collect, index) for index in pending]
            for future in futures:
                try:
                    future.result()
                except RuntimeError as error:
                    failures.append(error)
    else:
        for index in pending:
            try:
                collect(index)
            except RuntimeError as error:
                failures.append(error)
    if failures:
        raise failures[0]
    parts = validate_checkpoint(checkpoint)
    if len(parts) != PARTITIONS:
        raise ValueError("Swisscharge partition set incomplete")
    shards = out / "shards"
    shards.mkdir(parents=True, exist_ok=True)
    for index in range(PARTITIONS):
        shutil.copy2(checkpoint / f"shard-{index}.json", shards / f"shard-{index}.json")
    national = {part["scope"]["nationalEvseCount"] for part in parts.values()}
    resolved = [row for index in range(PARTITIONS) for row in parts[index]["evses"]]
    unresolved = [row for index in range(PARTITIONS) for row in parts[index]["unresolved"]]
    ids = [row["physicalReference"] for row in resolved + unresolved]
    if len(national) != 1 or len(ids) != next(iter(national)) or len(ids) != len(set(ids)):
        raise ValueError("Swisscharge source partitions incomplete")
    tariffs = {}
    for index in range(PARTITIONS):
        tariffs.update(parts[index]["tariffsById"])
    classes = {name: [] for name in ("notFound", "noTariff", "other4xx", "serverError", "transport", "other")}
    for row in unresolved:
        classes[classify(row)].append(row)
    counts = {key: sum(parts[index]["summary"].get(key, 0) for index in range(PARTITIONS))
              for key in ("http200", "http4xx", "http5xx", "transport", "noTariff")}
    now = datetime.now(timezone.utc).isoformat()
    coverage = round(len(resolved) / len(ids) * 100, 3) if ids else 0
    merged = {"schemaVersion": 1, "source": parts[0].get("source", {}),
              "scope": {"selector": parts[0]["scope"].get("selector"),
                        "nationalEvseCount": len(ids), "evseCount": len(ids), "shardCount": PARTITIONS},
              "summary": {"resolvedTariffEvseCount": len(resolved),
                          "unresolvedEvseCount": len(unresolved), "coveragePct": coverage,
                          "uniqueTariffCount": len(tariffs), **counts,
                          "unresolvedClassification": {key: len(value) for key, value in classes.items()}},
              "tariffsById": tariffs, "evses": resolved, "unresolved": unresolved,
              "unresolvedByClass": classes, "mergedAt": now}
    finalization = {"schemaVersion": 1, "country": "CH", "cpo": "Swisscharge",
                    "status": "coverage-complete-scope-pending", "updatedAt": now,
                    "method": "Swiss national OICP feed CH*SUI*E scope + public Swisscharge ad-hoc tariff API",
                    "nationalEvseCount": len(ids), "resolvedTariffEvseCount": len(resolved),
                    "unresolvedEvseCount": len(unresolved), "coveragePct": coverage,
                    "uniqueTariffCount": len(tariffs),
                    "unresolvedClassification": {key: len(value) for key, value in classes.items()},
                    "policy": "No extrapolation. Unresolved EVSEs remain explicit source gaps.",
                    "semanticScopePending": True,
                    "scopeNote": "CH*SUI may include underlying networks; strict CPO scope remains pending.",
                    "productionSource": str(DATA), "collector": str(SCRIPT)}
    for relative, value in ((DATA, merged), (REPORT, finalization)):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.checkpoint)


if __name__ == "__main__":
    main()
