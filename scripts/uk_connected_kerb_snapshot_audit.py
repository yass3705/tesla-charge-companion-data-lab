#!/usr/bin/env python3
"""Audit a persisted Connected Kerb snapshot without API credentials."""
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def without_timestamps(value):
    if isinstance(value, dict):
        return {k: without_timestamps(v) for k, v in value.items() if k != "last_updated"}
    if isinstance(value, list):
        return [without_timestamps(v) for v in value]
    return value


def main():
    with gzip.open(ROOT / "data/national/uk_connected_kerb_locations.json.gz", "rt") as f:
        source = json.load(f)
    with gzip.open(ROOT / "data/national/uk_connected_kerb_tariffs.json.gz", "rt") as f:
        tariffs = json.load(f)["tariffs"]
    groups = defaultdict(list)
    for loc in source["locations"]:
        groups[loc["id"]].append(loc)
    conflicts = []
    for key, rows in groups.items():
        if any(without_timestamps(row) != without_timestamps(rows[0]) for row in rows[1:]):
            conflicts.append(key)
    # A view for counts only; the complete raw response remains untouched.
    unique = [max(rows, key=lambda row: row.get("last_updated", "")) for rows in groups.values()]
    public = [loc for loc in unique if loc.get("publish") is True]
    multi_energy = []
    no_energy = []
    non_energy = []
    for tariff in tariffs:
        components = [pc for el in tariff["elements"] for pc in el["price_components"]]
        prices = {(pc["price"], pc.get("vat")) for pc in components if pc["type"] == "ENERGY"}
        if len(prices) > 1:
            multi_energy.append(tariff["id"])
        if not prices:
            no_energy.append(tariff["id"])
        if any(pc["type"] != "ENERGY" for pc in components):
            non_energy.append(tariff["id"])
    tariff_map = {tariff["id"]: tariff for tariff in tariffs}
    connectors = {c["id"]: c for loc in public for evse in loc["evses"] for c in evse["connectors"]}
    missing = sorted({tid for c in connectors.values() for tid in c.get("tariff_ids", []) if tid not in tariff_map})
    audit = {
        "provider": "Connected Kerb", "snapshotCollectedAt": source["collectedAt"],
        "rawLocationRows": len(source["locations"]), "distinctLocationIds": len(unique),
        "extraRepeatedRows": len(source["locations"]) - len(unique),
        "identicalDuplicateGroups": sum(len(rows) > 1 and all(row == rows[0] for row in rows[1:]) for rows in groups.values()),
        "duplicateGroupsDifferingOnlyInTimestamps": sum(len(rows) > 1 and any(row != rows[0] for row in rows[1:])
            and all(without_timestamps(row) == without_timestamps(rows[0]) for row in rows[1:]) for rows in groups.values()),
        "substantiveConflictingLocationIds": conflicts,
        "distinctPublishedLocations": len(public), "distinctNonpublishedLocations": len(unique) - len(public),
        "distinctPublishedEvses": len({e["uid"] for loc in public for e in loc["evses"]}),
        "distinctPublishedConnectors": len(connectors), "missingReferencedTariffIds": missing,
        "tariffs": len(tariffs), "tariffsWithMultipleEnergyPricesAndNoRestrictions": multi_energy,
        "tariffsWithoutEnergyPrice": no_energy, "tariffsWithAdditionalFeeComponents": non_energy,
        "publishedConnectorsReferencingMultiPriceTariffs": sum(bool(set(c.get("tariff_ids", [])) & set(multi_energy)) for c in connectors.values()),
        "publishedConnectorsWithMultipleTariffReferences": sum(len(c.get("tariff_ids", [])) > 1 for c in connectors.values()),
        "scope": "publish=true is a source flag; public access, planned/removed EVSEs and concessions still need publication filtering",
        "pricingBlocker": "Tariff objects lack type/name/restrictions; multiple ENERGY prices and multiple tariff references cannot be assigned to retail/ad-hoc or time windows without further operator clarification.",
        "publishedToV9": False,
    }
    path = ROOT / "reports/uk/connected-kerb-snapshot-audit-latest.json"
    path.write_text(json.dumps(audit, indent=2) + "\n")
    assert not conflicts and not missing
    print(json.dumps({k: v for k, v in audit.items() if not isinstance(v, list)}, indent=2))


if __name__ == "__main__":
    main()
