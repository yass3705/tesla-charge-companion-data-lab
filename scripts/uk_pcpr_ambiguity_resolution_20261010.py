#!/usr/bin/env python3
"""Evidence-first UK CPO ambiguity audit. Read-only for pricing and V9 runtime.

Inspects each original ChargePoint PCPR OCPI connector, never guesses a tariff,
separates missing PAYG evidence from real contradictory offer rules, and
crosschecks current Connected Kerb / Allego / Blink / Gridserve dispositions.
"""
from __future__ import annotations
import collections
import csv
import gzip
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/uk"
SOURCE = ROOT / "data/national/uk_eco_movement_pcpr.json.gz"


def load(path):
    path = ROOT / path
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf8") as f:
        return json.load(f)


def txt(value):
    return str(value).strip() if value is not None else ""


def seq(value):
    return value if isinstance(value, list) else []


def tariff_components(tariff):
    for element in seq(tariff.get("elements")):
        for component in seq(element.get("price_components")):
            yield component, (element.get("restrictions") or {})


def identical_scope_conflict(tariff):
    """Only exact same restriction scope plus contradictory amount counts.

    Overlapping but different scopes require dedicated OCPI evaluation;
    identical TIME and PARKING_TIME are different units, NOT duplicates.
    """
    elements = list(tariff_components(tariff))
    for (a, ra), (b, rb) in combinations(elements, 2):
        if txt(a.get("type")) != txt(b.get("type")):
            continue
        if ra != rb:
            continue
        if a.get("price") != b.get("price") or a.get("step_size") != b.get("step_size"):
            return True
    return False


def main():
    raw = load("data/national/uk_eco_movement_pcpr.json.gz")
    existing = load("reports/uk/eco-movement-pcpr-v9-staging.json")
    ck = load("reports/uk/connected-kerb-app-collection-latest.json")
    ck_ex = load("reports/uk/connected-kerb-price-exclusions-latest.json")
    allego = load("reports/uk/allego_uk-pcpr-validation-latest.json")
    blink = load("reports/uk/blink-pcpr-validation-latest.json")
    grid = load("reports/uk/gridserve-v9-integration-latest.json")

    locations = seq(raw.get("locations"))
    tariffs = seq(raw.get("tariffs"))
    tariff_map = collections.defaultdict(list)
    for tariff in tariffs:
        tariff_map[(txt(tariff.get("country_code")), txt(tariff.get("party_id")), txt(tariff.get("id")))].append(tariff)

    counts = collections.Counter()
    tariff_reasons = collections.Counter()
    fee_profiles = collections.Counter()
    unsafe_refs = collections.Counter()
    issuer_type = collections.Counter()
    no_vat_by_kind = collections.Counter()
    conflicted_tariffs = set()
    unique_scopes = set()
    cases = []
    station_ids = set()
    for station in locations:
        loc_id = txt(station.get("id"))
        station_ids.add(loc_id)
        for evse in seq(station.get("evses")):
            evse_id = txt(evse.get("evse_id") or evse.get("uid"))
            for connector in seq(evse.get("connectors")):
                cid = txt(connector.get("id"))
                key = (loc_id, evse_id, cid)
                assert key not in unique_scopes, f"Duplicate connector key {key}"
                unique_scopes.add(key)
                tids = sorted({txt(tid) for tid in seq(connector.get("tariff_ids")) if txt(tid)})
                reasons = []
                combined_kinds = set()
                if station.get("publish") is not True:
                    reasons.append("location_not_explicitly_published")
                if not tids:
                    reasons.append("missing_tariff_reference")
                if len(tids) > 1:
                    reasons.append("multiple_tariffs_same_connector_requires_rule_selection")
                for tid in tids:
                    matches = tariff_map.get((txt(station.get("country_code")), txt(station.get("party_id")), tid), [])
                    if len(matches) != 1:
                        reasons.append("missing_or_duplicate_exact_tariff_record")
                        continue
                    tariff = matches[0]
                    currency = txt(tariff.get("currency")).upper()
                    if currency != "GBP":
                        reasons.append("foreign_currency_tariff")
                        unsafe_refs[tid] += 1
                    tariff_type = txt(tariff.get("type")).upper()
                    issuer_type[tariff_type or "MISSING"] += 1
                    if tariff_type != "AD_HOC_PAYMENT":
                        reasons.append("ad_hoc_payment_not_explicit_in_ocpi_tariff")
                    fields = list(tariff_components(tariff))
                    for component, restriction in fields:
                        kind = txt(component.get("type")).upper()
                        combined_kinds.add(kind)
                        if component.get("vat") is None:
                            no_vat_by_kind[kind] += 1
                            reasons.append("ocpi_vat_unspecified_20pct_derivation_not_operator_verified")
                        if kind not in {"ENERGY", "FLAT", "TIME", "PARKING_TIME"}:
                            reasons.append("unknown_price_component")
                        if restriction and any(k not in {
                            "start_time", "end_time", "day_of_week", "min_duration", "max_duration",
                            "min_power", "max_power", "start_date", "end_date",
                        } for k in restriction):
                            reasons.append("unsupported_tariff_restriction")
                    if identical_scope_conflict(tariff):
                        reasons.append("contradictory_same_dimension_same_restriction")
                        conflicted_tariffs.add(tid)
                    if {"TIME", "PARKING_TIME"} <= combined_kinds:
                        fee_profiles["charging_time_and_idle_time_distinct_dimensions"] += 1
                    if {"ENERGY", "TIME", "PARKING_TIME"} <= combined_kinds:
                        fee_profiles["energy_charging_idle_combined"] += 1
                reasons = sorted(set(reasons))
                for reason in reasons:
                    counts[reason] += 1
                counts["total_connectors"] += 1
                # A price cannot be used as confirmed direct-PAYG without
                # payment attribution and verified VAT semantics.
                decision = ("tarif_ambigu" if "contradictory_same_dimension_same_restriction" in reasons
                            else "tarif_incalculable" if "multiple_tariffs_same_connector_requires_rule_selection" in reasons
                            else "tarif_indisponible" if "foreign_currency_tariff" in reasons or
                                 "missing_tariff_reference" in reasons or
                                 "missing_or_duplicate_exact_tariff_record" in reasons
                            else "verification_requise_ne_pas_promouvoir_comme_payg_valide")
                counts["decision:" + decision] += 1
                cases.append({
                    "locationId": loc_id, "stationName": txt(station.get("name")),
                    "city": txt(station.get("city")), "evseId": evse_id, "connectorId": cid,
                    "powerW": connector.get("max_electric_power"), "tariffIds": ";".join(tids),
                    "decision": decision, "reasons": ";".join(reasons),
                    "source": "Eco-Movement ChargePoint PCPR CPO OCPI 2.2.1",
                })

    for t in tariffs:
        tid = txt(t.get("id"))
        if not t.get("type"):
            tariff_reasons["unspecified_tariff_type"] += 1
        if txt(t.get("currency")).upper() != "GBP":
            tariff_reasons["non_GBP_tariff"] += 1
        if identical_scope_conflict(t):
            tariff_reasons["same_dimension_same_scope_conflict"] += 1
        kinds = {txt(c.get("type")).upper() for c, _ in tariff_components(t)}
        if {"TIME", "PARKING_TIME"} <= kinds:
            tariff_reasons["both_charge_time_and_idle_time"] += 1
        if any(c.get("vat") is None for c, _ in tariff_components(t)):
            tariff_reasons["at_least_one_vat_absent"] += 1

    # Connected Kerb: preserve every excluded connector's original evidence.
    # A real price conflict is distinct from an unidentified tariff or an
    # unresolved correspondence. Never lift a quarantine by station average.
    ck_rows = []
    ck_labels = collections.Counter()
    for item in ck_ex["excludedConnectors"]:
        reasons = seq(item.get("reasons"))
        reason = reasons[0] if reasons else "no_validated_app_detail"
        if reason == "multiple_energy_prices_without_windows":
            label, priority = "tarif_ambigu", "P1"
        elif reason == "fee_unit_verification_pending":
            label, priority = "tarif_incalculable", "P1"
        elif reason == "no_unique_standard_tariff":
            label, priority = "tarif_non_attribuable", "P2"
        elif reason in {"no_unique_exact_socket_match", "no_unique_exact_qr_and_geo_match"}:
            label, priority = "correspondance_non_verifiee", "P3"
        else:
            label, priority = "tarif_indisponible", "P4"
        ck_labels[label] += 1
        ck_rows.append({
            "priority":priority, "stationName":txt(item.get("stationName")),
            "stationId":txt(item.get("stationId")), "evseId":txt(item.get("evseId")),
            "connectorId":txt(item.get("connectorId")), "reason":reason,
            "classification":label, "source":txt(item.get("reasonReport")),
        })
    ck_csv = REPORTS / "connected-kerb-unresolved-connectors-2026-10-10.csv"
    ck_urgent = REPORTS / "connected-kerb-priority-ambiguities-2026-10-10.csv"
    for target, items in ((ck_csv,ck_rows), (ck_urgent,[x for x in ck_rows if x["priority"] == "P1"])):
        with target.open("w", newline="", encoding="utf8") as out:
            w = csv.DictWriter(out, fieldnames=list(ck_rows[0]))
            w.writeheader()
            w.writerows(items)
    assert len(ck_rows) == ck_ex["excludedConnectorCount"]
    assert ck_labels["tarif_ambigu"] == ck["unresolvedReasonCounts"]["multiple_energy_prices_without_windows"]
    assert ck_labels["tarif_incalculable"] == ck["unresolvedReasonCounts"]["fee_unit_verification_pending"]
    assert ck_labels["tarif_ambigu"] + ck_labels["tarif_incalculable"] == 56

    assert counts["total_connectors"] == 1142, "Unexpected source baseline, inspect before promoting"
    assert len(station_ids) == 323
    assert sum(1 for c in cases if c["decision"] == "tarif_indisponible") == existing["stagedUnpricedConnectors"], "Quarantine parity"
    assert counts["foreign_currency_tariff"] == existing["stagedUnpricedConnectors"]
    assert not conflicted_tariffs, "Confirmed contradictory source tariffs need manual handling"
    assert ck_ex["excludedConnectorCount"] == ck["unresolvedConnectors"], "Connected Kerb evidence mismatch"
    assert ck_ex["retainedConnectorCount"] == ck["resolvedConnectors"], "Connected Kerb resolved mismatch"
    assert allego["validatedForV9"] and allego["unpricedPublicConnectors"] == 0
    assert blink["validatedForV9"] and blink["unpricedPublicConnectors"] == 0
    assert grid["validatedForV9"] and grid["unpricedPublicConnectors"] == 0

    REPORTS.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS / "chargepoint-pcpr-connector-review-2026-10-10.csv"
    with csv_path.open("w", newline="", encoding="utf8") as out:
        w = csv.DictWriter(out, fieldnames=list(cases[0]))
        w.writeheader()
        w.writerows(cases)
    data = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "UK CPO DIRECT; independent evidence review; no V9 activation or price rewriting",
        "chargePoint": {
            "sourceCollectedAt": raw.get("retrievedAt"),
            "locations": len(locations), "connectors": len(cases), "tariffs": len(tariffs),
            "connectorDisposition": dict(sorted((k.split("decision:",1)[1],v) for k,v in counts.items() if k.startswith("decision:"))),
            "connectorEvidenceIssues": dict(sorted((k,v) for k,v in counts.items() if k != "total_connectors" and not k.startswith("decision:"))),
            "tariffEvidenceIssues": dict(tariff_reasons),
            "feeInterpretation": {"TIME":"charging time only", "PARKING_TIME":"idle/not-charging time only",
                "separateDimensionsNotAnAutomaticConflict": True,
                "chargingAndParkingComponentConnectorOccurrences":fee_profiles["charging_time_and_idle_time_distinct_dimensions"]},
            "vatComponentMissing": dict(no_vat_by_kind),
            "foreignCurrencyTariffReferenceCounts": dict(unsafe_refs),
            "currentStaging": {
                "pricedByArithmeticButNotPAYGVerified": existing["stagedRankableDirectOffers"],
                "excludedFromArithmetic":existing["stagedUnpricedConnectors"],
                "currentV9Activation": "not_verified_by_source_report",
                "note": "Tariff.type absent; calculated 20% VAT is a statutory inference, not per-offer operator attestation."
            },
            "guards": [
                "Never convert a USD FLAT 0 into GBP or interpret it as confirmed free charging",
                "Never rank missing-type prices as verified anonymous ad-hoc without independent CPO evidence",
                "TIME and PARKING_TIME must use charging and idle durations separately, never same elapsed minutes twice",
                "Missing OCPI VAT must retain inferred-VAT provenance and be independently checked against customer-facing PAYG",
                "Only exact location+EVSE+connector+tariff identity may receive a tariff",
                "Manual list is per connector, not a station-level tariff extrapolation",
            ],
            "manualReviewCsv":str(csv_path.relative_to(ROOT)),
        },
        "otherUKCPO": {
            "ConnectedKerb": {"sourceCollectedAt":ck["collectedAt"],
                "resolvedConnectors":ck["resolvedConnectors"], "excludedConnectors":ck["unresolvedConnectors"],
                "unresolvedReasonCounts":ck.get("unresolvedReasonCounts",{}),
                "noUnverifiedFeesAssumed":True,
                "classifiedExcludedConnectors":dict(ck_labels),
                "manualReviewAllCsv":str(ck_csv.relative_to(ROOT)),
                "manualPriority1Csv":str(ck_urgent.relative_to(ROOT)),
                "manualPriority1Connectors":sum(x["priority"] == "P1" for x in ck_rows)},
            "Allego":{"publicExactPricedConnectors":allego["exactPricedConnectors"],"unpricedPublicConnectors":allego["unpricedPublicConnectors"],"state":allego["status"]},
            "Blink":{"publicExactPricedConnectors":blink["exactPricedConnectors"],"unpricedPublicConnectors":blink["unpricedPublicConnectors"],"state":blink["status"]},
            "Gridserve":{"publicExactPricedConnectors":grid["exactPricedConnectors"],"unpricedPublicConnectors":grid["unpricedPublicConnectors"],"excludedLocationReasons":grid["excludedCounts"],"state":grid["status"]},
        },
        "status":"validated_source_conflicts_quarantined_payment_scope_still_pending",
    }
    out = REPORTS / "uk-cpo-ambiguity-review-2026-10-10.json"
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("UK_CPO_AMBIGUITY_AUDIT="+json.dumps({
        "connectors":len(cases),"decision":data["chargePoint"]["connectorDisposition"],
        "vatMissing":tariff_reasons["at_least_one_vat_absent"],
        "tariffTypesMissing":tariff_reasons["unspecified_tariff_type"],
        "ambiguousSameScopeTariffs":len(conflicted_tariffs),
        "connectedKerbExcluded":ck["unresolvedConnectors"],
        "connectedKerbTrueAmbiguity":ck_labels["tarif_ambigu"],
        "connectedKerbIncalculableFee":ck_labels["tarif_incalculable"],
        "allegoValidated":allego["exactPricedConnectors"],
        "blinkValidated":blink["exactPricedConnectors"],
        "gridserveValidated":grid["exactPricedConnectors"],
        "status":data["status"]
    },ensure_ascii=False))


if __name__ == "__main__":
    main()
