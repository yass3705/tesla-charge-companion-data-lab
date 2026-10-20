#!/usr/bin/env python3
"""Run preserved Bump public GraphQL harvest and TCC finalization off checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

GRAPHQL = Path("data/national/bump_direct_tariffs_graphql_france.json.gz")
TCC = Path("data/national/bump_direct_tariffs_tcc_france.json.gz")
SUMMARY = Path("reports/bump/national_tariff_harvest_latest.json")
REPORT = Path("reports/bump/tcc_ready_france_latest.json")
FILES = (GRAPHQL, TCC, SUMMARY, REPORT,
         Path("reports/bump_direct_tariffs_graphql_france.md"),
         Path("reports/bump/tcc_ready_france_latest.md"))


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Bump output is not an object: {path}")
    return value


def validate_output(out: Path) -> dict[str, dict]:
    if any(not (out / path).is_file() for path in FILES):
        raise ValueError("Bump GraphQL/TCC output or report missing")
    graph = read_gzip(out / GRAPHQL)
    tcc = read_gzip(out / TCC)
    summary = json.loads((out / SUMMARY).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    if (graph.get("dataset") != "bump-direct-public-graphql-tariffs-france"
            or graph.get("operator") != "Bump" or graph.get("country") != "FR"
            or graph.get("scope", {}).get("directCpoOnly") is not True
            or graph.get("scope", {}).get("roamingIncluded") is not False
            or not isinstance(graph.get("stations"), list)):
        raise ValueError("Bump GraphQL contract invalid")
    if summary.get("counts") != graph.get("counts") or summary.get("failedMapTiles") or summary.get("failedTariffGroups"):
        raise ValueError("Bump GraphQL map/tariff requests or report incomplete")
    if graph["counts"].get("officialStations") != len(graph["stations"]):
        raise ValueError("Bump GraphQL station accounting mismatch")
    if graph["counts"].get("officialPoints") != sum(len(row.get("points") or []) for row in graph["stations"]):
        raise ValueError("Bump GraphQL point accounting mismatch")
    if not isinstance(tcc.get("stations"), list) or tcc.get("country") != "FR" or tcc.get("operator") != "Bump":
        raise ValueError("Bump TCC output contract invalid")
    counts = tcc.get("counts") or {}
    if (counts.get("franceStations") != len(tcc["stations"])
            or counts.get("francePoints") != sum(len(row.get("points") or []) for row in tcc["stations"])
            or counts.get("franceStations", 0) + counts.get("excludedForeignStations", 0) != len(graph["stations"]) 
            or report.get("counts") != counts or tcc.get("variableParseFailures")):
        raise ValueError("Bump TCC finalization accounting mismatch")
    ids = [row.get("stationId") for row in tcc["stations"]]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Bump TCC station identity collision")
    return {"graphql": graph, "tcc": tcc}


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Bump output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "scripts")
    for script in ("bump_graphql_national_tariffs.py", "bump_tcc_ready_france.py"):
        result = runner([sys.executable, str(ROOT / "scripts" / script)], cwd=out, env=env,
                        capture_output=True, text=True, timeout=3600, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Bump method failed: {script}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
