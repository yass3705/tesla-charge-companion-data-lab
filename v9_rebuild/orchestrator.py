#!/usr/bin/env python3
"""Run approved collector modules into isolated, content-addressed artifacts.

No Git command, branch write, or Production mutation occurs in this process.
The legacy operator-manifest runner is the first migrated module family.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path(__file__).with_name("sources.json")
SAFE_ID = re.compile(r"^[A-Z]{2}:[a-z0-9_]+$")
SAFE_SECRET = re.compile(r"^[A-Z][A-Z0-9_]*$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"Unsafe registry path: {raw}")
    return path


def read_sources(root: Path = ROOT, registry: Path = REGISTRY) -> list[dict]:
    payload = json.loads(registry.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported source registry schema")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Source registry must contain a list")
    ids = set()
    for spec in sources:
        source_id = spec.get("id", "")
        if not SAFE_ID.fullmatch(source_id) or source_id in ids:
            raise ValueError(f"Invalid or duplicate source ID: {source_id}")
        ids.add(source_id)
        if not isinstance(spec.get("secret_names"), list) or any(not SAFE_SECRET.fullmatch(name) for name in spec["secret_names"]):
            raise ValueError(f"Invalid secret name list: {source_id}")
        if spec.get("module") == "operator_manifest":
            manifest_path = root / safe_relative(spec.get("manifest", ""))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("key") != spec.get("operator") or source_id != f"{manifest.get('country', 'FR')}:{manifest.get('key')}":
                raise ValueError(f"Source/manifest identity mismatch: {source_id}")
            output = safe_relative(manifest.get("outputFile", ""))
            if len(output.parts) != 1:
                raise ValueError(f"Manifest output must be a filename: {source_id}")
            spec["output_file"] = output.name
            spec["manifest_sha256"] = sha256(manifest_path)
            spec["expected_operator"] = manifest["operator"]
            spec["expected_dataset"] = manifest["dataset"]
            spec["expected_country"] = manifest.get("country", "FR")
        elif spec.get("module") == "belgium_nap" and source_id == "BE:nap":
            script = safe_relative(spec.get("script", ""))
            if script.as_posix() != "scripts/belgium_nap_full_country.py" or not (root / script).is_file():
                raise ValueError("Belgium NAP source script differs from the preserved method")
            if spec["secret_names"] != ["BELGIUM_NAP_TOKEN"]:
                raise ValueError("Belgium NAP authentication contract changed")
            spec["output_file"] = "data/belgium/nap-belgium-manifest.json"
            spec["manifest_sha256"] = sha256(root / script)
        elif spec.get("module") == "nl_dotnl" and source_id == "NL:dotnl":
            script = root / "v9_rebuild/nl_dotnl.py"
            if not script.is_file() or spec["secret_names"]:
                raise ValueError("DOT-NL module or authentication contract invalid")
            spec["output_file"] = "data/national/netherlands_dotnl/runtime/manifest.json"
            spec["manifest_sha256"] = sha256(script)
        elif spec.get("module") == "electroverse" and source_id in {"FR:electroverse_daily", "FR:electroverse_full"}:
            from v9_rebuild.electroverse import CACHE, MAPPING
            if spec["secret_names"] != ["ELECTROVERSE_API_KEY"] or spec.get("mode") != source_id.rsplit("_", 1)[-1]:
                raise ValueError("Electroverse source/mode/authentication mismatch")
            if spec["mode"] == "full" and spec.get("max_chunks") != 1:
                raise ValueError("Electroverse full must be bounded to one legacy chunk per run")
            for method in ("electroverse_daily_delta_selector.mjs", "electroverse_force_chunk_selection.mjs", "electroverse_hybrid_refresh.mjs"):
                if not (root / "scripts" / method).is_file():
                    raise ValueError(f"Missing preserved Electroverse method: {method}")
            if not (root / MAPPING).is_file() or not (root / CACHE / "manifest.json").is_file():
                raise ValueError("Missing Electroverse mapping or cached state")
            spec["output_file"] = (CACHE / "manifest.json").as_posix()
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electroverse.py")
        elif spec.get("module") == "electroverse_status" and source_id == "FR:electroverse_status":
            if spec["secret_names"] != ["ELECTROVERSE_API_KEY"]:
                raise ValueError("Electroverse status authentication contract changed")
            for name in ("electroverse_status_incremental.mjs", "electroverse_merge_status_partitions.mjs"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing preserved Electroverse status method: {name}")
            spec["output_file"] = "data/electroverse/live_statuses/manifest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electroverse_status.py")
        elif spec.get("module") == "electroverse_overlay" and source_id == "FR:electroverse_overlay":
            if spec["secret_names"] or not (root / "scripts/build_electroverse_france_evse_overlay.mjs").is_file() or not (root / "scripts/audit_electroverse_status_gate_postbuild.mjs").is_file():
                raise ValueError("Electroverse overlay historical method missing or unexpected secret")
            spec["output_file"] = "data/platforms/electroverse/france-evse/manifest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electroverse_overlay.py")
        elif spec.get("module") == "isolated_script" and source_id == "FR:atlante_direct":
            script = safe_relative(spec.get("script", ""))
            if script.as_posix() != "scripts/atlante_station_tariffs.py" or spec["secret_names"] != ["ATLANTE_API_SUBSCRIPTION_KEY"]:
                raise ValueError("Atlante direct historical method changed")
            spec["output_file"] = "data/national/atlante_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / script)
        elif spec.get("module") == "isolated_script" and source_id == "FR:labornebleue_direct":
            script = safe_relative(spec.get("script", ""))
            if script.as_posix() != "scripts/labornebleue_station_inventory.py" or spec["secret_names"]:
                raise ValueError("La Borne Bleue historical method changed")
            spec["output_file"] = "data/national/labornebleue_direct_stations_idf.json.gz"
            spec["manifest_sha256"] = sha256(root / script)
        elif spec.get("module") == "belib_chain" and source_id == "FR:belib":
            if spec["secret_names"]:
                raise ValueError("Belib historical collection has no secret")
            for name in ("belib_official.py", "belib_station_base.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical Belib script: {name}")
            spec["output_file"] = "data/national/belib_stations_paris.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/belib.py")
        elif spec.get("module") == "ionity_family" and source_id == "FR:ionity_direct_family":
            if spec["secret_names"]:
                raise ValueError("IONITY Direct historical method has no secret")
            for name in ("ionity_station_tariffs.py", "ionity_station_tariffs_uk.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical IONITY script: {name}")
            spec["output_file"] = "data/national/ionity_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/ionity.py")
        elif spec.get("module") == "fastned_family" and source_id == "FR:fastned_inventory_family":
            if spec["secret_names"]:
                raise ValueError("Fastned historical inventory has no secret")
            for name in ("fastned_station_inventory.py", "fastned_station_inventory_uk.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical Fastned script: {name}")
            spec["output_file"] = "data/national/fastned_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/fastned.py")
        elif spec.get("module") == "bump_inventory_family" and source_id == "FR:bump_inventory_family":
            if spec["secret_names"]:
                raise ValueError("Bump inventory methods have no secret")
            for name in ("bump_direct_inventory.py", "bump_direct_station_tariffs.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical Bump method: {name}")
            spec["output_file"] = "data/national/bump_direct_inventory_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/bump_inventory.py")
        elif spec.get("module") == "bump_tariffs" and source_id == "FR:bump_tariffs":
            if spec["secret_names"]:
                raise ValueError("Bump public GraphQL method has no secret")
            for name in ("bump_graphql_national_tariffs.py", "bump_tcc_ready_france.py", "bump_variable_tariff_parser.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical Bump tariff method: {name}")
            spec["output_file"] = "data/national/bump_direct_tariffs_tcc_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/bump_tariffs.py")
        elif spec.get("module") == "bump_official" and source_id == "FR:bump_official":
            if spec["secret_names"] or not (root / "scripts/bump_official.py").is_file():
                raise ValueError("Bump official method or authentication contract changed")
            spec["output_file"] = "data/operator_direct/bump_official_france.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/bump_official.py")
        elif spec.get("module") == "allego_stations" and source_id == "FR:allego_stations":
            if spec["secret_names"]:
                raise ValueError("Allego public DXP method has no named secret")
            for name in ("allego_dxp_national.py", "allego_normalize_v8.py", "allego_coordinate_fallbacks_v8.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical Allego method: {name}")
            spec["output_file"] = "data/national/allego_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/allego_stations.py")
        elif spec.get("module") == "allego_official" and source_id == "FR:allego_official":
            if spec["secret_names"] or any(not (root / "scripts" / name).is_file() for name in ("allego_official.py", "allego_static_wrapper.py")):
                raise ValueError("Allego official historical method or authentication contract changed")
            spec["output_file"] = "data/operator_direct/allego_official_france.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/allego_official.py")
        elif spec.get("module") == "official_rules" and source_id in {"FR:atlante_official", "FR:driveco_official", "FR:eborn_official", "FR:electric55_official", "FR:etotem_official", "FR:fastned_official", "FR:freshmile_official", "FR:iecharge_official", "FR:ionity_official", "FR:lidl_plus_official", "FR:metropolis_official", "FR:plenitude_official", "FR:pluginn_fastcharge_official", "FR:qovoltis_official", "FR:vianeo_official", "FR:zunder_official"}:
            source = spec.get("source")
            if source_id != f"FR:{source}_official" or spec["secret_names"] or not (root / f"scripts/{source}_official.py").is_file():
                raise ValueError("Official rule source or authentication contract changed")
            spec["output_file"] = ("data/operator_direct/metropolis_official_grand_paris.json" if source == "metropolis" else "data/operator_direct/lidl_plus_france.json" if source == "lidl_plus"
                                   else f"data/operator_direct/{source}_official_france.json")
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/official_rules.py")
        elif spec.get("module") == "fx" and source_id == "GL:fx":
            if spec["secret_names"] or not (root / "scripts/update_fx.py").is_file():
                raise ValueError("FX historical method or authentication contract changed")
            spec["output_file"] = "data/fx/exchange_rates.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/fx.py")
        elif spec.get("module") == "suc_tracker" and source_id == "GL:suc_tracker":
            if spec["secret_names"] or any(not (root / name).is_file() for name in ("scripts/suc_tracker/update.py", "scripts/suc_tracker/core.py", "config/countries.json")):
                raise ValueError("SuC Tracker historical method or configuration changed")
            spec["output_file"] = "data/suc-tracker/metadata.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/suc_tracker.py")
        elif spec.get("module") == "tesla_mac" and source_id == "GL:tesla_mac":
            if spec["secret_names"] or not (root / "scripts/import_tesla_mac_ingress.py").is_file():
                raise ValueError("Tesla/Mac historical ingress method or authentication contract changed")
            spec["output_file"] = "data/tesla/mac/last-good.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/tesla_mac.py")
        elif spec.get("module") == "cwd_script" and source_id in {"FR:etotem_inventory", "FR:qwello_saone_et_loire", "FR:reveo_official", "FR:avia_picoty_inventory", "FR:waat_inventory", "CH:fastned_official", "CH:lidl_official", "CH:ionity_national", "CH:plenitude_official", "CH:ail_emoti", "CH:ebs_ecarup", "CH:ewd_official", "CH:migrol_official", "CH:autosense_amag", "CH:chevp_evpass", "CH:shell_evpass", "CH:saascharge_official", "CH:partino_restricted", "CH:iwb_basel", "CH:tae_matterhorn", "CH:ewo_ecarup", "CH:ecarup_coordinate", "CH:ecarup_owner"}:
            from v9_rebuild.cwd_script import METHODS
            method = spec.get("method")
            if ((source_id, method) not in {("FR:etotem_inventory", "etotem_inventory"), ("FR:qwello_saone_et_loire", "qwello_saone_et_loire"), ("FR:reveo_official", "reveo_official"), ("FR:avia_picoty_inventory", "avia_picoty_inventory"), ("FR:waat_inventory", "waat_inventory"), ("CH:fastned_official", "swiss_fastned"), ("CH:lidl_official", "swiss_lidl"), ("CH:ionity_national", "swiss_ionity"), ("CH:plenitude_official", "swiss_plenitude"), ("CH:ail_emoti", "swiss_ail"), ("CH:ebs_ecarup", "swiss_ebs"), ("CH:ewd_official", "swiss_ewd"), ("CH:migrol_official", "swiss_migrol"), ("CH:autosense_amag", "swiss_autosense"), ("CH:chevp_evpass", "swiss_chevp"), ("CH:shell_evpass", "swiss_shell_evpass"), ("CH:saascharge_official", "swiss_saascharge"), ("CH:partino_restricted", "swiss_partino"), ("CH:iwb_basel", "swiss_iwb"), ("CH:tae_matterhorn", "swiss_tae"), ("CH:ewo_ecarup", "swiss_ewo"), ("CH:ecarup_coordinate", "swiss_ecarup_coordinate"), ("CH:ecarup_owner", "swiss_ecarup_owner")}
                    or spec["secret_names"] or not (root / METHODS[method][0]).is_file()):
                raise ValueError("Relative-output historical method or authentication contract changed")
            spec["output_file"] = METHODS[method][1]
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/cwd_script.py")
        elif spec.get("module") == "france_irve" and source_id == "FR:irve_national":
            if spec["secret_names"] or any(not (root / name).is_file() for name in ("scripts/france/build_france_irve_static_v9.py", "scripts/france/build_france_irve_dynamic_status_v9.py", "scripts/france/audit_france_irve_residuals.py")):
                raise ValueError("France IRVE historical chain or authentication contract changed")
            spec["output_file"] = "data/national/france-irve-static-v9/manifest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/france_irve.py")
        elif spec.get("module") == "france_canonical" and source_id == "FR:canonical":
            if spec["secret_names"] or not (root / "scripts/build_france_canonical_dataset.py").is_file():
                raise ValueError("France canonical historical method or authentication contract changed")
            spec["output_file"] = "data/national/france_public_charging_canonical.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/france_canonical.py")
        elif spec.get("module") == "uk_blink" and source_id == "GB:blink_pcpr":
            if spec["secret_names"] != ["BLINK_PCPR_TOKEN"] or any(not (root / name).is_file() for name in ("scripts/uk_blink_pcpr_collect.py", "scripts/uk_blink_pcpr_validate.py")):
                raise ValueError("UK Blink historical method or authentication contract changed")
            spec["output_file"] = "data/national/uk_blink_pcpr_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_blink.py")
        elif spec.get("module") == "uk_pcpr" and source_id in {"GB:allego_uk_pcpr", "GB:source_ev_pcpr"}:
            provider = spec.get("provider")
            names = {"allego_uk": "ALLEGO_UK_PCPR_TOKEN", "source_ev": "SOURCE_EV_PCPR_TOKEN"}
            if (source_id != f"GB:{provider}_pcpr" or spec["secret_names"] != [names.get(provider)]
                    or any(not (root / "scripts" / name).is_file() for name in ("uk_pcpr_cpo_collect.py", f"uk_{provider.replace('_uk', '')}_pcpr_validate.py"))):
                raise ValueError("UK PCPR historical method or authentication contract changed")
            spec["output_file"] = f"data/national/uk_{provider}_pcpr_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_pcpr.py")
        elif spec.get("module") == "uk_evyve" and source_id == "GB:evyve_pcpr":
            if spec["secret_names"] != ["EVYVE_PCPR_TOKEN"] or not (root / "scripts/uk_evyve_pcpr_collect.py").is_file():
                raise ValueError("UK Evyve historical method or authentication contract changed")
            spec["output_file"] = "data/national/uk_evyve_pcpr_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_evyve.py")
        elif spec.get("module") == "uk_gridserve" and source_id == "GB:gridserve_pcpr":
            if spec["secret_names"] != ["GRIDSERVE_API_KEY"] or any(not (root / name).is_file() for name in ("scripts/uk_gridserve_pcpr_collect.py", "scripts/uk_gridserve_v9_prepare.py")):
                raise ValueError("UK GRIDSERVE historical method or authentication contract changed")
            spec["output_file"] = "data/national/uk_gridserve_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_gridserve.py")
        elif spec.get("module") == "uk_ubitricity" and source_id == "GB:ubitricity_pcpr":
            if spec["secret_names"] != ["UBITRICITY_PCPR_TOKEN"] or any(not (root / name).is_file() for name in ("scripts/uk_ubitricity_pcpr_collect.py", "scripts/uk_ubitricity_pcpr_validate.py")):
                raise ValueError("UK Ubitricity historical method or authentication contract changed")
            spec["output_file"] = "data/national/uk_ubitricity_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_ubitricity.py")
        elif spec.get("module") == "avia_picoty_extract" and source_id == "FR:avia_picoty_extract":
            if spec["secret_names"] or any(not (root / name).is_file() for name in ("scripts/avia_picoty_irve_extract.py", "scripts/avia_picoty_compact_index.py")):
                raise ValueError("AVIA Picoty PAN methods or authentication contract changed")
            spec["output_file"] = "data/national/avia_volt_picoty_irve_extract.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/avia_picoty_extract.py")
        elif spec.get("module") == "electric55_chain" and source_id == "FR:electric55_chain":
            if spec["secret_names"] or any(not (root / name).is_file() for name in ("scripts/electric55_station_base.py", "scripts/electric55_direct_tariffs.py")):
                raise ValueError("E55C historical chain or authentication contract changed")
            spec["output_file"] = "data/national/electric55_stations_france.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electric55_chain.py")
        elif spec.get("module") == "freshmile_inventory" and source_id == "FR:freshmile_inventory":
            if spec["secret_names"] or any(not (root / name).is_file() for name in ("scripts/freshmile_direct_inventory.py", "scripts/freshmile_prune_regional_networks.py", "config/freshmile_regional_network_exclusions.json")):
                raise ValueError("Freshmile direct inventory historical chain changed")
            spec["output_file"] = "data/national/freshmile_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/freshmile_inventory.py")
        elif spec.get("module") == "waat_monta_sharded" and source_id == "FR:waat_monta_sharded":
            if spec["secret_names"] or not (root / "scripts/waat_monta_shard.mjs").is_file():
                raise ValueError("WAAT/Monta historical shard method changed")
            spec["output_file"] = "data/national/waat_monta_direct_tariffs_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/waat_monta_sharded.py")
        elif spec.get("module") == "waat_monta_public" and source_id == "FR:waat_monta_public":
            if spec["secret_names"] or not (root / "scripts/waat_monta_public_tariffs.mjs").is_file():
                raise ValueError("WAAT/Monta historical public method changed")
            spec["output_file"] = "data/national/waat_monta_public_tariffs_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/waat_monta_public.py")
        elif spec.get("module") == "driveco_evse" and source_id == "FR:driveco_evse":
            if spec["secret_names"] or not (root / "scripts/driveco_evse_tariffs.py").is_file():
                raise ValueError("DRIVECO historical exact EVSE method changed")
            spec["output_file"] = "data/operator_direct/driveco_evse_tariffs.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/driveco_evse.py")
        elif spec.get("module") == "uk_midhope" and source_id == "GB:midhope_verified":
            if spec["secret_names"] or not (root / "scripts/uk_midhope_build_verified_runtime.py").is_file():
                raise ValueError("Midhope historical exact socket method changed")
            spec["output_file"] = "data/national/uk_connected_kerb_midhope_verified_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_midhope.py")
        elif spec.get("module") == "chargezy_te63" and source_id == "FR:chargezy_te63":
            if spec["secret_names"] or not (root / "scripts/chargezy_te63_official_direct.py").is_file():
                raise ValueError("TE63 historical exact PAN method changed")
            spec["output_file"] = "data/operator_direct/chargezy_te63_official_france.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/chargezy_te63.py")
        elif spec.get("module") == "uk_connected_kerb_operator" and source_id == "GB:connected_kerb_operator":
            if (spec["secret_names"] != ["CONNECTED_KERB_TOKEN"]
                    or not all((root / "scripts" / name).is_file() for name in
                               ("uk_connected_kerb_collect.py", "uk_connected_kerb_snapshot_audit.py"))):
                raise ValueError("Connected Kerb operator API contract changed")
            spec["output_file"] = "data/national/uk_connected_kerb_locations.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_connected_kerb_operator.py")
        elif spec.get("module") == "uk_connected_kerb_app" and source_id == "GB:connected_kerb_app":
            if (spec["secret_names"]
                    or not all((root / "scripts" / name).is_file() for name in
                               ("uk_connected_kerb_app_collect.py", "uk_connected_kerb_reconcile.py"))):
                raise ValueError("Connected Kerb guest app method changed")
            spec["output_file"] = "data/national/uk_connected_kerb_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_connected_kerb_app.py")
        elif spec.get("module") == "uk_eco_movement" and source_id == "GB:eco_movement_pcpr":
            if (spec["secret_names"] != ["ECO_MOVEMENT_PCPR_TOKEN"]
                    or not all((root / "scripts" / name).is_file() for name in
                               ("uk_eco_movement_pcpr_collect.py", "uk_eco_movement_pcpr_audit.py"))):
                raise ValueError("Eco-Movement historical PCPR method changed")
            spec["output_file"] = "data/national/uk_eco_movement_pcpr_v9.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/uk_eco_movement.py")
        elif spec.get("module") == "electra_france" and source_id == "FR:electra_platform":
            from v9_rebuild.electra_france import ASSOCIATIONS, ASSOCIATION_DIR, NATIONAL, SCRIPT, VERIFIED
            if spec["secret_names"] or any(not (root / path).is_file() for path in
                                            (ASSOCIATIONS, NATIONAL, SCRIPT, VERIFIED)):
                raise ValueError("Electra France preserved inputs missing")
            if not (root / ASSOCIATION_DIR).is_dir():
                raise ValueError("Electra France curated association batches missing")
            spec["output_file"] = "data/platforms/electra/france/manifest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electra_france.py")
        elif spec.get("module") == "energyvision" and source_id == "BE:energyvision":
            from v9_rebuild.energyvision import METHODS, NAP_MANIFEST
            if (spec["secret_names"] != ["ENERGYVISION_API_KEY"]
                    or any(not (root / "scripts" / name).is_file() for name in METHODS)
                    or not (root / NAP_MANIFEST).is_file()):
                raise ValueError("EnergyVision archived methods, NAP or authentication missing")
            spec["output_file"] = "data/belgium/energyvision-official-2026-10-13.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/energyvision.py")
        elif spec.get("module") == "swiss_ecarup_finalizer" and source_id == "CH:ecarup_finalization":
            if spec["secret_names"] or not (root / "scripts/finalize_swiss_ecarup_owner.py").is_file():
                raise ValueError("Swiss eCarUp finalization historical method changed")
            spec["output_file"] = "docs/switzerland-ecarup-finalization-2026-09-28.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swiss_ecarup_finalizer.py")
        elif spec.get("module") == "swiss_move" and source_id in {"CH:cci_move", "CH:soc_move", "CH:mmn_move"}:
            from v9_rebuild.swiss_move import INPUTS, METHODS
            method = spec.get("method")
            if (source_id != f"CH:{method}_move" or method not in METHODS or spec["secret_names"]
                    or any(not (root / path).is_file() for path in INPUTS)
                    or not (root / "scripts" / METHODS[method][0]).is_file()):
                raise ValueError("Swiss MOVE historical method or inputs missing")
            spec["output_file"] = METHODS[method][1]
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swiss_move.py")
        elif spec.get("module") == "swiss_plenitude_closeout" and source_id == "CH:plenitude_closeout":
            from v9_rebuild.swiss_plenitude_closeout import CONTEXT, SCRIPTS
            if (spec["secret_names"] or not (root / CONTEXT).is_file()
                    or any(not (root / "scripts" / name).is_file() for name in SCRIPTS)):
                raise ValueError("Swiss Plenitude closeout archived inputs missing")
            spec["output_file"] = "data/switzerland/plenitude-official-direct-tariffs.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swiss_plenitude_closeout.py")
        elif spec.get("module") == "morocco_inventory" and source_id in {"MA:fastvolt_inventory", "MA:kilowatt_inventory"}:
            from v9_rebuild.morocco_inventory import METHODS
            method = spec.get("method")
            if (source_id != f"MA:{method}_inventory" or method not in METHODS
                    or spec["secret_names"] or not (root / METHODS[method][0]).is_file()):
                raise ValueError("Morocco public-map historical method changed")
            spec["output_file"] = METHODS[method][1]
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/morocco_inventory.py")
        elif spec.get("module") == "morocco_reconcile" and source_id == "MA:kilowatt_reconcile":
            from v9_rebuild.morocco_inventory import RECONCILIATION
            if spec["secret_names"] or not (root / RECONCILIATION[0]).is_file():
                raise ValueError("Kilowatt historical reconciliation missing")
            spec["output_file"] = RECONCILIATION[1]
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/morocco_inventory.py")
        elif spec.get("module") == "morocco_tariff_overlay" and source_id == "MA:kilowatt_tariff_overlay":
            from v9_rebuild.morocco_inventory import TARIFF_EVIDENCE, TARIFF_OVERLAY
            if (spec["secret_names"] or not (root / TARIFF_OVERLAY[0]).is_file()
                    or not (root / TARIFF_EVIDENCE).is_file()):
                raise ValueError("Kilowatt historical overlay missing")
            spec["output_file"] = TARIFF_OVERLAY[1]
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/morocco_inventory.py")
        elif spec.get("module") == "swiss_ebs_closeout" and source_id == "CH:ebs_closeout":
            from v9_rebuild.swiss_ebs_closeout import SCRIPT
            if spec["secret_names"] or not (root / SCRIPT).is_file():
                raise ValueError("Swiss EBS archived closeout missing")
            spec["output_file"] = "data/switzerland/ebs-ecarup-direct-tariffs.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swiss_ebs_closeout.py")
        elif spec.get("module") == "swiss_cpi" and source_id == "CH:cpi_finalization":
            from v9_rebuild.swiss_cpi import INPUTS, SCRIPT
            if (spec["secret_names"] or not (root / SCRIPT).is_file()
                    or any(not (root / path).is_file() for path in INPUTS)):
                raise ValueError("Swiss CPI historical method or inputs missing")
            spec["output_file"] = "data/switzerland/cpi-current-direct-tariffs.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swiss_cpi.py")
        elif spec.get("module") == "swiss_powerup" and source_id == "CH:powerup_monta":
            from v9_rebuild.swiss_powerup import SCRIPT
            if spec["secret_names"] or not (root / SCRIPT).is_file():
                raise ValueError("Swiss PowerUp/Monta historical collector missing")
            spec["output_file"] = "data/switzerland/powerup-monta-direct-tariffs.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swiss_powerup.py")
        elif spec.get("module") == "swiss_powerup_closeout" and source_id == "CH:powerup_closeout":
            from v9_rebuild.swiss_powerup_closeout import SCRIPT
            if spec["secret_names"] or not (root / SCRIPT).is_file():
                raise ValueError("Swiss PowerUp residual script missing")
            spec["output_file"] = "data/switzerland/powerup-monta-direct-tariffs.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swiss_powerup_closeout.py")
        elif spec.get("module") == "swisscharge" and source_id == "CH:swisscharge_full":
            from v9_rebuild.swisscharge import SCRIPT
            if spec["secret_names"] or not (root / SCRIPT).is_file():
                raise ValueError("Swisscharge preserved sharded collector missing")
            spec["output_file"] = "data/swisscharge/swisscharge-tariffs.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/swisscharge.py")
        elif spec.get("module") == "greenspot" and source_id == "FR:greenspot":
            from v9_rebuild.greenspot import SCRIPT
            if spec["secret_names"] or not (root / SCRIPT).is_file():
                raise ValueError("Greenspot historical collector missing")
            spec["output_file"] = "data/greenspot/france/greenspot-france-current.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/greenspot.py")
        elif spec.get("module") == "reve_stream" and source_id == "ES:reve_stream":
            from v9_rebuild.reve_stream import SCRIPT
            if spec["secret_names"] != ["REVE_API_KEY"] or not (root / SCRIPT).is_file():
                raise ValueError("REVE historical stream collector or secret changed")
            spec["output_file"] = "data/spain_reve/full_20261018/tariff_status_stream_state.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/reve_stream.py")
        elif spec.get("module") == "reve_national" and source_id == "ES:reve_national":
            from v9_rebuild.reve_national import BASELINE, SCRIPTS, VALIDATOR
            if (spec["secret_names"] or any(not (root / path).is_file() for path in (*SCRIPTS, VALIDATOR))
                    or not (root / BASELINE / "spain-static/manifest.json").is_file()):
                raise ValueError("REVE national methods or last-good baseline missing")
            spec["output_file"] = "data/reve_v2/validated_runtime/spain-static/manifest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/reve_national.py")
        elif spec.get("module") == "delmonicos_watch" and source_id == "FR:delmonicos_watch":
            from v9_rebuild.delmonicos_watch import DATA, SCRIPT
            if spec["secret_names"] or not (root / SCRIPT).is_file() or not (root / DATA).is_file():
                raise ValueError("Delmonicos historical method or baseline missing")
            spec["output_file"] = str(DATA)
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/delmonicos_watch.py")
        elif spec.get("module") == "france_fixed_watch" and source_id == "FR:fixed_tariff_watch":
            from v9_rebuild.france_fixed_watch import DATA, SCRIPT
            if spec["secret_names"] or any(not (root / path).is_file() for path in (*DATA, SCRIPT)):
                raise ValueError("France fixed watch historical files missing")
            spec["output_file"] = "reports/fixed-tariff-refresh-france-watch-latest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/france_fixed_watch.py")
        elif spec.get("module") == "spain_fixed_secondary" and source_id == "ES:fixed_tariff_secondary":
            from v9_rebuild.spain_fixed_secondary import DATA, SCRIPT
            if spec["secret_names"] or any(not (root / path).is_file() for path in (*DATA, SCRIPT)):
                raise ValueError("Spain secondary historical method missing")
            spec["output_file"] = "reports/fixed-tariff-refresh-spain-secondary-latest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/spain_fixed_secondary.py")
        elif spec.get("module") == "spain_fixed_core" and source_id == "ES:fixed_tariff_core":
            from v9_rebuild.spain_fixed_core import DATA, SCRIPT
            if spec["secret_names"] or any(not (root / path).is_file() for path in (*DATA, SCRIPT)):
                raise ValueError("Spain core historical files missing")
            spec["output_file"] = "reports/fixed-tariff-refresh-spain-latest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/spain_fixed_core.py")
        elif spec.get("module") == "bfc_fixed_watch" and source_id == "FR:bfc_fixed_watch":
            from v9_rebuild.bfc_fixed_watch import DATA, SCRIPT
            if spec["secret_names"] or any(not (root / path).is_file() for path in (*DATA, SCRIPT)):
                raise ValueError("BFC historical files missing")
            spec["output_file"] = "reports/fixed-tariff-refresh-bfc-latest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/bfc_fixed_watch.py")
        elif spec.get("module") == "france_fixed_core" and source_id == "FR:fixed_tariff_core":
            from v9_rebuild.france_fixed_core import DATA, SCRIPT
            if spec["secret_names"] or any(not (root / path).is_file() for path in (*DATA, SCRIPT)):
                raise ValueError("France core historical files missing")
            spec["output_file"] = "reports/fixed-tariff-refresh-france-core-latest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/france_fixed_core.py")
        elif spec.get("module") == "france_fixed_secondary" and source_id == "FR:fixed_tariff_secondary":
            from v9_rebuild.france_fixed_secondary import DATA, SCRIPT
            if spec["secret_names"] or any(not (root / path).is_file() for path in (*DATA, SCRIPT)):
                raise ValueError("France secondary historical files missing")
            spec["output_file"] = "reports/fixed-tariff-refresh-france-secondary-latest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/france_fixed_secondary.py")
        else:
            raise ValueError(f"Unmigrated module cannot execute: {source_id}")
    return sources


def validate_belgium_output(staged: Path, manifest: dict) -> bool:
    pages = manifest.get("pages")
    if manifest.get("country") != "BE" or not isinstance(pages, list) or not pages or manifest.get("pageCount") != len(pages):
        return False
    offsets = [page.get("offset") for page in pages if isinstance(page, dict)]
    if (len(offsets) != len(pages) or any(not isinstance(offset, int) or offset < 0 for offset in offsets)
            or len(set(offsets)) != len(offsets) or pages[-1].get("nextOffset") is not None):
        return False
    for index, page in enumerate(pages):
        if index + 1 < len(pages) and page.get("nextOffset") != pages[index + 1].get("offset"):
            return False
        try:
            path = staged / safe_relative(page["canonicalPath"])
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                if not isinstance(json.load(handle), dict):
                    return False
        except (KeyError, OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            return False
    report_path = staged / "reports/belgium-national-full-extraction-2026-09-28.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    integrity = report.get("integrity") if isinstance(report, dict) else None
    pagination = report.get("pagination") if isinstance(report, dict) else None
    return (isinstance(integrity, dict) and integrity.get("paginationEndedNormally") is True
            and isinstance(pagination, dict) and pagination.get("pageCount") == len(pages))


def artifact_digest(staged: Path) -> tuple[str, list[dict]]:
    files = []
    digest = hashlib.sha256()
    for path in sorted(p for p in staged.rglob("*") if p.is_file()):
        relative = path.relative_to(staged).as_posix()
        file_sha = sha256(path)
        digest.update(relative.encode("utf-8") + b"\0" + file_sha.encode("ascii") + b"\n")
        files.append({"path": relative, "sha256": file_sha, "bytes": path.stat().st_size})
    return digest.hexdigest(), files


def previous_electroverse_state(out_root: Path, source_id: str, module: str = "electroverse") -> Path | None:
    """Use a previously validated immutable artifact as the next collection seed."""
    from v9_rebuild.electroverse import validate_state
    from v9_rebuild.electroverse_status import validate_partial
    for base in (out_root / "input_state", out_root):
        manifest_path = base / "manifest.json"
        if not manifest_path.is_file():
            if base.name == "input_state" and base.exists():
                raise ValueError("Provided Electroverse state has no collection manifest")
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            if base.name == "input_state":
                raise ValueError("Provided Electroverse state manifest is unreadable")
            continue
        rows = [row for row in payload.get("sources", []) if row.get("status") == "ok" and row.get("module") == module]
        if base.name == "input_state" and not rows:
            raise ValueError("Provided artifact contains no validated source for this module")
        rows.sort(key=lambda row: row.get("source") != source_id)
        for row in rows:
            try:
                artifact = base / safe_relative(row["artifact"])
                if not artifact.resolve().is_relative_to(base.resolve()) or sha256(artifact) != row["sha256"]:
                    continue
                state = artifact.parents[3]
                if module == "electroverse_status":
                    validate_partial(state)
                else:
                    validate_state(state)
                digest, files = artifact_digest(state)
                if digest != row.get("artifact_set_sha256") or files != row.get("files"):
                    continue
                return state
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if rows:
            raise ValueError("Previous Electroverse artifact failed immutable integrity checks")
    return None


def validated_dependency(bundle: Path, source_id: str, module: str) -> Path:
    """Resolve one exact source from a downloaded immutable collection bundle."""
    from v9_rebuild.electroverse import validate_state
    from v9_rebuild.electroverse_status import validate_complete
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise ValueError("Dependency collection manifest is incomplete")
    rows = [row for row in manifest.get("sources", []) if row.get("source") == source_id
            and row.get("module") == module and row.get("status") == "ok"]
    if len(rows) != 1:
        raise ValueError(f"Missing validated dependency: {source_id}")
    row = rows[0]
    relative = safe_relative(row["artifact"])
    if (len(relative.parts) < 5 or relative.parts[:2] != ("objects", source_id.replace(":", "_"))):
        raise ValueError(f"Dependency object path invalid: {source_id}")
    artifact = bundle / relative
    if not artifact.resolve().is_relative_to(bundle.resolve()) or sha256(artifact) != row.get("sha256"):
        raise ValueError(f"Dependency manifest SHA mismatch: {source_id}")
    state = bundle / Path(*relative.parts[:3])
    if module == "electroverse_status":
        validate_complete(state, require_fresh_parts=False)
    elif module == "belib_chain":
        from v9_rebuild.belib import validate_output
        validate_output(state)
    elif module == "fx":
        from v9_rebuild.fx import validate_output
        validate_output(state)
    elif module == "suc_tracker":
        from v9_rebuild.suc_tracker import validate_output
        validate_output(state)
    elif module == "tesla_mac":
        from v9_rebuild.tesla_mac import validate_output
        validate_output(state)
    elif module == "electric55_chain":
        from v9_rebuild.electric55_chain import validate_output
        validate_output(state)
    elif module == "cwd_script" and source_id == "FR:waat_inventory":
        from v9_rebuild.cwd_script import validate_output
        validate_output(state, "waat_inventory")
    elif module == "cwd_script" and source_id == "CH:ecarup_owner":
        from v9_rebuild.cwd_script import validate_output
        validate_output(state, "swiss_ecarup_owner")
    elif module == "cwd_script" and source_id == "CH:ecarup_coordinate":
        from v9_rebuild.cwd_script import validate_output
        validate_output(state, "swiss_ecarup_coordinate")
    elif module == "cwd_script" and source_id == "CH:plenitude_official":
        from v9_rebuild.cwd_script import validate_output
        validate_output(state, "swiss_plenitude")
    elif module == "cwd_script" and source_id == "CH:ebs_ecarup":
        from v9_rebuild.cwd_script import validate_output
        validate_output(state, "swiss_ebs")
    elif module == "uk_connected_kerb_operator" and source_id == "GB:connected_kerb_operator":
        from v9_rebuild.uk_connected_kerb_operator import validate_output
        validate_output(state)
    elif module == "morocco_inventory" and source_id == "MA:kilowatt_inventory":
        from v9_rebuild.morocco_inventory import validate_output
        validate_output(state, "kilowatt")
    elif module == "swiss_powerup" and source_id == "CH:powerup_monta":
        from v9_rebuild.swiss_powerup import validate_output
        validate_output(state)
    elif module == "electroverse":
        validate_state(state)
    else:
        raise ValueError(f"Unsupported dependency module: {module}")
    digest, files = artifact_digest(state)
    if digest != row.get("artifact_set_sha256") or files != row.get("files"):
        raise ValueError(f"Dependency file integrity mismatch: {source_id}")
    return state


def validate_isolated_script_output(spec: dict, output: Path) -> bool:
    with gzip.open(output, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if spec["id"] == "FR:atlante_direct":
        scope = data.get("scope") or {}
        locations = data.get("locations")
        if (data.get("dataset") != "atlante-direct-operated-stations-france" or data.get("operator") != "Atlante"
                or data.get("country") != "FR" or scope.get("requiredCpo") != "FRATL"
                or scope.get("onlyOperatedLocations") is not True or scope.get("partnerLocationsIncluded") is not False
                or not isinstance(locations, list) or data.get("counts", {}).get("franceLocationCount") != len(locations)):
            return False
        ids = set()
        for row in locations:
            key = row.get("id")
            if (not key or key in ids or row.get("countryCode") != "FR" or row.get("partyId") != "ATL"
                    or row.get("operatorName") != "Atlante" or not isinstance(row.get("connectors"), list)):
                return False
            ids.add(key)
        return True
    if spec["id"] == "FR:labornebleue_direct":
        scope = data.get("scope") or {}
        stations = data.get("stations")
        counts = data.get("counts") or {}
        if (data.get("dataset") != "labornebleue-direct-tcc-v8-idf"
                or scope.get("countryCode") != "FR" or scope.get("onlyDirectCpo") is not True
                or scope.get("strictExplicitNetworkLabel") is not True
                or scope.get("partnerLocationsIncluded") is not False
                or scope.get("partnerTariffsIncluded") is not False
                or not isinstance(stations, list) or counts.get("publishedStations") != len(stations)):
            return False
        ids = set()
        for station in stations:
            sid = station.get("stationId")
            if (not sid or sid in ids or station.get("countryCode") != "FR"
                    or not isinstance(station.get("configurations"), list)):
                return False
            ids.add(sid)
            config_ids = set()
            for config in station["configurations"]:
                config_id = config.get("id")
                if (not config_id or config_id in config_ids
                        or config.get("offerType") != "operator_direct"
                        or config.get("labornebleueOwnNetworkOnly") is not True):
                    return False
                config_ids.add(config_id)
        return True
    return False


def run_source(spec: dict, out_root: Path, *, root: Path = ROOT, attempts: int = 2, timeout_s: int = 2400, runner=subprocess.run) -> dict:
    source_id = spec["id"]
    missing = [name for name in spec["secret_names"] if not os.environ.get(name)]
    if missing:
        return {"source": source_id, "status": "failed", "reason": "missing_required_secret", "missing_secret_names": missing}
    source_dir = out_root / "objects" / source_id.replace(":", "_")
    source_dir.mkdir(parents=True, exist_ok=True)
    electroverse_module = spec["module"] == "electroverse"
    status_module = spec["module"] == "electroverse_status"
    overlay_module = spec["module"] == "electroverse_overlay"
    belib_module = spec["module"] == "belib_chain"
    ionity_module = spec["module"] == "ionity_family"
    fastned_module = spec["module"] == "fastned_family"
    bump_inventory_module = spec["module"] == "bump_inventory_family"
    bump_tariffs_module = spec["module"] == "bump_tariffs"
    bump_official_module = spec["module"] == "bump_official"
    allego_stations_module = spec["module"] == "allego_stations"
    allego_official_module = spec["module"] == "allego_official"
    official_rules_module = spec["module"] == "official_rules"
    fx_module = spec["module"] == "fx"
    suc_module = spec["module"] == "suc_tracker"
    tesla_mac_module = spec["module"] == "tesla_mac"
    cwd_script_module = spec["module"] == "cwd_script"
    france_irve_module = spec["module"] == "france_irve"
    france_canonical_module = spec["module"] == "france_canonical"
    uk_blink_module = spec["module"] == "uk_blink"
    uk_pcpr_module = spec["module"] == "uk_pcpr"
    uk_evyve_module = spec["module"] == "uk_evyve"
    uk_gridserve_module = spec["module"] == "uk_gridserve"
    uk_ubitricity_module = spec["module"] == "uk_ubitricity"
    avia_picoty_extract_module = spec["module"] == "avia_picoty_extract"
    electric55_chain_module = spec["module"] == "electric55_chain"
    freshmile_inventory_module = spec["module"] == "freshmile_inventory"
    waat_monta_module = spec["module"] == "waat_monta_sharded"
    waat_monta_public_module = spec["module"] == "waat_monta_public"
    driveco_evse_module = spec["module"] == "driveco_evse"
    uk_midhope_module = spec["module"] == "uk_midhope"
    chargezy_te63_module = spec["module"] == "chargezy_te63"
    uk_connected_kerb_operator_module = spec["module"] == "uk_connected_kerb_operator"
    uk_connected_kerb_app_module = spec["module"] == "uk_connected_kerb_app"
    uk_eco_movement_module = spec["module"] == "uk_eco_movement"
    electra_france_module = spec["module"] == "electra_france"
    energyvision_module = spec["module"] == "energyvision"
    swiss_ecarup_finalizer_module = spec["module"] == "swiss_ecarup_finalizer"
    swiss_move_module = spec["module"] == "swiss_move"
    swiss_plenitude_closeout_module = spec["module"] == "swiss_plenitude_closeout"
    morocco_inventory_module = spec["module"] == "morocco_inventory"
    morocco_reconcile_module = spec["module"] == "morocco_reconcile"
    morocco_tariff_module = spec["module"] == "morocco_tariff_overlay"
    swiss_ebs_closeout_module = spec["module"] == "swiss_ebs_closeout"
    swiss_cpi_module = spec["module"] == "swiss_cpi"
    swiss_powerup_module = spec["module"] == "swiss_powerup"
    swiss_powerup_closeout_module = spec["module"] == "swiss_powerup_closeout"
    swisscharge_module = spec["module"] == "swisscharge"
    greenspot_module = spec["module"] == "greenspot"
    reve_stream_module = spec["module"] == "reve_stream"
    reve_national_module = spec["module"] == "reve_national"
    delmonicos_module = spec["module"] == "delmonicos_watch"
    france_fixed_watch_module = spec["module"] == "france_fixed_watch"
    spain_fixed_secondary_module = spec["module"] == "spain_fixed_secondary"
    spain_fixed_core_module = spec["module"] == "spain_fixed_core"
    bfc_fixed_watch_module = spec["module"] == "bfc_fixed_watch"
    france_fixed_core_module = spec["module"] == "france_fixed_core"
    france_fixed_secondary_module = spec["module"] == "france_fixed_secondary"
    waat_monta_dependency = waat_monta_module or waat_monta_public_module
    checkpoint_module = electroverse_module or status_module or waat_monta_module
    checkpoint = out_root / "checkpoints" / source_id.replace(":", "_")
    previous_state = previous_electroverse_state(out_root, source_id, spec["module"]) if (electroverse_module or status_module) else None
    belib_prior = None
    if (belib_module or fx_module or suc_module or tesla_mac_module or electric55_chain_module) and (out_root / "input_state").is_dir():
        try:
            belib_prior = validated_dependency(out_root / "input_state", source_id, spec["module"])
        except (OSError, ValueError, KeyError, TypeError):
            return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
    operator_module = spec["module"] == "operator_manifest"
    nl_module = spec["module"] == "nl_dotnl"
    isolated_script = spec["module"] == "isolated_script"
    reason = "collector_failed"
    for attempt in range(1, attempts + 1):
        if checkpoint_module and checkpoint.is_dir():
            from v9_rebuild.electroverse import validate_state
            from v9_rebuild.electroverse_status import validate_partial
            from v9_rebuild.waat_monta_sharded import validate_checkpoint
            try:
                validate_checkpoint(checkpoint) if waat_monta_module else validate_partial(checkpoint) if status_module else validate_state(checkpoint, require_complete=False)
            except (OSError, ValueError, KeyError, TypeError):
                return {"source": source_id, "status": "failed", "reason": "collector_checkpoint_invalid", "attempts": attempt - 1}
        staged = checkpoint if checkpoint_module and checkpoint.is_dir() else Path(tempfile.mkdtemp(prefix="attempt-", dir=source_dir))
        try:
            if overlay_module:
                dependencies = out_root / "input_dependencies"
                status_bundle = dependencies / "FR_electroverse_status"
                tariff_bundles = [(source, dependencies / source.replace(":", "_")) for source in ("FR:electroverse_daily", "FR:electroverse_full")]
                present_tariffs = [(source, path) for source, path in tariff_bundles if path.is_dir()]
                if not status_bundle.is_dir() or len(present_tariffs) != 1:
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    tariff_id, tariff_bundle = present_tariffs[0]
                    tariff_input = validated_dependency(tariff_bundle, tariff_id, "electroverse")
                    status_input = validated_dependency(status_bundle, "FR:electroverse_status", "electroverse_status")
                except (OSError, ValueError, KeyError, TypeError, RuntimeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if waat_monta_dependency:
                dependency = out_root / "input_dependencies/FR_waat_inventory"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    inventory_state = validated_dependency(dependency, "FR:waat_inventory", "cwd_script")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if uk_connected_kerb_app_module:
                dependency = out_root / "input_dependencies/GB_connected_kerb_operator"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    operator_state = validated_dependency(dependency, "GB:connected_kerb_operator", "uk_connected_kerb_operator")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if source_id == "CH:ecarup_coordinate":
                dependency = out_root / "input_dependencies/CH_ecarup_owner"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    owner_state = validated_dependency(dependency, "CH:ecarup_owner", "cwd_script")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if swiss_ecarup_finalizer_module:
                dependency = out_root / "input_dependencies/CH_ecarup_coordinate"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    coordinate_state = validated_dependency(dependency, "CH:ecarup_coordinate", "cwd_script")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if swiss_plenitude_closeout_module:
                dependency = out_root / "input_dependencies/CH_plenitude_official"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    plenitude_state = validated_dependency(dependency, "CH:plenitude_official", "cwd_script")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if morocco_reconcile_module or morocco_tariff_module:
                dependency = out_root / "input_dependencies/MA_kilowatt_inventory"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    kilowatt_state = validated_dependency(dependency, "MA:kilowatt_inventory", "morocco_inventory")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if swiss_ebs_closeout_module:
                dependency = out_root / "input_dependencies/CH_ebs_ecarup"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    ebs_state = validated_dependency(dependency, "CH:ebs_ecarup", "cwd_script")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            if swiss_powerup_closeout_module:
                dependency = out_root / "input_dependencies/CH_powerup_monta"
                if not dependency.is_dir():
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    powerup_state = validated_dependency(dependency, "CH:powerup_monta", "swiss_powerup")
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            command = ([sys.executable, str(root / safe_relative(spec["script"])), "--out", str(staged / spec["output_file"])]
                       if isolated_script else [sys.executable, str(root / "scripts/operator_manifest_runner.py"), "--operator", spec["operator"], "--out", str(staged)]
                       if operator_module else [sys.executable, str(root / "v9_rebuild/nl_dotnl.py"), "--out", str(staged)]
                       if nl_module else [sys.executable, str(root / "v9_rebuild/electroverse.py"), "--out", str(staged), "--mode", spec["mode"]]
                       if electroverse_module else [sys.executable, str(root / "v9_rebuild/electroverse_status.py"), "--out", str(staged)]
                       if status_module else [sys.executable, str(root / "v9_rebuild/electroverse_overlay.py"), "--out", str(staged), "--source", str(tariff_input), "--status-source", str(status_input)]
                       if overlay_module else [sys.executable, str(root / "v9_rebuild/belib.py"), "--out", str(staged)]
                       if belib_module else [sys.executable, str(root / "v9_rebuild/ionity.py"), "--out", str(staged)]
                       if ionity_module else [sys.executable, str(root / "v9_rebuild/fastned.py"), "--out", str(staged)]
                       if fastned_module else [sys.executable, str(root / "v9_rebuild/bump_inventory.py"), "--out", str(staged)]
                       if bump_inventory_module else [sys.executable, str(root / "v9_rebuild/bump_tariffs.py"), "--out", str(staged)]
                       if bump_tariffs_module else [sys.executable, str(root / "v9_rebuild/bump_official.py"), "--out", str(staged)]
                       if bump_official_module else [sys.executable, str(root / "v9_rebuild/allego_stations.py"), "--out", str(staged)]
                       if allego_stations_module else [sys.executable, str(root / "v9_rebuild/allego_official.py"), "--out", str(staged)]
                       if allego_official_module else [sys.executable, str(root / "v9_rebuild/official_rules.py"), "--source", spec["source"], "--out", str(staged)]
                       if official_rules_module else [sys.executable, str(root / "v9_rebuild/fx.py"), "--out", str(staged)]
                       if fx_module else [sys.executable, str(root / "v9_rebuild/suc_tracker.py"), "--out", str(staged)]
                       if suc_module else [sys.executable, str(root / "v9_rebuild/tesla_mac.py"), "--out", str(staged)]
                       if tesla_mac_module else [sys.executable, str(root / "v9_rebuild/cwd_script.py"), "--method", spec["method"], "--out", str(staged)]
                       if cwd_script_module else [sys.executable, str(root / "v9_rebuild/france_irve.py"), "--out", str(staged)]
                       if france_irve_module else [sys.executable, str(root / "v9_rebuild/france_canonical.py"), "--out", str(staged)]
                       if france_canonical_module else [sys.executable, str(root / "v9_rebuild/uk_blink.py"), "--out", str(staged)]
                       if uk_blink_module else [sys.executable, str(root / "v9_rebuild/uk_pcpr.py"), "--provider", spec["provider"], "--out", str(staged)]
                       if uk_pcpr_module else [sys.executable, str(root / "v9_rebuild/uk_evyve.py"), "--out", str(staged)]
                       if uk_evyve_module else [sys.executable, str(root / "v9_rebuild/uk_gridserve.py"), "--out", str(staged)]
                       if uk_gridserve_module else [sys.executable, str(root / "v9_rebuild/uk_ubitricity.py"), "--out", str(staged)]
                       if uk_ubitricity_module else [sys.executable, str(root / "v9_rebuild/avia_picoty_extract.py"), "--out", str(staged)]
                       if avia_picoty_extract_module else [sys.executable, str(root / "v9_rebuild/electric55_chain.py"), "--out", str(staged)]
                       if electric55_chain_module else [sys.executable, str(root / "v9_rebuild/freshmile_inventory.py"), "--out", str(staged)]
                       if freshmile_inventory_module else [sys.executable, str(root / "v9_rebuild/waat_monta_sharded.py"), "--out", str(staged)]
                       if waat_monta_module else [sys.executable, str(root / "v9_rebuild/waat_monta_public.py"), "--out", str(staged)]
                       if waat_monta_public_module else [sys.executable, str(root / "v9_rebuild/driveco_evse.py"), "--out", str(staged)]
                       if driveco_evse_module else [sys.executable, str(root / "v9_rebuild/uk_midhope.py"), "--out", str(staged)]
                       if uk_midhope_module else [sys.executable, str(root / "v9_rebuild/chargezy_te63.py"), "--out", str(staged)]
                       if chargezy_te63_module else [sys.executable, str(root / "v9_rebuild/uk_connected_kerb_operator.py"), "--out", str(staged)]
                       if uk_connected_kerb_operator_module else [sys.executable, str(root / "v9_rebuild/uk_connected_kerb_app.py"), "--out", str(staged), "--operator-state", str(operator_state)]
                       if uk_connected_kerb_app_module else [sys.executable, str(root / "v9_rebuild/uk_eco_movement.py"), "--out", str(staged)]
                       if uk_eco_movement_module else [sys.executable, str(root / "v9_rebuild/electra_france.py"), "--out", str(staged)]
                       if electra_france_module else [sys.executable, str(root / "v9_rebuild/energyvision.py"), "--out", str(staged)]
                       if energyvision_module else [sys.executable, str(root / "v9_rebuild/swiss_ecarup_finalizer.py"), "--out", str(staged), "--source", str(coordinate_state)]
                       if swiss_ecarup_finalizer_module else [sys.executable, str(root / "v9_rebuild/swiss_move.py"), "--method", spec["method"], "--out", str(staged)]
                       if swiss_move_module else [sys.executable, str(root / "v9_rebuild/swiss_plenitude_closeout.py"), "--out", str(staged), "--source", str(plenitude_state)]
                       if swiss_plenitude_closeout_module else [sys.executable, str(root / "v9_rebuild/morocco_inventory.py"), "--method", spec["method"], "--out", str(staged)]
                       if morocco_inventory_module else [sys.executable, str(root / "scripts/belgium_nap_full_country.py")])
            if morocco_reconcile_module:
                command = [sys.executable, str(root / "v9_rebuild/morocco_inventory.py"), "--method", "kilowatt_reconcile", "--out", str(staged), "--source", str(kilowatt_state)]
            if morocco_tariff_module:
                command = [sys.executable, str(root / "v9_rebuild/morocco_inventory.py"), "--method", "kilowatt_tariff_overlay", "--out", str(staged), "--source", str(kilowatt_state)]
            if swiss_ebs_closeout_module:
                command = [sys.executable, str(root / "v9_rebuild/swiss_ebs_closeout.py"), "--out", str(staged), "--source", str(ebs_state)]
            if swiss_cpi_module:
                command = [sys.executable, str(root / "v9_rebuild/swiss_cpi.py"), "--out", str(staged)]
            if swiss_powerup_module:
                command = [sys.executable, str(root / "v9_rebuild/swiss_powerup.py"), "--out", str(staged)]
            if swiss_powerup_closeout_module:
                command = [sys.executable, str(root / "v9_rebuild/swiss_powerup_closeout.py"), "--out", str(staged), "--source", str(powerup_state)]
            if swisscharge_module:
                command = [sys.executable, str(root / "v9_rebuild/swisscharge.py"), "--out", str(staged),
                           "--checkpoint", str(checkpoint)]
            if greenspot_module:
                command = [sys.executable, str(root / "v9_rebuild/greenspot.py"), "--out", str(staged)]
            if reve_stream_module:
                command = [sys.executable, str(root / "v9_rebuild/reve_stream.py"), "--out", str(staged),
                           "--checkpoint", str(checkpoint)]
            if reve_national_module:
                command = [sys.executable, str(root / "v9_rebuild/reve_national.py"), "--out", str(staged)]
            if delmonicos_module:
                command = [sys.executable, str(root / "v9_rebuild/delmonicos_watch.py"), "--out", str(staged)]
            if france_fixed_watch_module:
                command = [sys.executable, str(root / "v9_rebuild/france_fixed_watch.py"), "--out", str(staged)]
            if spain_fixed_secondary_module:
                command = [sys.executable, str(root / "v9_rebuild/spain_fixed_secondary.py"), "--out", str(staged)]
            if spain_fixed_core_module:
                command = [sys.executable, str(root / "v9_rebuild/spain_fixed_core.py"), "--out", str(staged)]
            if bfc_fixed_watch_module:
                command = [sys.executable, str(root / "v9_rebuild/bfc_fixed_watch.py"), "--out", str(staged)]
            if france_fixed_core_module:
                command = [sys.executable, str(root / "v9_rebuild/france_fixed_core.py"), "--out", str(staged)]
            if france_fixed_secondary_module:
                command = [sys.executable, str(root / "v9_rebuild/france_fixed_secondary.py"), "--out", str(staged)]
            if previous_state is not None:
                command.extend(["--source" if status_module else "--resume", str(previous_state)])
            if belib_prior is not None:
                command.extend(["--source", str(belib_prior)])
            if waat_monta_dependency:
                command.extend(["--inventory", str(inventory_state)])
            if source_id == "CH:ecarup_coordinate":
                command.extend(["--source", str(owner_state)])
            if electroverse_module and spec["mode"] == "full":
                command.extend(["--max-chunks", "1"])
            completed = runner(command, cwd=staged if spec["module"] == "belgium_nap" else root,
                               capture_output=True, text=True, timeout=timeout_s, check=False)
            output = staged / spec["output_file"]
            if completed.returncode != 0:
                reason = "collector_exit_nonzero"
                if checkpoint_module and (output.is_file() or status_module or (waat_monta_module and any((staged / f"data/shards/waat_monta_shard_{index}.json.gz").is_file() for index in range(4)))):
                    from v9_rebuild.electroverse import validate_state
                    from v9_rebuild.electroverse_status import validate_partial
                    from v9_rebuild.waat_monta_sharded import validate_checkpoint
                    try:
                        validate_checkpoint(staged) if waat_monta_module else validate_partial(staged) if status_module else validate_state(staged, require_complete=False)
                        if staged != checkpoint:
                            checkpoint.parent.mkdir(parents=True, exist_ok=True)
                            if checkpoint.exists():
                                shutil.rmtree(checkpoint)
                            staged.rename(checkpoint)
                            staged = checkpoint
                    except (OSError, ValueError, KeyError, TypeError):
                        reason = "collector_checkpoint_invalid"
                continue
            if not output.is_file():
                reason = "collector_output_missing"
                continue
            try:
                if (isolated_script or ionity_module or fastned_module or bump_inventory_module or bump_tariffs_module or allego_stations_module or cwd_script_module or uk_blink_module or uk_pcpr_module or uk_evyve_module or uk_gridserve_module or uk_ubitricity_module or uk_midhope_module or uk_connected_kerb_operator_module or uk_connected_kerb_app_module or uk_eco_movement_module or energyvision_module or freshmile_inventory_module or waat_monta_dependency or greenspot_module) and output.suffix == ".gz":
                    with gzip.open(output, "rt", encoding="utf-8") as handle:
                        payload = json.load(handle)
                else:
                    payload = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError, gzip.BadGzipFile):
                reason = "collector_output_invalid_json"
                continue
            if operator_module:
                source_evidence = payload.get("sourceEvidence") if isinstance(payload, dict) else None
                valid = (isinstance(payload, dict) and payload.get("operator") == spec["expected_operator"]
                         and payload.get("dataset") == spec["expected_dataset"]
                         and payload.get("country") == spec["expected_country"]
                         and isinstance(source_evidence, dict) and source_evidence.get("officialOnly") is True)
            elif nl_module:
                from v9_rebuild.nl_dotnl import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif electroverse_module:
                from v9_rebuild.electroverse import validate_state
                try:
                    validate_state(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                    valid = False
            elif status_module:
                from v9_rebuild.electroverse_status import validate_complete
                try:
                    validate_complete(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                    valid = False
            elif overlay_module:
                from v9_rebuild.electroverse_overlay import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, RuntimeError, gzip.BadGzipFile):
                    valid = False
            elif isolated_script:
                try:
                    valid = validate_isolated_script_output(spec, output)
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif belib_module:
                from v9_rebuild.belib import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif ionity_module:
                from v9_rebuild.ionity import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif fastned_module:
                from v9_rebuild.fastned import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif bump_inventory_module:
                from v9_rebuild.bump_inventory import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif bump_tariffs_module:
                from v9_rebuild.bump_tariffs import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif bump_official_module:
                from v9_rebuild.bump_official import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif allego_stations_module:
                from v9_rebuild.allego_stations import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif allego_official_module:
                from v9_rebuild.allego_official import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif official_rules_module:
                from v9_rebuild.official_rules import validate_output
                try:
                    validate_output(staged, spec["source"])
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif fx_module:
                from v9_rebuild.fx import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif suc_module:
                from v9_rebuild.suc_tracker import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif tesla_mac_module:
                from v9_rebuild.tesla_mac import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif cwd_script_module:
                from v9_rebuild.cwd_script import validate_output
                try:
                    validate_output(staged, spec["method"])
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif france_irve_module:
                from v9_rebuild.france_irve import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif france_canonical_module:
                from v9_rebuild.france_canonical import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif uk_blink_module:
                from v9_rebuild.uk_blink import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif uk_pcpr_module:
                from v9_rebuild.uk_pcpr import validate_output
                try:
                    validate_output(staged, spec["provider"])
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif uk_evyve_module:
                from v9_rebuild.uk_evyve import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif uk_gridserve_module:
                from v9_rebuild.uk_gridserve import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif uk_ubitricity_module:
                from v9_rebuild.uk_ubitricity import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif avia_picoty_extract_module:
                from v9_rebuild.avia_picoty_extract import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif electric55_chain_module:
                from v9_rebuild.electric55_chain import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif freshmile_inventory_module:
                from v9_rebuild.freshmile_inventory import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif waat_monta_module:
                from v9_rebuild.waat_monta_sharded import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif waat_monta_public_module:
                from v9_rebuild.waat_monta_public import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif driveco_evse_module:
                from v9_rebuild.driveco_evse import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif uk_midhope_module:
                from v9_rebuild.uk_midhope import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif chargezy_te63_module:
                from v9_rebuild.chargezy_te63 import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif uk_connected_kerb_operator_module:
                from v9_rebuild.uk_connected_kerb_operator import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif uk_connected_kerb_app_module:
                from v9_rebuild.uk_connected_kerb_app import validate_app_output
                try:
                    validate_app_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif uk_eco_movement_module:
                from v9_rebuild.uk_eco_movement import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif electra_france_module:
                from v9_rebuild.electra_france import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif energyvision_module:
                from v9_rebuild.energyvision import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swiss_ecarup_finalizer_module:
                from v9_rebuild.swiss_ecarup_finalizer import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swiss_move_module:
                from v9_rebuild.swiss_move import validate_output
                try:
                    validate_output(staged, spec["method"])
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swiss_plenitude_closeout_module:
                from v9_rebuild.swiss_plenitude_closeout import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif morocco_inventory_module:
                from v9_rebuild.morocco_inventory import validate_output
                try:
                    validate_output(staged, spec["method"])
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif morocco_reconcile_module:
                from v9_rebuild.morocco_inventory import validate_reconciliation
                try:
                    validate_reconciliation(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif morocco_tariff_module:
                from v9_rebuild.morocco_inventory import validate_tariff_overlay
                try:
                    validate_tariff_overlay(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swiss_ebs_closeout_module:
                from v9_rebuild.swiss_ebs_closeout import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swiss_cpi_module:
                from v9_rebuild.swiss_cpi import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swiss_powerup_module:
                from v9_rebuild.swiss_powerup import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swiss_powerup_closeout_module:
                from v9_rebuild.swiss_powerup_closeout import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif swisscharge_module:
                from v9_rebuild.swisscharge import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif greenspot_module:
                from v9_rebuild.greenspot import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif reve_stream_module:
                from v9_rebuild.reve_stream import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif reve_national_module:
                from v9_rebuild.reve_national import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif delmonicos_module:
                from v9_rebuild.delmonicos_watch import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif france_fixed_watch_module:
                from v9_rebuild.france_fixed_watch import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif spain_fixed_secondary_module:
                from v9_rebuild.spain_fixed_secondary import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif spain_fixed_core_module:
                from v9_rebuild.spain_fixed_core import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif bfc_fixed_watch_module:
                from v9_rebuild.bfc_fixed_watch import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif france_fixed_core_module:
                from v9_rebuild.france_fixed_core import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif france_fixed_secondary_module:
                from v9_rebuild.france_fixed_secondary import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            else:
                valid = isinstance(payload, dict) and validate_belgium_output(staged, payload)
            if not valid:
                reason = "collector_output_contract_mismatch"
                continue
            digest, files = artifact_digest(staged)
            target = source_dir / digest
            if not target.exists():
                try:
                    staged.rename(target)
                    staged = target
                except OSError:
                    if not target.exists():
                        raise
            elif checkpoint_module and staged == checkpoint:
                shutil.rmtree(checkpoint)
            if swisscharge_module and checkpoint.is_dir():
                shutil.rmtree(checkpoint)
            if reve_stream_module and checkpoint.is_dir():
                shutil.rmtree(checkpoint)
            return {
                "source": source_id,
                "status": "ok",
                "attempts": attempt,
                "module": spec["module"],
                "manifest_sha256": spec["manifest_sha256"],
                "artifact": str((target / spec["output_file"]).relative_to(out_root)),
                "sha256": sha256(target / spec["output_file"]),
                "artifact_set_sha256": digest,
                "files": files,
            }
        except subprocess.TimeoutExpired:
            reason = "collector_timeout"
        finally:
            if staged.exists() and staged.name.startswith("attempt-"):
                if belib_module and (staged / "reports/belib/latest_diagnostic.json").is_file():
                    diagnostic = out_root / "failures" / source_id.replace(":", "_") / "latest_diagnostic.json"
                    diagnostic.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(staged / "reports/belib/latest_diagnostic.json", diagnostic)
                shutil.rmtree(staged)
    return {"source": source_id, "status": "failed", "reason": reason, "attempts": attempts}


def run_batch(sources: list[dict], out_root: Path, *, root: Path = ROOT, workers: int = 2, attempts: int = 2, runner=subprocess.run) -> dict:
    out_root = out_root.resolve()
    if out_root == root.resolve() or root.resolve() in out_root.parents:
        raise ValueError("Artifact directory must be outside the source checkout")
    out_root.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_source, spec, out_root, root=root, attempts=attempts, runner=runner) for spec in sources]
        results = []
        for spec, future in zip(sources, futures):
            try:
                results.append(future.result())
            except Exception:
                results.append({"source": spec["id"], "status": "failed", "reason": "collector_exception"})
        results.sort(key=lambda row: row["source"])
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "complete" if all(row["status"] == "ok" for row in results) else "partial_failure",
        "sources": results,
    }
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="manifest-", suffix=".tmp", dir=out_root, delete=False) as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(out_root / "manifest.json")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", help="Exact source ID; omit to run every migrated source")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.attempts < 1:
        parser.error("workers and attempts must be positive")
    sources = read_sources()
    requested = set(args.source or [])
    known = {spec["id"] for spec in sources}
    if requested - known:
        parser.error(f"Unknown sources: {sorted(requested - known)}")
    selected = [spec for spec in sources if not requested or spec["id"] in requested]
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "sources": [spec["id"] for spec in selected]}))
        return 0
    result = run_batch(selected, args.out, workers=args.workers, attempts=args.attempts)
    print(json.dumps({"status": result["status"], "sources": result["sources"]}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
