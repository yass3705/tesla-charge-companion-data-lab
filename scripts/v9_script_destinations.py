#!/usr/bin/env python3
"""Map every preserved legacy script to candidate software modules."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from v9_scheduled_methods import proposed_destination
from v9_source_registry import SCRIPT_ONLY_DESTINATIONS


EXPLICIT_DESTINATIONS = {
    "scripts/public_safety_check.py": "shared/public_safety",
    "scripts/operator_manifest_runner.py": "shared/operator_manifest",
    "scripts/collect_swiss_atlas_cpo.py": "national/ch_public_charging",
    "scripts/collect_swiss_atlas_cpo_parallel.py": "national/ch_public_charging",
    "scripts/collect_uk_validated_open_feeds.py": "national/uk_open_feeds",
    "scripts/dotnl_national_tariff_guard.py": "national/nl_dotnl",
    "scripts/dotnl_netherlands_access_patch.py": "national/nl_dotnl",
    "scripts/dotnl_netherlands_build.py": "national/nl_dotnl",
    "scripts/dotnl_netherlands_runtime.py": "national/nl_dotnl",
    "scripts/electra_nl_emsp_national_stage.py": "platform/electra",
    "scripts/electroverse_uk_cpo_pilot.mjs": "platform/electroverse",
    "scripts/loadmotion/compile_loadmotion_v9_offers.mjs": "cpo/loadmotion",
    "scripts/morocco_numocity_url_construction_probe.py": "cpo/numocity",
    "scripts/powerdot_official.py": "cpo/powerdot",
    "scripts/pun_italy_national.py": "national/it_pun",
    "scripts/reconcile_swiss_first_pass_national.py": "national/ch_public_charging",
    "scripts/swisscharge_home_probe.py": "cpo/swisscharge",
    "scripts/tesla_global_tariff_inventory_20261009.py": "tesla/provenance",
    "scripts/tesla_source_selection_audit_20261009.py": "tesla/provenance",
    "scripts/uk_pcpr_cpo_collect.py": "shared/uk_pcpr",
    "scripts/archive_global_tariff_scenario_review.py": "validation/tariff_components",
    "scripts/audit_electroverse_full_reconciliation.mjs": "platform/electroverse",
    "scripts/audit_swiss_owner_gap_atlas.py": "national/ch_public_charging",
    "scripts/audit_swiss_owner_gap_ecarup.py": "national/ch_public_charging",
    "scripts/audit_switzerland_public_access_field.py": "national/ch_public_charging",
    "scripts/avia_picoty_authenticated_bootstrap_probe.py": "cpo/avia_picoty",
    "scripts/avia_picoty_deftpower_smoke.py": "cpo/avia_picoty",
    "scripts/avia_picoty_residual_probe.py": "cpo/avia_picoty",
    "scripts/collect_avia_picoty_france_guest.py": "cpo/avia_picoty",
    "scripts/compile_bump_runtime_offers.py": "cpo/bump",
    "scripts/count_swiss_national_owners.py": "national/ch_public_charging",
    "scripts/driveco_direct_scope_reconciliation.py": "cpo/driveco",
    "scripts/electroverse_live_priority_price_probe.mjs": "platform/electroverse",
    "scripts/electroverse_uk_national_seeds.py": "platform/electroverse",
    "scripts/electroverse_uk_national_tiles.mjs": "platform/electroverse",
    "scripts/france/audit_irve_emsp_alphanumeric_residuals.mjs": "validation/fr_emsp_join",
    "scripts/france/investigate_alphanumeric_electroverse_candidates.mjs": "validation/fr_emsp_join",
    "scripts/france/probe_anyos_monta.py": "cpo/anyos",
    "scripts/france_runtime_offer_fixtures_20261009.py": "validation/tariff_components",
    "scripts/inspect_swiss_owner_gap_context.py": "national/ch_public_charging",
    "scripts/integrate_total_nl_chargingservices.py": "cpo/totalenergies",
    "scripts/morocco_fastvolt_evone_resource_keys_probe.py": "cpo/fastvolt",
    "scripts/morocco_public_probe.py": "validation/ma_integration",
    "scripts/nextcharge_ges_national.py": "cpo/nextcharge",
    "scripts/nl_5246_uncomputable_tariff_diagnostic.py": "national/nl_dotnl",
    "scripts/nl_agrigo_embedded_map_probe_20261011.py": "cpo/agrigo",
    "scripts/nl_agrigo_official_map_match_20261011.py": "cpo/agrigo",
    "scripts/nl_agrigo_qr_discovery_20261011.py": "cpo/agrigo",
    "scripts/nl_cpo_direct_price_provenance_20261011.py": "national/nl_dotnl",
    "scripts/nl_cpo_direct_residual_inventory_20261011.py": "national/nl_dotnl",
    "scripts/nl_dotnl_active_supported_tariff_gaps_20261011.py": "national/nl_dotnl",
    "scripts/nl_gfx_exact_tariff_crosswalk_20261011.py": "cpo/totalenergies",
    "scripts/nl_gfx_totalenergies_exact_missing_classification_20261011.py": "cpo/totalenergies",
    "scripts/probe_swiss_small_cpo_national_context.py": "national/ch_public_charging",
    "scripts/reconcile_swiss_owner_gap_national.py": "national/ch_public_charging",
    "scripts/reconcile_swiss_owner_gap_normalized.py": "national/ch_public_charging",
    "scripts/reconcile_swiss_second_pass_national.py": "national/ch_public_charging",
    "scripts/seed_france_last_good_static.py": "national/fr_irve",
    "scripts/tariff_global_inventory_20261009.py": "validation/tariff_components",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    inv = json.loads((root / "migration/v9/legacy-inventory.json").read_text())
    refs: dict[str, list[str]] = defaultdict(list)
    for workflow in inv["workflows"]:
        for script in workflow["scripts"]:
            refs[script].append(workflow["workflow"])
    rows = []
    for item in inv["scripts"]:
        path = item["path"]
        workflows = sorted(refs.get(path, []))
        modules = sorted({proposed_destination(Path(w).name) for w in workflows})
        if not workflows:
            modules = [SCRIPT_ONLY_DESTINATIONS[path]]
        elif path in EXPLICIT_DESTINATIONS:
            modules = [EXPLICIT_DESTINATIONS[path]]
        rows.append({
            "script": path,
            "workflow_references": workflows,
            "candidate_modules": modules,
            "review_status": "ambiguous_shared_method" if len(modules) != 1 else "candidate_destination_pending_review",
        })
    if len(rows) != 756:
        raise ValueError(f"Historical script count changed: {len(rows)}")
    payload = {"schema_version": 1, "status": "provisional; no script deleted", "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(rows)} scripts, {sum(len(row['candidate_modules']) != 1 for row in rows)} ambiguous destinations")


if __name__ == "__main__":
    main()
