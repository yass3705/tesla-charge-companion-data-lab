#!/usr/bin/env python3
"""Create a review matrix for scheduled legacy methods without running them."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


COMMAND_RE = re.compile(r"^\s*(?:(?:-\s*)?run:\s*)?(?:python(?:3)?|node|bash|sh|npx)\s+[^#\n]+")
SPECIAL_DESTINATIONS = {
    "actions-storage": "operations/actions_storage",
    "audit-fixed": "validation/fixed_tariffs",
    "france-irve": "national/fr_irve",
    "belgium-nap": "national/be_nap",
    "netherlands-dotnl": "national/nl_dotnl",
    "spain-reve": "national/es_reve",
    "switzerland-tcc": "national/ch_public_charging",
    "electra": "platform/electra",
    "electroverse": "platform/electroverse",
    "import-tesla": "tesla/mac_ingress",
    "tesla-dataset": "tesla/provenance",
    "suc-tracker": "tesla/suc_tracker",
    "fx-daily": "shared/fx",
    "refresh-fixed-tariffs-bfc": "fixed_tariffs/fr_bfc",
    "refresh-fixed-tariffs-france": "fixed_tariffs/fr",
    "refresh-fixed-tariffs-spain": "fixed_tariffs/es",
    "watch-fixed": "validation/fixed_tariffs",
    "validate-v9": "validation/legacy_progress",
    "france-treated": "validation/fr_progress",
    "france-spie": "validation/fr_spie",
    "france-irve-public-access": "validation/fr_public_access",
    "france-irve-tariff-coverage": "validation/fr_tariff_coverage",
    "avia-picoty": "cpo/avia_picoty",
    "switzerland-avia": "cpo/avia_ch",
    "morocco-total": "cpo/totalenergies",
    "shell-recharge": "cpo/shell_recharge",
    "lidl-plus": "cpo/lidl_plus",
    "uk-connected-kerb": "cpo/connected_kerb",
    "uk-eco-movement": "cpo/eco_movement",
    "uk-source_ev": "cpo/source_ev",
    "uk-validated-open-feeds": "national/uk_open_feeds",
    "switzerland-v9-integration": "national/ch_public_charging",
    "switzerland-post-first-pass": "validation/ch_reconciliation",
    "belgium-final": "national/be_nap",
    "belgium-monta": "national/be_nap",
    "germany-afir": "national/de_afir",
    "france-canonical": "national/fr_irve",
    "uk-zero-cost": "operations/uk_source_audit",
    "validate-v9-source": "validation/legacy_source_guards",
    "audit-electra": "platform/electra",
    "ionity-france": "cpo/ionity",
}


def proposed_destination(name: str) -> str:
    stem = name.removesuffix(".yml").removesuffix(".yaml")
    for prefix in sorted(SPECIAL_DESTINATIONS, key=len, reverse=True):
        if stem.startswith(prefix):
            return SPECIAL_DESTINATIONS[prefix]
    parts = stem.replace("_", "-").split("-")
    if parts[0] in {"uk", "morocco", "switzerland"} and len(parts) > 1:
        return "cpo/" + parts[1]
    return "cpo/" + parts[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    inventory = json.loads((root / "migration/v9/legacy-inventory.json").read_text())
    reviewed = json.loads((root / "migration/v9/scheduled-scope-review.json").read_text())["workflows"]
    rows = []
    seen_overrides = set()
    for item in inventory["workflows"]:
        if not item["scheduled"]:
            continue
        name = Path(item["workflow"]).name
        override = reviewed.get(name)
        if item["country_hint"] is None:
            if override is None:
                raise ValueError(f"Scheduled workflow lacks scope review: {name}")
            seen_overrides.add(name)
        elif override is not None:
            raise ValueError(f"Unexpected override for unambiguous country: {name}")
        body = (root / item["workflow"]).read_text(encoding="utf-8", errors="replace")
        commands = sorted({line.strip() for line in body.splitlines() if COMMAND_RE.match(line)})
        rows.append({
            "workflow": item["workflow"],
            "scope": override["scope"] if override else [item["country_hint"]],
            "role": override["role"] if override else "requires_role_review",
            "commands": commands,
            "scripts": item["scripts"],
            "missing_script_references": item["missing_script_references"],
            "secret_names": item["secrets"],
            "literal_data_paths": item["data_paths"],
            "proposed_destination_module": proposed_destination(name),
            "destination_module": None,
            "review_status": "pending_method_and_output_review",
        })
    if seen_overrides != set(reviewed):
        raise ValueError(f"Unused scope reviews: {sorted(set(reviewed) - seen_overrides)}")
    if len(rows) != 117:
        raise ValueError(f"Expected current baseline of 117 scheduled workflows, found {len(rows)}")
    payload = {"schema_version": 1, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} scheduled methods; {sum(bool(r['commands']) for r in rows)} with parsed commands")


if __name__ == "__main__":
    main()
