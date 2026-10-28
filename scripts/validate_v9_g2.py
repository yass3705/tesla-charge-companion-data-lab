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
    for spec in sources:
        claim = spec.get("github_handoff", "")
        if not claim.startswith("verified_pilot_"):
            continue
        relative = Path(spec.get("evidence", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            errors.append(f"verified handoff evidence path invalid: {spec['id']}")
            continue
        try:
            evidence = json.loads((ROOT / relative).read_text())
        except (OSError, ValueError, TypeError):
            errors.append(f"verified handoff evidence unavailable: {spec['id']}")
            continue
        if (claim != f"verified_pilot_{evidence.get('runId')}"
                or spec.get("live") != claim
                or evidence.get("sourceId") != spec["id"]
                or evidence.get("runConclusion") != "success"
                or evidence.get("actionsEnabledAfter") is not False
                or not isinstance(evidence.get("artifactZipSha256"), str)
                or len(evidence["artifactZipSha256"]) != 64):
            errors.append(f"verified handoff evidence mismatch: {spec['id']}")
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
        method = ("scripts/collect_uk_validated_open_feeds.py" if spec["module"] == "uk_open_feeds" else "scripts/izivia_official.py" if spec["module"] == "izivia_official" else "scripts/mobisdec_official.py" if spec["module"] == "mobisdec_official" else "scripts/totalenergies_official.py" if spec["module"] == "totalenergies_official" else "scripts/shell_recharge_official.py" if spec["module"] == "shell_official" else "scripts/powerdot_official.py" if spec["module"] == "powerdot_official" else "scripts/evadea_official.py" if spec["module"] == "evadea_official" else "scripts/france/audit_electra_pricing_residuals.mjs" if spec["module"] == "electra_residual_audit" else "scripts/soregies_mobilites_official.py" if spec["module"] == "soregies_official" else "scripts/france_treated_reliability_audit.py" if spec["module"] == "france_treated_audit" else "scripts/izivia_fast_capture.py" if spec["module"] == "izivia_fast" else "scripts/belgium_finalize_gap_reconciliation.py" if spec["module"] == "belgium_gap_archive" else "scripts/atlante/extract_atlante.py" if spec["module"] == "atlante_fr_it" else "scripts/zewatt/extract_zewatt_france.mjs" if spec["module"] == "zewatt"
                  else "scripts/zephyre/extract_zephyre_france.mjs" if spec["module"] == "zephyre"
                  else "scripts/ozecar/extract_ozecar.py" if spec["module"] == "ozecar"
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
                  else "scripts/build_swiss_tcc_v9_bundle.py" if spec["module"] == "swiss_bundle"
                  else "scripts/build_switzerland_v9_dataset.py" if spec["module"] == "swiss_integration"
                  else "scripts/collect_avia_switzerland_guest.py" if spec["module"] == "swiss_avia_guest"
                  else "scripts/collect_swiss_atlas_cpo.py" if spec["module"] == "swiss_easy_closeouts"
                  else "scripts/morocco_evgo_pin_hydration_probe.py" if spec["module"] == "morocco_evgo"
                  else "scripts/loadmotion/extract_loadmotion_france.mjs" if spec["module"] == "loadmotion_france"
                  else spec["script"])
        if spec["module"] == "swiss_bundle":
            method = "scripts/build_swiss_tcc_v9_bundle.py"
        source_code = ROOT / ("v9_rebuild/uk_open_feeds.py" if spec["module"] == "uk_open_feeds" else "v9_rebuild/izivia_official.py" if spec["module"] == "izivia_official" else "v9_rebuild/mobisdec_official.py" if spec["module"] == "mobisdec_official" else "v9_rebuild/totalenergies_official.py" if spec["module"] == "totalenergies_official" else "v9_rebuild/shell_official.py" if spec["module"] == "shell_official" else "v9_rebuild/powerdot_official.py" if spec["module"] == "powerdot_official" else "v9_rebuild/evadea_official.py" if spec["module"] == "evadea_official" else "v9_rebuild/electra_residual_audit.py" if spec["module"] == "electra_residual_audit" else "v9_rebuild/soregies_official.py" if spec["module"] == "soregies_official" else "v9_rebuild/france_treated_audit.py" if spec["module"] == "france_treated_audit" else "v9_rebuild/izivia_fast.py" if spec["module"] == "izivia_fast" else "v9_rebuild/belgium_gap_archive.py" if spec["module"] == "belgium_gap_archive" else "v9_rebuild/atlante_fr_it.py" if spec["module"] == "atlante_fr_it" else "v9_rebuild/zewatt.py" if spec["module"] == "zewatt" else "v9_rebuild/zephyre.py" if spec["module"] == "zephyre" else "v9_rebuild/ozecar.py" if spec["module"] == "ozecar" else "v9_rebuild/france_fixed_secondary.py" if spec["module"] == "france_fixed_secondary" else "v9_rebuild/france_fixed_core.py" if spec["module"] == "france_fixed_core" else "v9_rebuild/bfc_fixed_watch.py" if spec["module"] == "bfc_fixed_watch" else "v9_rebuild/spain_fixed_core.py" if spec["module"] == "spain_fixed_core" else "v9_rebuild/spain_fixed_secondary.py" if spec["module"] == "spain_fixed_secondary" else "v9_rebuild/france_fixed_watch.py" if spec["module"] == "france_fixed_watch" else "v9_rebuild/delmonicos_watch.py" if spec["module"] == "delmonicos_watch" else "v9_rebuild/reve_national.py" if spec["module"] == "reve_national" else "v9_rebuild/reve_stream.py" if spec["module"] == "reve_stream" else "v9_rebuild/greenspot.py" if spec["module"] == "greenspot" else "v9_rebuild/swisscharge.py" if spec["module"] == "swisscharge" else "v9_rebuild/swiss_powerup_closeout.py" if spec["module"] == "swiss_powerup_closeout" else "v9_rebuild/swiss_powerup.py" if spec["module"] == "swiss_powerup" else "v9_rebuild/swiss_cpi.py" if spec["module"] == "swiss_cpi" else "v9_rebuild/swiss_ebs_closeout.py" if spec["module"] == "swiss_ebs_closeout" else "v9_rebuild/morocco_inventory.py" if spec["module"] in {"morocco_inventory", "morocco_reconcile", "morocco_tariff_overlay"} else spec["manifest"] if spec["module"] == "operator_manifest" else "v9_rebuild/belib.py" if spec["module"] == "belib_chain" else "v9_rebuild/ionity.py" if spec["module"] == "ionity_family" else "v9_rebuild/fastned.py" if spec["module"] == "fastned_family" else "v9_rebuild/bump_inventory.py" if spec["module"] == "bump_inventory_family" else "v9_rebuild/bump_tariffs.py" if spec["module"] == "bump_tariffs" else "v9_rebuild/bump_official.py" if spec["module"] == "bump_official" else "v9_rebuild/allego_stations.py" if spec["module"] == "allego_stations" else "v9_rebuild/allego_official.py" if spec["module"] == "allego_official" else "v9_rebuild/official_rules.py" if spec["module"] == "official_rules" else "v9_rebuild/fx.py" if spec["module"] == "fx" else "v9_rebuild/suc_tracker.py" if spec["module"] == "suc_tracker" else "v9_rebuild/tesla_mac.py" if spec["module"] == "tesla_mac" else "v9_rebuild/cwd_script.py" if spec["module"] == "cwd_script" else "v9_rebuild/france_irve.py" if spec["module"] == "france_irve" else "v9_rebuild/france_canonical.py" if spec["module"] == "france_canonical" else "v9_rebuild/uk_blink.py" if spec["module"] == "uk_blink" else "v9_rebuild/uk_pcpr.py" if spec["module"] == "uk_pcpr" else "v9_rebuild/uk_evyve.py" if spec["module"] == "uk_evyve" else "v9_rebuild/uk_gridserve.py" if spec["module"] == "uk_gridserve" else "v9_rebuild/uk_ubitricity.py" if spec["module"] == "uk_ubitricity" else "v9_rebuild/avia_picoty_extract.py" if spec["module"] == "avia_picoty_extract" else "v9_rebuild/electric55_chain.py" if spec["module"] == "electric55_chain" else "v9_rebuild/freshmile_inventory.py" if spec["module"] == "freshmile_inventory" else "v9_rebuild/waat_monta_sharded.py" if spec["module"] == "waat_monta_sharded" else "v9_rebuild/waat_monta_public.py" if spec["module"] == "waat_monta_public" else "v9_rebuild/driveco_evse.py" if spec["module"] == "driveco_evse" else "v9_rebuild/uk_midhope.py" if spec["module"] == "uk_midhope" else "v9_rebuild/chargezy_te63.py" if spec["module"] == "chargezy_te63" else "v9_rebuild/uk_connected_kerb_operator.py" if spec["module"] == "uk_connected_kerb_operator" else "v9_rebuild/uk_connected_kerb_app.py" if spec["module"] == "uk_connected_kerb_app" else "v9_rebuild/uk_eco_movement.py" if spec["module"] == "uk_eco_movement" else "v9_rebuild/electra_france.py" if spec["module"] == "electra_france" else "v9_rebuild/energyvision.py" if spec["module"] == "energyvision" else "v9_rebuild/swiss_ecarup_finalizer.py" if spec["module"] == "swiss_ecarup_finalizer" else "v9_rebuild/swiss_move.py" if spec["module"] == "swiss_move" else "v9_rebuild/swiss_plenitude_closeout.py" if spec["module"] == "swiss_plenitude_closeout" else method)
        if spec["module"] == "swiss_bundle":
            source_code = ROOT / "v9_rebuild/swiss_bundle.py"
        if spec["module"] == "swiss_integration":
            source_code = ROOT / "v9_rebuild/swiss_integration.py"
        if spec["module"] == "swiss_avia_guest":
            source_code = ROOT / "v9_rebuild/swiss_avia_guest.py"
        if spec["module"] == "swiss_easy_closeouts":
            source_code = ROOT / "v9_rebuild/swiss_easy_closeouts.py"
        if spec["module"] == "morocco_evgo":
            source_code = ROOT / "v9_rebuild/morocco_evgo.py"
        if spec["module"] == "loadmotion_france":
            source_code = ROOT / "v9_rebuild/loadmotion_france.py"
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
                            ".github/workflows/audit-fixed-tariff-refresh.yml",
                            ".github/workflows/electroverse-targeted-station-probe.yml",
                            ".github/workflows/electroverse-actionable-gaps.yml",
                            ".github/workflows/france-irve-tariff-coverage-archive.yml",
                            ".github/workflows/tesla-dataset-provenance-20261010.yml",
                            ".github/workflows/uk-zero-cost-tcc-autopilot.yml"}
    if (retired.get("schema_version") != 1
            or {row.get("workflow") for row in retired.get("retired", [])} != approved_retirements
            or len(retired.get("retired", [])) != len(approved_retirements)):
        errors.append("G2 retirement registry differs from the reviewed inactive methods")
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
        targeted_investigation = (workflow == ".github/workflows/electroverse-targeted-station-probe.yml"
                                  and script == "scripts/electroverse_targeted_station_probe.mjs"
                                  and row.get("classification") == "historical_targeted_tariff_investigation"
                                  and legacy["source_scripts"] == ["scripts/electroverse_cache_audit.mjs",
                                                                   script,
                                                                   "scripts/integrate_electroverse_targeted_probe.py"]
                                  and {"data/electroverse/irve_location_mapping.json",
                                       "data/electroverse/tariff_cache/manifest.json"}
                                      == set(legacy["literal_production_references"])
                                  and "electra-bois-d-arcy" in body and "lidl-dole" in body
                                  and "SINGLE_LOCATION_QUERY" in body
                                  and all((ROOT / path).is_file() for path in (
                                      "reports/electroverse/targeted-station-probe.json",
                                      "data/electroverse/irve_location_mapping.json",
                                      "data/electroverse/tariff_cache/manifest.json",
                                      "data/electroverse/tariff_cache/shard-089.json",
                                      "data/electroverse/tariff_cache/shard-093.json"))
                                  and {"FR:electroverse_daily", "FR:electroverse_full", "FR:electroverse_overlay"}
                                      <= {item["id"] for item in sources}) if legacy else False
        actionable_research = (workflow == ".github/workflows/electroverse-actionable-gaps.yml"
                               and row.get("classification") == "historical_match_investigation"
                               and legacy["source_scripts"] == ["scripts/analyze_electroverse_actionable_gaps.mjs",
                                                                "scripts/analyze_electroverse_fingerprint_candidates.mjs",
                                                                "scripts/build_electroverse_irve_fingerprint_index.py"]
                               and set(legacy["literal_production_references"]) == {"data/national/france_public_charging_canonical.json"}
                               and all((ROOT / path).is_file() for path in legacy["published_paths_in_git_add"])) if legacy else False
        france_g5_audit = (workflow == ".github/workflows/france-irve-tariff-coverage-archive.yml"
                           and row.get("classification") == "deferred_g5_join_audit"
                           and len(legacy["source_scripts"]) == 5
                           and "scripts/france/archive_irve_tariff_coverage.py" in legacy["source_scripts"]
                           and set(legacy["literal_production_references"]) == {
                               "data/electroverse/irve_location_mapping.json",
                               "data/national/france-irve-dynamic-status-v9.json.gz"}
                           and (ROOT / "reports/france/tariff-coverage").is_dir()
                           and all((ROOT / path).is_file() for path in legacy["source_scripts"])) if legacy else False
        tesla_audit = (workflow == ".github/workflows/tesla-dataset-provenance-20261010.yml"
                       and row.get("classification") == "historical_one_time_provenance_audit"
                       and len(legacy["source_scripts"]) == 4
                       and not legacy["literal_production_references"]
                       and (ROOT / "reports/tesla/history").is_dir()
                       and "len(data)<100" in body
                       and "GL:tesla_mac" in {item["id"] for item in sources}
                       and all((ROOT / path).is_file() for path in legacy["source_scripts"])) if legacy else False
        uk_autopilot = (workflow == ".github/workflows/uk-zero-cost-tcc-autopilot.yml"
                        and row.get("classification") == "superseded_legacy_orchestration"
                        and legacy["source_scripts"] == [script]
                        and not legacy["published_paths_in_git_add"]
                        and set(legacy["literal_production_references"]) == {"data/national/uk_validated_open_feeds.json.gz"}
                        and "UK:validated_open_feeds" in {item["id"] for item in sources}
                        and "scripts/collect_uk_validated_open_feeds.py" in body
                        and "scripts/reconcile_uk_canonical.py" in body) if legacy else False
        if (not row.get("reason") or workflow not in required or workflow in migrated
                or not legacy or (script not in legacy["source_scripts"] and not volume_guard and not workflow_audit)
                or not (volume_guard or workflow_audit or targeted_investigation or actionable_research or france_g5_audit or tesla_audit or uk_autopilot)
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
