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
        method = ("scripts/ozecar/extract_ozecar.py" if spec["module"] == "ozecar"
                  else "scripts/refresh_fixed_tariffs_france_secondary.py" if spec["module"] == "france_fixed_secondary"
                  else "scripts/refresh_fixed_tariffs_france_core.py" if spec["module"] == "france_fixed_core"
                  else "scripts/refresh_fixed_tariffs_bfc.py" if spec["module"] == "bfc_fixed_watch"
                  else "scripts/refresh_fixed_tariffs_spain_core.py" if spec["module"] == "spain_fixed_core"
                  else "scripts/refresh_fixed_tariffs_spain_secondary.py" if spec["module"] == "spain_fixed_secondary"
                  else "scripts/refresh_fixed_tariffs_france_watch.py" if spec["module"] == "france_fixed_watch"
                  else "scripts/refresh_fixed_tariffs_france_delmonicos.py" if spec["module"] == "delmonicos_watch"
                  else "scripts/reve-v2-web-extract.mjs" if spec["module"] == "reve_national"
                  else "scripts/reve_es_stream_collect.py" if spec["module"] == "reve_stream"
                  else "scripts/greenspot/extract_greenspot.py" if spec["module"] == "greenspot"
                  else "scripts/operator_manifest_runner.py" if spec["module"] == "operator_manifest"
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
                  else "scripts/finalize_swiss_autosense_amag.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_autosense"
                  else "scripts/finalize_swiss_chevp_evpass.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_chevp"
                  else "scripts/finalize_swiss_shell_evpass_official.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_shell_evpass"
                  else "scripts/finalize_swiss_saascharge_official.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_saascharge"
                  else "scripts/finalize_swiss_par_partino.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_partino"
                  else "scripts/finalize_swiss_iwb_official_basel.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_iwb"
                  else "scripts/finalize_swiss_tae.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_tae"
                  else "scripts/finalize_swiss_ewo_ecarup.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_ewo"
                  else "scripts/reconcile_swiss_ecarup_coordinate_safe.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_ecarup_coordinate"
                  else "scripts/reconcile_swiss_ecarup_owner.py" if spec["module"] == "cwd_script" and spec["method"] == "swiss_ecarup_owner"
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
                  else "scripts/driveco_evse_tariffs.py" if spec["module"] == "driveco_evse"
                  else "scripts/uk_midhope_build_verified_runtime.py" if spec["module"] == "uk_midhope"
                  else "scripts/chargezy_te63_official_direct.py" if spec["module"] == "chargezy_te63"
                  else "scripts/uk_connected_kerb_collect.py" if spec["module"] == "uk_connected_kerb_operator"
                  else "scripts/uk_connected_kerb_app_collect.py" if spec["module"] == "uk_connected_kerb_app"
                  else "scripts/uk_eco_movement_pcpr_audit.py" if spec["module"] == "uk_eco_movement"
                  else "scripts/electra_france_platform_snapshot.mjs" if spec["module"] == "electra_france"
                  else "scripts/energyvision_datex_semantic_stage.py" if spec["module"] == "energyvision"
                  else "scripts/finalize_swiss_ecarup_owner.py" if spec["module"] == "swiss_ecarup_finalizer"
                  else {"cci": "scripts/finalize_swiss_cci_cpo_level.py", "soc": "scripts/finalize_swiss_soc_cpo_level.py", "mmn": "scripts/finalize_swiss_mmn_move.py"}[spec["method"]] if spec["module"] == "swiss_move"
                  else "scripts/close_swiss_plenitude_known_residuals.py" if spec["module"] == "swiss_plenitude_closeout"
                  else {"fastvolt": "scripts/morocco/extract_fastvolt_public_map_chargers.py", "kilowatt": "scripts/morocco/kilowatt_public_station_inventory.py"}[spec["method"]] if spec["module"] == "morocco_inventory"
                  else "scripts/morocco/kilowatt_location_reconciliation.py" if spec["module"] == "morocco_reconcile"
                  else "scripts/morocco_kilowatt_build_v9_tariff_overlay.py" if spec["module"] == "morocco_tariff_overlay"
                  else "scripts/close_swiss_ebs_official_locations.py" if spec["module"] == "swiss_ebs_closeout"
                  else "scripts/finalize_swiss_cpi.py" if spec["module"] == "swiss_cpi"
                  else "scripts/collect_powerup_monta_public.py" if spec["module"] == "swiss_powerup"
                  else "scripts/close_powerup_residuals.py" if spec["module"] == "swiss_powerup_closeout"
                  else "scripts/collect_swisscharge_cloud.py" if spec["module"] == "swisscharge"
                  else spec["script"])
        source_code = ROOT / ("v9_rebuild/ozecar.py" if spec["module"] == "ozecar" else "v9_rebuild/france_fixed_secondary.py" if spec["module"] == "france_fixed_secondary" else "v9_rebuild/france_fixed_core.py" if spec["module"] == "france_fixed_core" else "v9_rebuild/bfc_fixed_watch.py" if spec["module"] == "bfc_fixed_watch" else "v9_rebuild/spain_fixed_core.py" if spec["module"] == "spain_fixed_core" else "v9_rebuild/spain_fixed_secondary.py" if spec["module"] == "spain_fixed_secondary" else "v9_rebuild/france_fixed_watch.py" if spec["module"] == "france_fixed_watch" else "v9_rebuild/delmonicos_watch.py" if spec["module"] == "delmonicos_watch" else "v9_rebuild/reve_national.py" if spec["module"] == "reve_national" else "v9_rebuild/reve_stream.py" if spec["module"] == "reve_stream" else "v9_rebuild/greenspot.py" if spec["module"] == "greenspot" else "v9_rebuild/swisscharge.py" if spec["module"] == "swisscharge" else "v9_rebuild/swiss_powerup_closeout.py" if spec["module"] == "swiss_powerup_closeout" else "v9_rebuild/swiss_powerup.py" if spec["module"] == "swiss_powerup" else "v9_rebuild/swiss_cpi.py" if spec["module"] == "swiss_cpi" else "v9_rebuild/swiss_ebs_closeout.py" if spec["module"] == "swiss_ebs_closeout" else "v9_rebuild/morocco_inventory.py" if spec["module"] in {"morocco_inventory", "morocco_reconcile", "morocco_tariff_overlay"} else spec["manifest"] if spec["module"] == "operator_manifest" else "v9_rebuild/belib.py" if spec["module"] == "belib_chain" else "v9_rebuild/ionity.py" if spec["module"] == "ionity_family" else "v9_rebuild/fastned.py" if spec["module"] == "fastned_family" else "v9_rebuild/bump_inventory.py" if spec["module"] == "bump_inventory_family" else "v9_rebuild/bump_tariffs.py" if spec["module"] == "bump_tariffs" else "v9_rebuild/bump_official.py" if spec["module"] == "bump_official" else "v9_rebuild/allego_stations.py" if spec["module"] == "allego_stations" else "v9_rebuild/allego_official.py" if spec["module"] == "allego_official" else "v9_rebuild/official_rules.py" if spec["module"] == "official_rules" else "v9_rebuild/fx.py" if spec["module"] == "fx" else "v9_rebuild/suc_tracker.py" if spec["module"] == "suc_tracker" else "v9_rebuild/tesla_mac.py" if spec["module"] == "tesla_mac" else "v9_rebuild/cwd_script.py" if spec["module"] == "cwd_script" else "v9_rebuild/france_irve.py" if spec["module"] == "france_irve" else "v9_rebuild/france_canonical.py" if spec["module"] == "france_canonical" else "v9_rebuild/uk_blink.py" if spec["module"] == "uk_blink" else "v9_rebuild/uk_pcpr.py" if spec["module"] == "uk_pcpr" else "v9_rebuild/uk_evyve.py" if spec["module"] == "uk_evyve" else "v9_rebuild/uk_gridserve.py" if spec["module"] == "uk_gridserve" else "v9_rebuild/uk_ubitricity.py" if spec["module"] == "uk_ubitricity" else "v9_rebuild/avia_picoty_extract.py" if spec["module"] == "avia_picoty_extract" else "v9_rebuild/electric55_chain.py" if spec["module"] == "electric55_chain" else "v9_rebuild/freshmile_inventory.py" if spec["module"] == "freshmile_inventory" else "v9_rebuild/waat_monta_sharded.py" if spec["module"] == "waat_monta_sharded" else "v9_rebuild/waat_monta_public.py" if spec["module"] == "waat_monta_public" else "v9_rebuild/driveco_evse.py" if spec["module"] == "driveco_evse" else "v9_rebuild/uk_midhope.py" if spec["module"] == "uk_midhope" else "v9_rebuild/chargezy_te63.py" if spec["module"] == "chargezy_te63" else "v9_rebuild/uk_connected_kerb_operator.py" if spec["module"] == "uk_connected_kerb_operator" else "v9_rebuild/uk_connected_kerb_app.py" if spec["module"] == "uk_connected_kerb_app" else "v9_rebuild/uk_eco_movement.py" if spec["module"] == "uk_eco_movement" else "v9_rebuild/electra_france.py" if spec["module"] == "electra_france" else "v9_rebuild/energyvision.py" if spec["module"] == "energyvision" else "v9_rebuild/swiss_ecarup_finalizer.py" if spec["module"] == "swiss_ecarup_finalizer" else "v9_rebuild/swiss_move.py" if spec["module"] == "swiss_move" else "v9_rebuild/swiss_plenitude_closeout.py" if spec["module"] == "swiss_plenitude_closeout" else method)
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
                               else "scripts/energyvision_datex_independent_cpo.py" if workflow.endswith("energyvision-be-durable-source.yml")
                               else "scripts/energyvision_datex_nap_audit.py" if workflow.endswith("energyvision-datex-nap-audit.yml")
                               else "scripts/close_swiss_plenitude_restricted_residuals.py" if workflow.endswith("switzerland-plenitude-restricted-closeout.yml")
                               else method)
            if workflow not in original or workflow in migrated:
                errors.append(f"invalid or duplicate legacy workflow mapping: {workflow}")
            elif workflow_method not in original[workflow]["scripts"]:
                errors.append(f"legacy workflow uses a different extraction method: {workflow}")
            else:
                migrated.add(workflow)
    required = {row["workflow"] for row in final["workflow_rows"] if row["disposition"] in REQUIRED_METHOD_DISPOSITIONS}
    superseded = json.loads((ROOT / "migration/v9/g2-superseded-methods.json").read_text())["superseded"]
    superseded_workflows = set()
    for row in superseded:
        workflow = row["workflow"]
        replacement = row["replacement_workflow"]
        source = next((item for item in sources if item["id"] == row["replacement_source"]), None)
        old = next((item for item in final["workflow_rows"] if item["workflow"] == workflow), None)
        new = next((item for item in final["workflow_rows"] if item["workflow"] == replacement), None)
        if (workflow in superseded_workflows or workflow not in required or workflow in migrated
                or not source or replacement not in source["legacy_workflows"] or replacement not in migrated
                or not old or not new or old["source_scripts"] != [row["script"]]
                or old["published_paths_in_git_add"] != new["published_paths_in_git_add"]
                or not (ROOT / row["script"]).is_file() or not row.get("reason")):
            errors.append(f"invalid explicit G2 supersession: {workflow}")
        else:
            superseded_workflows.add(workflow)
    retired = json.loads((ROOT / "migration/v9/g2-retired-methods.json").read_text())
    retired_workflows = set()
    approved_retirements = {".github/workflows/validate-v9-source-guards.yml",
                            ".github/workflows/audit-fixed-tariff-refresh.yml"}
    if (retired.get("schema_version") != 1
            or {row.get("workflow") for row in retired.get("retired", [])} != approved_retirements
            or len(retired.get("retired", [])) != len(approved_retirements)):
        errors.append("G2 retirement registry differs from the two reviewed obsolete audits")
    for row in retired.get("retired", []):
        workflow = row.get("workflow")
        script = row.get("script")
        legacy = next((item for item in final["workflow_rows"] if item["workflow"] == workflow), None)
        body = (ROOT / script).read_text(encoding="utf-8") if isinstance(script, str) and (ROOT / script).is_file() else ""
        forbidden_volume_checks = ("resolvedNationalEvseCount\"]==583", "nfr>=160", "nit>=470",
                                   "franceConnectorCount\"]>=1800", "inventoryCount\"]>=160000",
                                   "len(lstores)>=300", "productionStations\"]==43", "station_count\"]==18")
        volume_guard = (workflow == ".github/workflows/validate-v9-source-guards.yml"
                        and script == "scripts/validate_v9_source_guards.py"
                        and row.get("classification") == "obsolete_volume_gate"
                        and not legacy["published_paths_in_git_add"]
                        and all(token in body for token in forbidden_volume_checks)) if legacy else False
        workflow_audit = (workflow == ".github/workflows/audit-fixed-tariff-refresh.yml"
                          and script == "scripts/audit_fixed_tariff_refresh.py"
                          and row.get("classification") == "obsolete_workflow_reference_audit"
                          and legacy["published_paths_in_git_add"] == ["reports/fixed-tariff-refresh-audit.json"]
                          and "WORKFLOWS=ROOT/\".github\"/\"workflows\"" in body
                          and "managed=bool(refs)" in body
                          and not any("fixed-tariff-refresh-audit.json" in str(item)
                                      for item in sources)) if legacy else False
        if (not row.get("reason") or workflow not in required or workflow in migrated
                or not legacy or legacy["source_scripts"] != [script]
                or not (volume_guard or workflow_audit)
                or workflow in retired_workflows):
            errors.append(f"invalid explicit G2 retirement: {workflow}")
        else:
            retired_workflows.add(workflow)
    pending = sorted(required - migrated - superseded_workflows - retired_workflows)
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
        "superseded_legacy_workflows": sorted(superseded_workflows),
        "retired_obsolete_legacy_workflows": sorted(retired_workflows),
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
