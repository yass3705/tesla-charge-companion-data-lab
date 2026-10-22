#!/usr/bin/env python3
"""Run the preserved Swiss AGR, Atlas reconciliation and SOC second-pass methods."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.orchestrator import ROOT

NATIONAL = Path("data/national/switzerland_oicp_source.json.gz")
AGR = Path("data/switzerland/agr-monta-direct-tariffs.json")
AGR_REPORT = Path("docs/switzerland-agr-finalization-2026-09-28.json")
SOC = Path("data/switzerland/soc-direct-tariffs-second-pass.json")
SOC_REPORT = Path("docs/switzerland-soc-second-pass-2026-09-28.json")
SCRIPTS = (Path("scripts/finalize_swiss_agr_monta.py"), Path("scripts/reconcile_swiss_atlas_scope.py"), Path("scripts/collect_swiss_atlas_cpo.py"))
ATLAS = (("CH*LDL", "lidl", "Lidl"), ("CH*IOY", "ioy", "IONITY"), ("CH*EDH", "edh", "Energiedienst CH"), ("DE*EDH", "de-edh", "Energiedienst DE"))
INPUTS = (NATIONAL,) + tuple(Path(f"data/switzerland/{slug}-direct-tariffs.json") for _, slug, _ in ATLAS)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_output(out: Path) -> dict:
    hashes = json.loads((out / "input-sha256.json").read_text(encoding="utf-8"))
    if set(hashes) != {str(path) for path in INPUTS} or any(sha(out / name) != digest for name, digest in hashes.items()):
        raise ValueError("Swiss closeout input SHA mismatch")
    agr = json.loads((out / AGR).read_text(encoding="utf-8"))
    agr_report = json.loads((out / AGR_REPORT).read_text(encoding="utf-8"))
    agr_ids = [row.get("evseId") for row in agr.get("evses") or []]
    ac = agr.get("counts") or {}
    if (agr.get("operatorId") != "CH*AGR" or agr_report.get("operatorId") != "CH*AGR"
            or len(agr_ids) != len(set(agr_ids)) or ac.get("matchedPricedEvseCount") != len(agr_ids)
            or ac.get("nationalEvseCount") != len(agr_ids) + ac.get("missingEvseCount", -1)
            or agr_report.get("pricedEvseCount") != len(agr_ids)
            or agr_report.get("missingEvseCount") != ac.get("missingEvseCount")):
        raise ValueError("Swiss AGR exact EVSE scope invalid")
    for operator, slug, _ in ATLAS:
        doc = json.loads((out / f"docs/switzerland-{slug}-scope-reconciliation-2026-09-28.json").read_text(encoding="utf-8"))
        counts = {name: doc.get(name) for name in ("nationalEvseCount", "matchedNationalEvseCount", "missingFromAtlasCount", "pricedNationalEvseCount", "unpricedNationalEvseCount")}
        if (doc.get("operatorId") != operator or counts["nationalEvseCount"] != counts["matchedNationalEvseCount"] + counts["missingFromAtlasCount"]
                or counts["nationalEvseCount"] != counts["pricedNationalEvseCount"] + counts["unpricedNationalEvseCount"]
                or counts["missingFromAtlasCount"] != len(doc.get("missingFromAtlasEvseIds") or [])
                or counts["unpricedNationalEvseCount"] != len(doc.get("unpricedNationalEvseIds") or [])):
            raise ValueError(f"Swiss Atlas exact scope invalid: {slug}")
    soc = json.loads((out / SOC).read_text(encoding="utf-8"))
    report = json.loads((out / SOC_REPORT).read_text(encoding="utf-8"))
    summary = soc.get("summary") or {}
    stations = soc.get("stations") or []
    if (soc.get("operatorId") != "CH*SOC" or report.get("operatorId") != "CH*SOC"
            or summary.get("stationCount") != len(stations)
            or summary.get("stationsWithDirectTariff", 0) + summary.get("stationsWithoutDirectTariff", 0) != len(stations)
            or report.get("stationsWithDirectTariff") != summary.get("stationsWithDirectTariff")
            or report.get("stationsWithoutDirectTariff") != summary.get("stationsWithoutDirectTariff")):
        raise ValueError("Swiss SOC second-pass scope invalid")
    for station in stations:
        if not station.get("stationId") or station.get("evseOperator") != "CH*SOC":
            raise ValueError("Swiss SOC station identity invalid")
        for point in station.get("chargePoints") or []:
            if point.get("status") != 200:
                raise ValueError("Swiss SOC tariff detail request incomplete")
            for tariff in point.get("directTariffs") or []:
                attrs = tariff.get("attributes") or {}
                emp = ((tariff.get("emp") or {}).get("id")
                       or (((tariff.get("emp") or {}).get("attributes") or {}).get("id")))
                cpo = ((tariff.get("cpo") or {}).get("id")
                       or (((tariff.get("cpo") or {}).get("attributes") or {}).get("id")))
                if attrs.get("is_roaming") is not False or not emp or emp != cpo:
                    raise ValueError("Swiss SOC roaming price in direct scope")
    return report


def run(out: Path, *, runner=subprocess.run, monta_fixture: Path | None = None) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Swiss closeout must run outside checkout")
    hashes = {}
    for path in INPUTS:
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, target)
        hashes[str(path)] = sha(target)
    (out / "input-sha256.json").write_text(json.dumps(hashes, sort_keys=True) + "\n")
    for path in SCRIPTS:
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, target)
    (out / "docs").mkdir(exist_ok=True)
    bootstrap = """import gzip, io, runpy, sys, urllib.request
from pathlib import Path
national=Path('data/national/switzerland_oicp_source.json.gz')
monta=Path('input_monta_fixture.json')
original=urllib.request.urlopen
def source_open(request, timeout=None):
    url=request.full_url
    if url == 'https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json':
        return io.BytesIO(gzip.decompress(national.read_bytes()))
    if url == 'https://monta.imgix.net/roaming-data/monta-as-a-cpo-pricing.json' and monta.exists():
        return io.BytesIO(monta.read_bytes())
    if url != 'https://monta.imgix.net/roaming-data/monta-as-a-cpo-pricing.json':
        raise ValueError('Unexpected Swiss source URL')
    return original(request, timeout=timeout)
urllib.request.urlopen=source_open
script = sys.argv[1]
sys.argv = [script] + sys.argv[2:]
runpy.run_path(script, run_name='__main__')
"""
    if monta_fixture is not None:
        shutil.copy2(monta_fixture, out / "input_monta_fixture.json")
    for script, args in [(SCRIPTS[0], [])] + [(SCRIPTS[1], ["--operator", operator, "--slug", slug, "--name", name]) for operator, slug, name in ATLAS]:
        completed = subprocess.run([sys.executable, "-c", bootstrap, str(script), *args], cwd=out, capture_output=True, text=True, timeout=300)
        if completed.returncode:
            raise RuntimeError(f"Historical Swiss closeout failed: {script}")
    command = [sys.executable, str(out / SCRIPTS[2]), "--operator", "CH*SOC", "--name", "SOCAR / CH*SOC", "--output", str(SOC), "--delay", "0.12", "--provider-customer-tariffs"]
    completed = runner(command, cwd=out, capture_output=True, text=True, timeout=1800)
    if completed.returncode:
        raise RuntimeError("Historical Swiss SOC second pass failed")
    soc = json.loads((out / SOC).read_text(encoding="utf-8"))
    summary = soc["summary"]
    doc = {"schemaVersion": 1, "country": "CH", "cpo": "SOCAR / CH*SOC", "operatorId": "CH*SOC",
           "status": summary["status"], "stationCount": summary["stationCount"],
           "stationsWithDirectTariff": summary["stationsWithDirectTariff"],
           "stationsWithoutDirectTariff": summary["stationsWithoutDirectTariff"],
           "coveragePct": summary["coveragePct"], "unresolved": soc.get("unresolved", []),
           "method": "Second pass with provider_customer_tariffs=true; direct-only is_roaming=false and EMP=CPO",
           "policy": "No cross-station extrapolation. Provider-customer results remain evidence and require exact station applicability.",
           "productionSource": str(SOC)}
    (out / SOC_REPORT).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
