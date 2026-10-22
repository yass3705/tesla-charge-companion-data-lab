#!/usr/bin/env python3
"""Isolated execution of the preserved AVIA guest collector and exact national reconciliation."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.orchestrator import ROOT

COLLECT = Path("scripts/collect_avia_switzerland_guest.py")
RECONCILE = Path("scripts/reconcile_avia_switzerland_guest.py")
NATIONAL = Path("data/national/switzerland_oicp_source.json.gz")
OUTPUT = Path("data/switzerland/avia-guest-direct-tariffs.json")
REPORT = Path("docs/switzerland-avia-guest-reconciliation-2026-09-29.json")
INPUT_SHA = Path("input-national-sha256.json")


def validate_output(out: Path) -> dict:
    meta = json.loads((out / INPUT_SHA).read_text(encoding="utf-8"))
    national = out / NATIONAL
    if meta.get("source") != str(NATIONAL) or hashlib.sha256(national.read_bytes()).hexdigest() != meta.get("sha256"):
        raise ValueError("AVIA national source SHA mismatch")
    data = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = data.get("connectors")
    if (data.get("schemaVersion") != 1 or data.get("country") != "CH" or data.get("operatorId") != "CH*AVI"
            or not isinstance(rows, list) or data.get("failures") or data.get("mapErrors")
            or report.get("operatorId") != "CH*AVI" or report.get("collectorFailures") or report.get("collectorMapErrors")):
        raise ValueError("AVIA collector or reconciliation incomplete")
    identities = [(row.get("evseId"), row.get("connectorInternalId")) for row in rows]
    if any(not a or not b for a, b in identities) or len(identities) != len(set(identities)):
        raise ValueError("AVIA connector identities invalid")
    for row in rows:
        price = row.get("price") or {}
        if price.get("pricePerKwhInclVat") is None or not price.get("currency"):
            raise ValueError("AVIA guest price component missing")
    counts = data.get("counts") or {}
    rc = report.get("counts") or {}
    if (counts.get("pricedConnectors") != len(rows)
            or counts.get("uniquePricedEvses") != len({a for a, _ in identities})
            or rc.get("matchedNationalEvseCount", 0) + rc.get("missingNationalEvseCount", 0) != rc.get("nationalEvseCount")
            or rc.get("guestPricedConnectorCount") != len(rows)
            or report.get("policy", {}).get("exactEvseMatch") is not True):
        raise ValueError("AVIA technical counts or exact scope invalid")
    if any(term in (out / OUTPUT).read_text(encoding="utf-8").lower() for term in ("subscription-key", "authorization", "bearer ", "ocp-apim")):
        raise ValueError("AVIA output contains credential marker")
    return report


def run(out: Path, national: Path, *, runner=subprocess.run) -> None:
    out, national = out.resolve(), national.resolve()
    if out == ROOT or ROOT in out.parents or not national.is_file():
        raise ValueError("AVIA collection must run outside checkout with national source")
    raw = gzip.decompress(national.read_bytes())
    json.loads(raw)
    national_copy = out / NATIONAL
    national_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(national, national_copy)
    (out / INPUT_SHA).write_text(json.dumps({"source": str(NATIONAL), "sha256": hashlib.sha256(national_copy.read_bytes()).hexdigest()}) + "\n")
    for method in (COLLECT, RECONCILE):
        target = out / method
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / method, target)
    for path in (OUTPUT, REPORT):
        (out / path).parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, AVIA_OUT=str(OUTPUT))
    result = runner([sys.executable, str(out / COLLECT)], cwd=out, env=environment, capture_output=True, text=True, timeout=3000)
    if result.returncode:
        raise RuntimeError("Historical AVIA guest collector failed")
    bootstrap = """import gzip, io, runpy, urllib.request
from pathlib import Path
source=Path('data/national/switzerland_oicp_source.json.gz')
def offline_open(request, timeout=None):
    if request.full_url != 'https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json':
        raise ValueError('Unexpected Swiss national URL')
    return io.BytesIO(gzip.decompress(source.read_bytes()))
urllib.request.urlopen=offline_open
runpy.run_path('scripts/reconcile_avia_switzerland_guest.py', run_name='__main__')
"""
    reconciled = subprocess.run([sys.executable, "-c", bootstrap], cwd=out, capture_output=True, text=True, timeout=300)
    if reconciled.returncode:
        raise RuntimeError("Historical AVIA national reconciliation failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--national", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.national)


if __name__ == "__main__":
    main()
