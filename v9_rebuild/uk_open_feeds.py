#!/usr/bin/env python3
"""Run the twelve preserved UK open feeds in an isolated staging directory."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/collect_uk_validated_open_feeds.py")
RAW = Path("artifacts/uk-validated-open-feeds.json")
OUTPUT = Path("data/national/uk_validated_open_feeds.json.gz")
REPORT = Path("reports/uk/validated-open-feeds-latest.json")


def validate_output(out: Path) -> dict:
    with gzip.open(out / OUTPUT, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    sources = payload.get("sources") or []
    # The historical script defines this closed list of feed methods; counts
    # of stations, EVSEs and tariffs remain data, never acceptance thresholds.
    known_names = {row["name"] for row in json.loads((ROOT / "migration/v9/uk-open-feeds-source-names.json").read_text())}
    if (payload.get("schemaVersion") != 1 or payload.get("country") != "GB"
            or payload.get("failures") or len(sources) != len(known_names)
            or {row.get("name") for row in sources} != known_names
            or summary.get("requestedSources") != len(known_names)
            or summary.get("successfulSources") != len(known_names)
            or summary.get("failedSources") != 0
            or any(not isinstance(row.get("locations"), list) or not isinstance(row.get("tariffs"), list)
                   or row.get("summary", {}).get("locations") != len(row["locations"])
                   or row.get("summary", {}).get("tariffs") != len(row["tariffs"])
                   or row.get("summary", {}).get("missingTariffIds") is None
                   for row in sources)
            or any(row.get("name") == "PoGo Charge" and
                   (row.get("sourceAudit") or {}).get("coverageComplete") is not True for row in sources)
            or report.get("summary") != summary or report.get("failures") != []
            or {row.get("name") for row in report.get("sources", [])} != known_names):
        raise ValueError("UK open-feed completeness, schema or report contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("UK feeds must run off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    raw = out / RAW
    completed = runner([sys.executable, str(script), "--output", str(raw)], cwd=out,
                       capture_output=True, text=True, timeout=3000, check=False)
    if completed.returncode:
        raise RuntimeError("Historical UK open-feed method failed")
    payload = json.loads(raw.read_text(encoding="utf-8"))
    output = out / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
    report = out / REPORT
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"country": payload.get("country"), "retrievedAt": payload.get("retrievedAt"),
                                  "summary": payload.get("summary"), "failures": payload.get("failures"),
                                  "sources": [{"name": row.get("name"), "summary": row.get("summary")}
                                              for row in payload.get("sources", [])]}, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
