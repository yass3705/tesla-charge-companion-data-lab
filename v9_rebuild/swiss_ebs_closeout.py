#!/usr/bin/env python3
"""Apply archived exact location evidence to a signed EBS first pass."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.cwd_script import validate_output as validate_initial
from v9_rebuild.electroverse import ROOT

DATA = Path("data/switzerland/ebs-ecarup-direct-tariffs.json")
REPORT = Path("docs/switzerland-ebs-finalization-2026-09-28.json")
ARCHIVE = Path("docs/switzerland-ecarup-targeted-national-queries-2026-09-28.json")
INITIAL = Path("inputs/ebs-initial.json")
SCRIPT = Path("scripts/close_swiss_ebs_official_locations.py")
EXACT_IDS = {"CH*EBS*E123*0004", "CH*EBS*E123*0005"}
SAHLI_ID = "CH*EBS*E123*0009"
SAHLI_PROOF = Path("docs/switzerland-ebs-sahli-identity-tariff-probe-2026-09-29.json")
SAHLI_ARCHIVE = Path("inputs/ebs-last-known-validated.json")


def archived_sahli_row(out: Path) -> dict:
    proof = json.loads((out / SAHLI_PROOF).read_text(encoding="utf-8"))
    archived = json.loads((out / SAHLI_ARCHIVE).read_text(encoding="utf-8"))
    rows = [row for row in archived.get("evses", []) if row.get("evseId") == SAHLI_ID]
    if (proof.get("country") != "CH" or proof.get("operatorId") != "CH*EBS"
            or proof.get("targetEvseId") != SAHLI_ID or len(rows) != 1):
        raise ValueError("Swiss EBS Sahli archived identity evidence invalid")
    row = rows[0]
    tariff = row.get("tariff") or {}
    probes = [item.get("tariff") for probe in proof.get("swisschargeProbes", [])
              for item in probe.get("evses", []) if isinstance(item, dict)]
    if (row.get("classificationSource") != "Swisscharge public ad-hoc backend exact site reconciliation"
            or row.get("source") != str(SAHLI_PROOF)
            or not isinstance(row.get("matchedPublicConnectors"), list)
            or len(row["matchedPublicConnectors"]) < 2
            or not any(p and p.get("currency") == tariff.get("currency") == "CHF"
                       and (p.get("pricing") or {}).get("pricePerKwh") == tariff.get("energyPrice")
                       and (p.get("restrictions") or {}).get("applyToAdHocUsers") is True
                       for p in probes)):
        raise ValueError("Swiss EBS Sahli tariff not supported by archived proof")
    return row


def validate_output(out: Path) -> dict:
    initial = json.loads((out / INITIAL).read_text(encoding="utf-8"))
    payload = json.loads((out / DATA).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    original_priced = {row["evseId"]: row for row in initial["evses"]}
    original_missing = {row["evseId"]: row for row in initial["unresolved"]}
    rows, missing = payload.get("evses"), payload.get("unresolved")
    if not isinstance(rows, list) or not isinstance(missing, list):
        raise ValueError("Swiss EBS closeout rows missing")
    priced = {row["evseId"]: row for row in rows}
    unresolved = {row["evseId"]: row for row in missing}
    counts = payload.get("counts") or {}
    new = set(priced) - set(original_priced)
    sahli = archived_sahli_row(out)
    if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
            or payload.get("operatorId") != "CH*EBS"
            or len(priced) != len(rows) or len(unresolved) != len(missing)
            or set(priced) | set(unresolved) != set(original_priced) | set(original_missing)
            or set(priced) & set(unresolved)
            or not new <= (EXACT_IDS | {SAHLI_ID}) & set(original_missing)
            or any(priced[eid] != row for eid, row in original_priced.items())
            or any(unresolved[eid] != row for eid, row in original_missing.items() if eid in unresolved)
            or counts.get("nationalEvseCount") != len(rows) + len(missing)
            or counts.get("pricedEvseCount") != len(rows)
            or counts.get("unresolvedEvseCount") != len(missing)
            or report.get("productionSource") != str(DATA)
            or report.get("status") != ("complete" if not missing else "partial")
            or report.get("pricedEvseCount") != len(rows)
            or report.get("unresolvedEvseCount") != len(missing)
            or any(priced[eid].get("tariff", {}).get("currency") != "CHF"
                   or not isinstance(priced[eid]["tariff"].get("energyPrice"), (int, float))
                   or priced[eid].get("classificationSource") != "official location website"
                   or not priced[eid].get("source") for eid in new if eid in EXACT_IDS)
            or (SAHLI_ID in new and priced[SAHLI_ID] != sahli)
            or not set(payload.get("officialLocationWebsiteResolvedEvseIds") or []) <= set(priced) & EXACT_IDS):
        raise ValueError("Swiss EBS exact location scope invalid")
    return payload


def run(out: Path, source: Path, *, runner=subprocess.run) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents:
        raise ValueError("Swiss EBS closeout must run outside checkout")
    validate_initial(source, "swiss_ebs")
    for relative in (DATA, REPORT, ARCHIVE):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    initial = out / INITIAL
    initial.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / DATA, initial)
    proof = out / SAHLI_PROOF
    proof.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SAHLI_PROOF, proof)
    archive = out / SAHLI_ARCHIVE
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / DATA, archive)
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Swiss EBS location closeout failed")
    payload = json.loads((out / DATA).read_text(encoding="utf-8"))
    unresolved = {row.get("evseId") for row in payload.get("unresolved", [])}
    if SAHLI_ID in unresolved:
        row = archived_sahli_row(out)
        payload["unresolved"] = [item for item in payload["unresolved"] if item.get("evseId") != SAHLI_ID]
        payload["evses"] = sorted([*payload["evses"], row], key=lambda item: item["evseId"])
        payload["counts"]["pricedEvseCount"] = len(payload["evses"])
        payload["counts"]["unresolvedEvseCount"] = len(payload["unresolved"])
        payload["policy"] = "Exact EBS first-pass, official location evidence, and archived exact Sahli ad-hoc proof; no extrapolation."
        (out / DATA).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = json.loads((out / REPORT).read_text(encoding="utf-8"))
        report["pricedEvseCount"] = len(payload["evses"])
        report["unresolvedEvseCount"] = len(payload["unresolved"])
        report["status"] = "complete" if not payload["unresolved"] else "partial"
        report["policy"] = payload["policy"]
        report["method"] = "EBS exact first pass + official location closeout + archived Sahli ad-hoc proof"
        (out / REPORT).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.source)


if __name__ == "__main__":
    main()
