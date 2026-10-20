#!/usr/bin/env python3
"""Preserve exact provenance of legacy methods embedded in YAML workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from v9_scheduled_methods import proposed_destination
from v9_inline_data_review import STEP_NAME, classify
from v9_inline_historical_review import VALIDATION as HISTORICAL_VALIDATION


ARCHIVE_COMMIT = "0b1b9d75463121b6ff86f94764b32d3349ee3e3c"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    workflows = json.loads((root / "migration/v9/legacy-inventory.json").read_text())["workflows"]
    production_linked = {
        row["workflow"]
        for row in json.loads((root / "migration/v9/production-linked-manual-workflows.json").read_text())["rows"]
    }
    critical_reviews = json.loads((root / "migration/v9/inline-critical-review.json").read_text())["workflows"]
    rows = []
    critical_names = set()
    for item in workflows:
        if item["scripts"]:
            continue
        path = root / item["workflow"]
        body = path.read_text(encoding="utf-8", errors="replace")
        has_data_literal = bool(re.search(r"\bdata/[\w./-]+", body))
        priority = (
            "critical" if item["scheduled"] or item["workflow"] in production_linked
            else "data_candidate" if any(p.startswith("data/") for p in item["data_paths"]) or has_data_literal or "izivia/izivia_express_station_tariffs_v1.json" in body
            else "historical_reference"
        )
        review = critical_reviews.get(path.name)
        if priority == "critical":
            critical_names.add(path.name)
            if review is None:
                raise ValueError(f"Critical inline method lacks review: {path.name}")
        elif review is not None:
            raise ValueError(f"Unexpected critical review for noncritical method: {path.name}")
        if priority == "data_candidate":
            role, disposition = classify(path.name)
            if not STEP_NAME.findall(body) and path.name != "ionity-france-pan-inventory.yml":
                raise ValueError(f"Data candidate lacks named steps: {path.name}")
        elif review:
            role, disposition = review["role"], review["disposition"]
        else:
            role = "historical_validation" if HISTORICAL_VALIDATION.search(path.name) else "technical_experiment"
            disposition = "retain_as_validation_reference" if role == "historical_validation" else "archive_experimental_method"
        rows.append({
            "workflow": item["workflow"],
            "archive_commit": ARCHIVE_COMMIT,
            "yaml_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "triggers": item["triggers"],
            "secret_names": item["secrets"],
            "literal_data_paths": item["data_paths"],
            "country_hint": item["country_hint"],
            "proposed_destination_module": proposed_destination(path.name),
            "review_priority": priority,
            "method_role": role,
            "disposition": disposition,
            "method_status": "classified" if role else "inline_yaml_review_pending",
        })
    if critical_names != set(critical_reviews):
        raise ValueError(f"Critical review mismatch: {sorted(set(critical_reviews) - critical_names)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "rows": rows}, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(rows)} inline-only workflows with immutable YAML hashes")


if __name__ == "__main__":
    main()
