#!/usr/bin/env python3
"""Build the provisional source-to-module migration registry."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from v9_scheduled_methods import proposed_destination

SCRIPT_ONLY_DESTINATIONS = {
    "scripts/allego_station_tariffs.py": "cpo/allego",
    "scripts/allego_station_tariffs_fast.py": "cpo/allego",
    "scripts/atlante/package_results.py": "cpo/atlante",
    "scripts/audit_after_minutes_current_v9_20261011.cjs": "validation/tariff_components",
    "scripts/audit_after_minutes_live_verified_20261011.cjs": "validation/tariff_components",
    "scripts/audit_after_minutes_production_20261011.cjs": "validation/tariff_components",
    "scripts/audit_after_minutes_staging_20261011.cjs": "validation/tariff_components",
    "scripts/audit_dotnl_pinned_transition.py": "national/nl_dotnl",
    "scripts/audit_electra_78_current_overlay_20261011.cjs": "platform/electra",
    "scripts/audit_electroverse_uk_national_details.py": "platform/electroverse",
    "scripts/audit_electroverse_uk_national_tiles.py": "platform/electroverse",
    "scripts/audit_live_v9_after_minutes_20261011.cjs": "validation/tariff_components",
    "scripts/audit_swiss_ecarup_60_deep.py": "cpo/ecarup",
    "scripts/build_electra_78_afterminutes_evidence_matrix_20261011.cjs": "platform/electra",
    "scripts/build_electroverse_final_residual_recovery_plan.mjs": "platform/electroverse",
    "scripts/build_powerdot_evse_technical_inventory.mjs": "cpo/powerdot",
    "scripts/build_vianeo_official_identity_map.mjs": "cpo/vianeo",
    "scripts/compare_electroverse_main_vs_duration_lab.mjs": "platform/electroverse",
    "scripts/debug_electroverse_p01_crossop_parent.mjs": "platform/electroverse",
    "scripts/electroverse_collect_live_evse_statuses.mjs": "platform/electroverse",
    "scripts/electroverse_incremental_refresh.mjs": "platform/electroverse",
    "scripts/france/audit_active_irve_station_matches.py": "national/fr_irve",
    "scripts/france/audit_pinned_irve_transition.py": "national/fr_irve",
    "scripts/france_cpo_coverage_audit.py": "validation/fr_progress",
    "scripts/france_pricing_real_offer_pilot_20261009.cjs": "validation/tariff_components",
    "scripts/freshmile_restore_unresolved_points.py": "cpo/freshmile",
    "scripts/ionity_reconcile_inventory.py": "cpo/ionity",
    "scripts/lib/electroverse_direct_client.mjs": "platform/electroverse",
    "scripts/lidl_uk_official_pricing.py": "cpo/lidl",
    "scripts/morocco_integration_guard.py": "validation/ma_integration",
    "scripts/operator_batch_controller.py": "operations/operator_batch",
    "scripts/reconcile_electroverse_uk_national_tiles.py": "platform/electroverse",
    "scripts/reconcile_uk_canonical.py": "national/uk_open_feeds",
    "scripts/reve-v2-snapshot.mjs": "national/es_reve",
    "scripts/saint_cyr_targeted_live_status.mjs": "validation/fr_targeted_status",
    "scripts/suc_tracker/compare_mac.py": "tesla/suc_tracker",
    "scripts/suc_tracker/core.py": "tesla/suc_tracker",
    "scripts/tariff_after_minutes_candidate_20261009.cjs": "validation/tariff_components",
    "scripts/tesla_complete_config_pricing_audit_20261009.cjs": "tesla/provenance",
    "scripts/tesla_global_pricing_real_rule_pilot_20261009.cjs": "tesla/provenance",
    "scripts/uk_geniepoint_official_collect.py": "cpo/geniepoint",
    "scripts/ze-watt/extract_ze_watt.py": "cpo/zewatt",
    "scripts/zephyre/extract_zephyre_epowerdirect.mjs": "cpo/zephyre",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    scheduled = json.loads((root / "migration/v9/scheduled-methods.json").read_text())["rows"]
    manual = json.loads((root / "migration/v9/production-linked-manual-workflows.json").read_text())["rows"]
    unreferenced = {
        item["path"] for item in json.loads((root / "migration/v9/legacy-inventory.json").read_text())["scripts"]
        if not item["referenced_by_workflow"]
    }
    if unreferenced != set(SCRIPT_ONLY_DESTINATIONS):
        raise ValueError(f"Script-only destinations missing/extra: {sorted(unreferenced - set(SCRIPT_ONLY_DESTINATIONS))} / {sorted(set(SCRIPT_ONLY_DESTINATIONS) - unreferenced)}")
    groups: dict[str, dict] = defaultdict(lambda: {"methods": [], "country_scope": set(), "secrets": set(), "data_paths": set(), "production_linked_paths": set()})
    for row in scheduled:
        module = row["proposed_destination_module"]
        group = groups[module]
        group["methods"].append({"workflow": row["workflow"], "kind": "scheduled", "migration_status": "method_review_pending"})
        group["country_scope"].update(row["scope"])
        group["secrets"].update(row["secret_names"])
        group["data_paths"].update(row["literal_data_paths"])
    for row in manual:
        module = proposed_destination(Path(row["workflow"]).name)
        group = groups[module]
        group["methods"].append({"workflow": row["workflow"], "kind": "manual_or_indirect_production_linked", "migration_status": "method_review_pending"})
        if row["country_hint"]:
            group["country_scope"].add(row["country_hint"])
        group["secrets"].update(row["secret_names"])
        group["production_linked_paths"].update(p["path"] for p in row["production_linked_paths"])
        group["data_paths"].update(p["path"] for p in row["production_linked_paths"])
    for script, module in sorted(SCRIPT_ONLY_DESTINATIONS.items()):
        groups[module]["methods"].append({"script": script, "kind": "script_without_literal_workflow_reference", "migration_status": "method_review_pending"})
    modules = []
    for name, group in sorted(groups.items()):
        modules.append({
            "candidate_module": name,
            "status": "provisional_method_destination",
            "country_scope_hints": sorted(group["country_scope"]),
            "methods": sorted(group["methods"], key=lambda row: row.get("workflow") or row["script"]),
            "secret_names": sorted(group["secrets"]),
            "literal_data_paths": sorted(group["data_paths"]),
            "literal_production_linked_paths": sorted(group["production_linked_paths"]),
        })
    payload = {
        "schema_version": 1,
        "status": "provisional; not a G1 signoff",
        "coverage": "117 scheduled workflows, 61 manual/indirect workflows with literal Production references, and 43 scripts without literal workflow references; all other workflows remain in legacy-inventory.json",
        "modules": modules,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(modules)} candidate modules, {sum(len(m['methods']) for m in modules)} methods")


if __name__ == "__main__":
    main()
