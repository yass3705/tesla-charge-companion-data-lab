#!/usr/bin/env python3
"""Report G2 readiness without treating a partial collector migration as PASS."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1_COMMIT = "15657f4a89c98e5e7c1d119c91c6cb55a891a913"
REQUIRED_METHOD_DISPOSITIONS = {
    "retain_scheduled_data_method",
    "retain_scheduled_partial_method",
    "retain_production_dependency",
}


def main() -> None:
    errors = []
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
    expected = {"v9-check.yml", "v9-collect.yml"}
    if {path.name for path in workflows} != expected:
        errors.append("active workflow set differs from the two approved read-only workflows")
    for path in workflows:
        body = path.read_text(encoding="utf-8")
        forbidden = ("contents: write", "git push", "workflow_run:", "repository_dispatch:", "push:", "pull_request_target:")
        if any(token in body for token in forbidden) or "contents: read" not in body:
            errors.append(f"workflow write/trigger risk: {path.name}")
    if not (ROOT / "scripts/operator_manifest_runner.py").is_file():
        errors.append("migrated operator module missing")
    archived = subprocess.run(["git", "cat-file", "-t", G1_COMMIT], cwd=ROOT, capture_output=True, text=True, check=False)
    if archived.returncode != 0 or archived.stdout.strip() != "commit":
        errors.append("G1 workflow archive commit unavailable")
    sources = json.loads((ROOT / "v9_rebuild/sources.json").read_text())["sources"]
    handoff_pending = sorted(spec["id"] for spec in sources
                             if spec.get("github_handoff") == "unverified"
                             or "github_handoff_unverified" in spec.get("status", ""))
    if handoff_pending:
        errors.append(f"GitHub artifact handoffs remain unverified: {len(handoff_pending)}")
    live_pending = sorted(spec["id"] for spec in sources
                          if spec.get("live") == "pending" or "live_pending" in spec.get("status", ""))
    original = {row["workflow"]: row for row in json.loads((ROOT / "migration/v9/legacy-inventory.json").read_text())["workflows"]}
    final = json.loads((ROOT / "migration/v9/method-dispositions.json").read_text())
    migrated = set()
    for spec in sources:
        method = ("scripts/operator_manifest_runner.py" if spec["module"] == "operator_manifest"
                  else "scripts/dotnl_netherlands_build.py" if spec["module"] == "nl_dotnl"
                  else "scripts/electroverse_hybrid_refresh.mjs" if spec["module"] == "electroverse"
                  else "scripts/electroverse_status_incremental.mjs" if spec["module"] == "electroverse_status"
                  else "scripts/build_electroverse_france_evse_overlay.mjs" if spec["module"] == "electroverse_overlay"
                  else spec["script"] if spec["module"] == "isolated_script"
                  else "scripts/belib_official.py" if spec["module"] == "belib_chain"
                  else "scripts/ionity_station_tariffs.py" if spec["module"] == "ionity_family"
                  else "scripts/fastned_station_inventory.py" if spec["module"] == "fastned_family"
                  else "scripts/bump_direct_inventory.py" if spec["module"] == "bump_inventory_family"
                  else "scripts/bump_graphql_national_tariffs.py" if spec["module"] == "bump_tariffs"
                  else "scripts/bump_official.py" if spec["module"] == "bump_official"
                  else "scripts/allego_dxp_national.py" if spec["module"] == "allego_stations"
                  else "scripts/allego_official.py" if spec["module"] == "allego_official"
                  else f"scripts/{spec['source']}_official.py" if spec["module"] == "official_rules"
                  else "scripts/update_fx.py" if spec["module"] == "fx"
                  else "scripts/suc_tracker/update.py" if spec["module"] == "suc_tracker"
                  else "scripts/import_tesla_mac_ingress.py" if spec["module"] == "tesla_mac"
                  else "scripts/qwello_saone_et_loire_official.py" if spec["module"] == "cwd_script" and spec["method"] == "qwello_saone_et_loire"
                  else "scripts/reveo_official.py" if spec["module"] == "cwd_script" and spec["method"] == "reveo_official"
                  else "scripts/avia_picoty_national.py" if spec["module"] == "cwd_script" and spec["method"] == "avia_picoty_inventory"
                  else "scripts/waat_national.py" if spec["module"] == "cwd_script" and spec["method"] == "waat_inventory"
                  else "scripts/finalize_swiss_fastned_official.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_fastned"
                  else "scripts/finalize_swiss_lidl_official.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_lidl"
                  else "scripts/finalize_swiss_ionity_national.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_ionity"
                  else "scripts/finalize_swiss_plenitude_official.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_plenitude"
                  else "scripts/finalize_swiss_ail_emoti.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_ail"
                  else "scripts/finalize_swiss_ebs_ecarup.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_ebs"
                  else "scripts/finalize_swiss_ewd_official.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_ewd"
                  else "scripts/finalize_swiss_migrol_official.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_migrol"
                  else "scripts/etotem_direct_station_inventory.py" if spec["module"] == "cwd_script"
                  else "scripts/france/build_france_irve_static_v9.py" if spec["module"] == "france_irve"
                  else "scripts/build_france_canonical_dataset.py" if spec["module"] == "france_canonical"
                  else "scripts/uk_blink_pcpr_collect.py" if spec["module"] == "uk_blink"
                  else "scripts/uk_pcpr_cpo_collect.py" if spec["module"] == "uk_pcpr"
                  else "scripts/uk_evyve_pcpr_collect.py" if spec["module"] == "uk_evyve"
                  else "scripts/uk_gridserve_pcpr_collect.py" if spec["module"] == "uk_gridserve"
                  else "scripts/uk_ubitricity_pcpr_collect.py" if spec["module"] == "uk_ubitricity"
                  else "scripts/avia_picoty_irve_extract.py" if spec["module"] == "avia_picoty_extract"
                  else "scripts/electric55_station_base.py" if spec["module"] == "electric55_chain"
                  else "scripts/freshmile_direct_inventory.py" if spec["module"] == "freshmile_inventory"
                  else "scripts/waat_monta_shard.mjs" if spec["module"] == "waat_monta_sharded"
                  else "scripts/waat_monta_public_tariffs.mjs" if spec["module"] == "waat_monta_public"
                  else spec["script"])
        source_code = ROOT / (spec["manifest"] if spec["module"] == "operator_manifest" else "v9_rebuild/belib.py" if spec["module"] == "belib_chain" else "v9_rebuild/ionity.py" if spec["module"] == "ionity_family" else "v9_rebuild/fastned.py" if spec["module"] == "fastned_family" else "v9_rebuild/bump_inventory.py" if spec["module"] == "bump_inventory_family" else "v9_rebuild/bump_tariffs.py" if spec["module"] == "bump_tariffs" else "v9_rebuild/bump_official.py" if spec["module"] == "bump_official" else "v9_rebuild/allego_stations.py" if spec["module"] == "allego_stations" else "v9_rebuild/allego_official.py" if spec["module"] == "allego_official" else "v9_rebuild/official_rules.py" if spec["module"] == "official_rules" else "v9_rebuild/fx.py" if spec["module"] == "fx" else "v9_rebuild/suc_tracker.py" if spec["module"] == "suc_tracker" else "v9_rebuild/tesla_mac.py" if spec["module"] == "tesla_mac" else "v9_rebuild/cwd_script.py" if spec["module"] == "cwd_script" else "v9_rebuild/france_irve.py" if spec["module"] == "france_irve" else "v9_rebuild/france_canonical.py" if spec["module"] == "france_canonical" else "v9_rebuild/uk_blink.py" if spec["module"] == "uk_blink" else "v9_rebuild/uk_pcpr.py" if spec["module"] == "uk_pcpr" else "v9_rebuild/uk_evyve.py" if spec["module"] == "uk_evyve" else "v9_rebuild/uk_gridserve.py" if spec["module"] == "uk_gridserve" else "v9_rebuild/uk_ubitricity.py" if spec["module"] == "uk_ubitricity" else "v9_rebuild/avia_picoty_extract.py" if spec["module"] == "avia_picoty_extract" else "v9_rebuild/electric55_chain.py" if spec["module"] == "electric55_chain" else "v9_rebuild/freshmile_inventory.py" if spec["module"] == "freshmile_inventory" else "v9_rebuild/waat_monta_sharded.py" if spec["module"] == "waat_monta_sharded" else "v9_rebuild/waat_monta_public.py" if spec["module"] == "waat_monta_public" else method)
        if not source_code.is_file():
            errors.append(f"source method/config missing: {spec['id']}")
        for workflow in spec.get("legacy_workflows", []):
            workflow_method = ("scripts/belib_official.py" if workflow.endswith("belib-official-tariffs.yml")
                               else "scripts/belib_station_base.py" if workflow.endswith("belib-station-base.yml")
                               else "scripts/ionity_station_tariffs_uk.py" if workflow.endswith("ionity-direct-uk-station-tariffs.yml")
                               else "scripts/fastned_station_inventory_uk.py" if workflow.endswith("fastned-direct-station-inventory-uk.yml")
                               else "scripts/bump_direct_station_tariffs.py" if workflow.endswith("bump-direct-station-tariffs.yml")
                               else "scripts/bump_tcc_ready_france.py" if workflow.endswith("bump-tcc-ready-france.yml")
                               else "scripts/uk_blink_pcpr_validate.py" if workflow.endswith("uk-blink-pcpr-audit.yml")
                               else method)
            if workflow not in original or workflow in migrated:
                errors.append(f"invalid or duplicate legacy workflow mapping: {workflow}")
            elif workflow_method not in original[workflow]["scripts"]:
                errors.append(f"legacy workflow uses a different extraction method: {workflow}")
            else:
                migrated.add(workflow)
    required = {row["workflow"] for row in final["workflow_rows"] if row["disposition"] in REQUIRED_METHOD_DISPOSITIONS}
    pending = sorted(required - migrated)
    if pending:
        errors.append(f"useful historical methods not yet migrated: {len(pending)}")
    if json.loads((ROOT / "v9_rebuild/sources.json").read_text()).get("status") != "complete_g2_migration":
        errors.append("execution registry remains explicitly partial")
    result = {
        "gate": "G2",
        "status": "pass" if not errors else "fail",
        "legacy_active_workflows_removed": len(expected) == len(workflows),
        "new_workflows": [path.name for path in workflows],
        "migrated_legacy_workflows": len(migrated),
        "registered_source_instances": len(sources),
        "pending_useful_methods": len(pending),
        "github_handoff_unverified": handoff_pending,
        "live_pending": live_pending,
        "pending_sample": pending[:12],
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
