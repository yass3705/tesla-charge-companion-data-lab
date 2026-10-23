"""Archived, technically proven canonical source routes for the V9 batch builder.

Each route points to a preserved source artifact and its existing normalizer.
Adding a route requires a source contract and a focused normalizer test.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Callable

from v9_rebuild.canonical import (
    normalize_atlante_italy,
    normalize_belib,
    normalize_belgium_nap,
    normalize_driveco_evse,
    normalize_france_irve_compact,
    normalize_ionity,
    normalize_midhope_verified,
    normalize_netherlands_dotnl,
    normalize_ozecar,
    normalize_swiss,
    normalize_zephyre_exact,
)
from v9_rebuild.canonical_uk_pcpr import normalize_uk_pcpr
from v9_rebuild.canonical_spain_reve import normalize_spain_reve
from v9_rebuild.canonical_morocco_evgo import normalize_morocco_evgo


@dataclass(frozen=True)
class CanonicalRoute:
    source_id: str
    archive: str
    normalizer: Callable
    manifest: str | None = None
    page_manifest: bool = False
    spain_reve_manifest: bool = False


ROUTES = (
    CanonicalRoute("MA:evgo", "reports/morocco/evgo/latest-production-stations.json",
                   normalize_morocco_evgo),
    CanonicalRoute("ES:reve_static", "data/reve_v2/validated_runtime/spain-static/all.json.gz",
                   normalize_spain_reve, "data/reve_v2/validated_runtime/spain-static/manifest.json",
                   spain_reve_manifest=True),
    CanonicalRoute("GB:allego_pcpr_direct", "data/national/uk_allego_uk_pcpr_v9.json.gz",
                   partial(normalize_uk_pcpr, source_id="GB:allego_pcpr_direct")),
    CanonicalRoute("GB:blink_pcpr_direct", "data/national/uk_blink_pcpr_v9.json.gz",
                   partial(normalize_uk_pcpr, source_id="GB:blink_pcpr_direct")),
    CanonicalRoute("GB:source_ev_pcpr_direct", "data/national/uk_source_ev_pcpr_v9.json.gz",
                   partial(normalize_uk_pcpr, source_id="GB:source_ev_pcpr_direct")),
    CanonicalRoute("BE:nap_static", "data/belgium/nap-belgium-manifest.json", normalize_belgium_nap,
                   page_manifest=True),
    CanonicalRoute("CH:swiss_integration", "data/national/switzerland_public_charging_v9.json", normalize_swiss),
    CanonicalRoute("DE:ionity_direct", "data/national/ionity_direct_stations_germany.json.gz", normalize_ionity),
    CanonicalRoute("FR:belib_stations", "data/national/belib_stations_paris.json", normalize_belib),
    CanonicalRoute("FR:driveco_evse_tariffs", "data/operator_direct/driveco_evse_tariffs.json", normalize_driveco_evse),
    CanonicalRoute("FR:irve_static", "data/national/france-irve-static-v9/all.json.gz",
                   normalize_france_irve_compact, "data/national/france-irve-static-v9/manifest.json"),
    CanonicalRoute("FR:ionity_direct", "data/national/ionity_direct_stations_france.json.gz", normalize_ionity),
    CanonicalRoute("FR:ozecar_monta", "data/ozecar/france/ozecar-france-current.json.gz", normalize_ozecar),
    CanonicalRoute("FR:zephyre_epowerdirect_exact", "data/operator_direct/zephyre_epowerdirect_exact_france_20260925.json", normalize_zephyre_exact),
    CanonicalRoute("GB:connected_kerb_midhope_verified", "data/national/uk_connected_kerb_midhope_verified_v9.json.gz", normalize_midhope_verified),
    CanonicalRoute("GB:ionity_direct", "data/national/ionity_direct_stations_uk.json.gz", normalize_ionity),
    CanonicalRoute("IT:atlante_direct", "data/national/atlante_direct_stations_italy_latest.json.gz", normalize_atlante_italy),
    CanonicalRoute("IT:ionity_direct", "data/national/ionity_direct_stations_italy.json.gz", normalize_ionity),
    CanonicalRoute("NL:dotnl_static", "data/national/netherlands_dotnl/normalized.json.gz", normalize_netherlands_dotnl),
)

BY_SOURCE = {route.source_id: route for route in ROUTES}
if len(BY_SOURCE) != len(ROUTES):
    raise ValueError("Canonical route source collision")
