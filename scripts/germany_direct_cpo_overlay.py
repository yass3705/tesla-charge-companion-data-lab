#!/usr/bin/env python3
"""Apply validated direct-CPO tariff evidence to the staged German catalog.

Staging precedence implemented here:
1. validated direct CPO tariff evidence;
2. validated simple AFIR ad-hoc fallback when no direct CPO applies.

EWE Go has one scalar own-network price. EnBW intercharge direct has
connector-class-specific AC/DC pricing. Wirelane has EVSE-specific public
direct-payment prices and is applied only to physical sites for which every
expected Wirelane EVSE was successfully resolved and parsed.

No production tariff ranking is enabled by this overlay.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_gz(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def compact_wirelane_evse(row: dict):
    """Keep auditable tariff evidence without importing unrelated page metadata."""
    parsed = row.get("parsed") or {}
    return {
        "evseId": row.get("evseId"),
        "canonicalEvseId": row.get("canonicalEvseId"),
        "url": row.get("url"),
        "tariffText": row.get("tariffText"),
        "eurPerKwh": parsed.get("eurPerKwh"),
        "startFeeEur": parsed.get("startFeeEur"),
        "minuteFeeEur": parsed.get("minuteFeeEur"),
        "afterMinutes": parsed.get("afterMinutes"),
        "capEur": parsed.get("capEur"),
        "inactiveLocalTime": parsed.get("inactiveLocalTime"),
        "taxIncluded": parsed.get("taxIncluded"),
        "providerConfirmed": row.get("providerWirelane") is True,
        "evseIdConfirmed": row.get("pageEvseId") == row.get("evseId"),
        "complete": row.get("complete") is True,
    }


def set_afir_fallback(site: dict):
    pricing = site.setdefault("pricing", {})
    if not pricing.get("stagingRankableCandidate"):
        return False
    price = pricing.get("stagingEffectiveEurPerKwh")
    if price is None:
        return False
    afir_data = ((site.get("afir") or {}).get("data") or {})
    pricing["stagingPreferredTariff"] = {
        "sourceType": "afir",
        "provider": afir_data.get("provider"),
        "selectionMode": "site_scalar",
        "currency": "EUR",
        "eurPerKwh": price,
        "reason": "validated_afir_fallback_no_direct_cpo",
        "productionRankable": False,
    }
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz"))
    ap.add_argument("--ewe", type=Path, default=Path("data/germany/ewe_go_direct_tariff.json"))
    ap.add_argument("--enbw", type=Path, default=Path("data/germany/enbw_direct_tariff.json"))
    ap.add_argument("--wirelane", type=Path, default=Path("data/germany/wirelane_direct_tariffs.json.gz"))
    ap.add_argument("--output", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo.json.gz"))
    ap.add_argument("--manifest", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo_manifest.json"))
    args = ap.parse_args()

    catalog = load_gz(args.catalog)
    ewe = load_json(args.ewe)
    enbw = load_json(args.enbw)
    wirelane = load_gz(args.wirelane)
    if catalog.get("dataset") != "germany-national-non-tesla-catalog-staging-tariff-classified":
        raise RuntimeError("unexpected catalog dataset")
    if ewe.get("dataset") != "germany-ewe-go-direct-tariff":
        raise RuntimeError("unexpected EWE dataset")
    if enbw.get("dataset") != "germany-enbw-direct-tariff":
        raise RuntimeError("unexpected EnBW dataset")
    if wirelane.get("dataset") != "germany-wirelane-direct-tariffs":
        raise RuntimeError("unexpected Wirelane dataset")

    ewe_ops = set(ewe["operator"]["bnetzaExactOperators"])
    enbw_ops = set(enbw["operator"]["bnetzaExactOperators"])
    wirelane_ops = set(wirelane["operator"]["bnetzaExactOperators"])
    ewe_own = ewe["directOwnNetwork"]
    enbw_own = enbw["directOwnNetwork"]
    if ewe_own.get("rankableCandidate") is not True:
        raise RuntimeError("EWE not eligible")
    if enbw.get("scope", {}).get("siteScalarPriceSafe") is not False:
        raise RuntimeError("EnBW scalar safety contract changed")
    if wirelane.get("scope", {}).get("tariffModel") != "evse_specific":
        raise RuntimeError("Wirelane tariff model changed")

    # Only complete sites are eligible for direct-CPO staging precedence.
    wirelane_by_site = {}
    for ws in wirelane.get("sites") or []:
        if not ws.get("fullyCovered"):
            continue
        evse_rows = ws.get("evseTariffs") or []
        if not evse_rows or len(evse_rows) != ws.get("expectedEvseCount"):
            raise RuntimeError(f"Wirelane complete-site EVSE count mismatch: {ws.get('siteId')}")
        if not all(row.get("complete") is True for row in evse_rows):
            raise RuntimeError(f"Wirelane incomplete EVSE inside complete site: {ws.get('siteId')}")
        wirelane_by_site[ws["siteId"]] = ws

    provider_counts = Counter()
    scalar_sites = 0
    connector_class_sites = 0
    evse_specific_sites = 0
    afir_candidates_overridden = 0
    direct_without_afir = 0
    afir_fallback_sites = 0
    afir_deltas = Counter()
    afir_price_pairs = Counter()
    outside_exact = 0
    wirelane_partial_not_applied = 0
    exact_all = ewe_ops | enbw_ops | wirelane_ops

    # Initialize an explicit safe-AFIR fallback before direct CPOs override it.
    for site in catalog.get("sites") or []:
        pricing = site.setdefault("pricing", {})
        pricing["rankable"] = False
        pricing["stagingPreferredTariff"] = None
        pricing["directCpo"] = None
        pricing.pop("directVsAfir", None)
        if set_afir_fallback(site):
            afir_fallback_sites += 1

    for site in catalog.get("sites") or []:
        pricing = site["pricing"]
        op = site.get("operator")
        afir_candidate = bool(pricing.get("stagingRankableCandidate") and pricing.get("stagingEffectiveEurPerKwh") is not None)

        if op in ewe_ops:
            provider_counts["EWE Go"] += 1
            scalar_sites += 1
            pricing["directCpo"] = {
                "provider": "EWE Go",
                "operatorExactMatch": op,
                "sourceDataset": ewe["dataset"],
                "sourceUrl": ewe["source"]["url"],
                "sourceSha256": ewe["source"]["sha256"],
                "tariffModel": "site_scalar",
                "currency": ewe_own["currency"],
                "eurPerKwh": ewe_own["eurPerKwh"],
                "taxIncluded": ewe_own["taxIncluded"],
                "monthlyFeeEur": ewe_own["monthlyFeeEur"],
                "blockingFee": ewe_own["blockingFee"],
                "acDcSamePrice": ewe_own["acDcSamePrice"],
                "scope": "operator-own-network",
                "stagingRankableCandidate": True,
                "requiresConnectorClass": False,
            }
            pricing["stagingPreferredTariff"] = {
                "sourceType": "direct_cpo",
                "provider": "EWE Go",
                "selectionMode": "site_scalar",
                "currency": "EUR",
                "eurPerKwh": ewe_own["eurPerKwh"],
                "taxIncluded": True,
                "reason": "direct_cpo_precedes_afir",
                "productionRankable": False,
            }
            if afir_candidate:
                afir_candidates_overridden += 1
                afir_fallback_sites -= 1
                afir_price = pricing["stagingEffectiveEurPerKwh"]
                delta = round(float(afir_price) - float(ewe_own["eurPerKwh"]), 6)
                afir_deltas[delta] += 1
                afir_price_pairs[(round(float(afir_price), 6), round(float(ewe_own["eurPerKwh"]), 6))] += 1
                pricing["directVsAfir"] = {
                    "afirEurPerKwh": afir_price,
                    "directEurPerKwh": ewe_own["eurPerKwh"],
                    "afirMinusDirectEurPerKwh": delta,
                    "preferred": "direct_cpo",
                }
            else:
                direct_without_afir += 1

        elif op in enbw_ops:
            provider_counts["EnBW mobility+"] += 1
            connector_class_sites += 1
            tariffs = enbw_own["connectorClassTariffs"]
            pricing["directCpo"] = {
                "provider": "EnBW mobility+",
                "operatorExactMatch": op,
                "sourceDataset": enbw["dataset"],
                "sourceUrl": enbw["source"]["url"],
                "sourceSha256": enbw["source"]["sha256"],
                "tariffModel": "connector_class",
                "accessMethod": enbw_own["accessMethod"],
                "monthlyFeeEur": enbw_own["monthlyFeeEur"],
                "connectorClassTariffs": tariffs,
                "scope": "operator-own-network",
                "stagingRankableCandidate": False,
                "requiresConnectorClass": True,
            }
            pricing["stagingPreferredTariff"] = {
                "sourceType": "direct_cpo",
                "provider": "EnBW mobility+",
                "selectionMode": "connector_class",
                "connectorClassTariffs": tariffs,
                "reason": "direct_cpo_precedes_afir_but_connector_class_required",
                "productionRankable": False,
            }
            if afir_candidate:
                afir_candidates_overridden += 1
                afir_fallback_sites -= 1
            else:
                direct_without_afir += 1

        elif op in wirelane_ops:
            ws = wirelane_by_site.get(site.get("id"))
            if ws is None:
                wirelane_partial_not_applied += 1
                continue
            provider_counts["Wirelane"] += 1
            evse_specific_sites += 1
            compact_evses = [compact_wirelane_evse(row) for row in (ws.get("evseTariffs") or [])]
            pricing["directCpo"] = {
                "provider": "Wirelane",
                "operatorExactMatch": op,
                "sourceDataset": wirelane["dataset"],
                "sourceType": wirelane["source"]["type"],
                "tariffModel": "evse_specific",
                "currency": "EUR",
                "scope": "operator-own-network",
                "requiresEvseSelection": True,
                "allExpectedEvseCovered": True,
                "expectedEvseCount": ws.get("expectedEvseCount"),
                "uniformTariffAcrossEvse": ws.get("uniformTariffAcrossEvse") is True,
                "uniformTariff": ws.get("uniformTariff"),
                "evseTariffs": compact_evses,
                "stagingRankableCandidateWhenEvseKnown": True,
                "providerPageAvailabilityNotUsedForServiceState": True,
            }
            pricing["stagingPreferredTariff"] = {
                "sourceType": "direct_cpo",
                "provider": "Wirelane",
                "selectionMode": "evse_specific",
                "currency": "EUR",
                "evseTariffs": compact_evses,
                "allExpectedEvseCovered": True,
                "reason": "direct_cpo_precedes_afir_evse_specific",
                "productionRankable": False,
            }
            if afir_candidate:
                afir_candidates_overridden += 1
                afir_fallback_sites -= 1
            else:
                direct_without_afir += 1

    for site in catalog.get("sites") or []:
        if (site.get("pricing") or {}).get("directCpo") and site.get("operator") not in exact_all:
            outside_exact += 1

    total_direct = sum(provider_counts.values())
    catalog["schemaVersion"] = "0.5.0"
    catalog["dataset"] = "germany-national-non-tesla-catalog-staging-direct-cpo"
    catalog["scope"].update({
        "directCpoTariffsIncluded": True,
        "directCpoPrecedesAfirInStaging": True,
        "validatedAfirFallbackIncluded": True,
        "connectorClassDirectTariffsSupported": True,
        "evseSpecificDirectTariffsSupported": True,
        "tariffsRankable": False,
        "publishesToTcc": False,
    })
    s = catalog["stats"]
    s["directCpoSites"] = total_direct
    s["directCpoProviders"] = dict(provider_counts)
    s["directCpoSiteScalarSites"] = scalar_sites
    s["directCpoConnectorClassRequiredSites"] = connector_class_sites
    s["directCpoEvseSpecificSites"] = evse_specific_sites
    s["directCpoAfirCandidatesOverridden"] = afir_candidates_overridden
    s["validatedAfirFallbackPreferredSites"] = afir_fallback_sites
    s["directCpoSitesWithoutRankableAfirCandidate"] = direct_without_afir
    s["directCpoAppliedOutsideExactOperator"] = outside_exact
    s["wirelaneFullyCoveredDirectSites"] = len(wirelane_by_site)
    s["wirelanePartialSitesNotApplied"] = wirelane_partial_not_applied
    s["wirelaneSourceEvseExpected"] = (wirelane.get("stats") or {}).get("evseExpected")
    s["wirelaneSourceEvseComplete"] = (wirelane.get("stats") or {}).get("evseComplete")
    s["eweGoDirectVsAfirDeltaDistribution"] = [
        {"afirMinusDirectEurPerKwh": d, "sites": n} for d, n in afir_deltas.most_common()
    ]
    s["eweGoAfirDirectPricePairs"] = [
        {"afirEurPerKwh": p[0], "directEurPerKwh": p[1], "sites": n}
        for p, n in afir_price_pairs.most_common()
    ]
    catalog.setdefault("sources", {})["eweGoDirectTariff"] = {
        "generatedAt": ewe.get("generatedAt"),
        "source": ewe.get("source"),
        "ownNetwork": ewe_own,
        "roamingPartnerStoredNotApplied": ewe.get("roamingPartner"),
    }
    catalog["sources"]["enbwDirectTariff"] = {
        "generatedAt": enbw.get("generatedAt"),
        "source": enbw.get("source"),
        "ownNetwork": enbw_own,
    }
    catalog["sources"]["wirelaneDirectTariffs"] = {
        "generatedAt": wirelane.get("generatedAt"),
        "source": wirelane.get("source"),
        "stats": wirelane.get("stats"),
        "priceDistribution": wirelane.get("priceDistribution"),
        "partialSitesStoredNotApplied": wirelane_partial_not_applied,
    }

    save_gz(args.output, catalog)
    manifest = {
        "schemaVersion": "0.5.0",
        "dataset": catalog["dataset"],
        "countryCode": "DE",
        "stagedOnly": True,
        "publishesToTcc": False,
        "productionRankingEnabled": False,
        "catalogFile": args.output.name,
        "stats": s,
        "scope": catalog["scope"],
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_GERMANY_DIRECT_CPO_OVERLAY=" + json.dumps({
        "directCpoSites": total_direct,
        "providers": dict(provider_counts),
        "scalarSites": scalar_sites,
        "connectorClassSites": connector_class_sites,
        "evseSpecificSites": evse_specific_sites,
        "afirCandidatesOverridden": afir_candidates_overridden,
        "afirFallbackPreferredSites": afir_fallback_sites,
        "wirelanePartialNotApplied": wirelane_partial_not_applied,
        "outsideExactOperator": outside_exact,
        "pricePairs": s["eweGoAfirDirectPricePairs"][:20],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
