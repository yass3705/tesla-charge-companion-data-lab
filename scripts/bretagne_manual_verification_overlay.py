#!/usr/bin/env python3
"""Overlay manually verified Bretagne station evidence onto generated regional outputs."""
from __future__ import annotations
import argparse, json
from pathlib import Path

SDE22_VERIFY = Path('data/station_verifications/ouestcharge_sde22_pledaran_app_2026_08_22.json')
BREST_VERIFY = Path('data/station_verifications/brest_easycharge_place_des_delisseurs_app_visibility_2026_08_22.json')


def load(path: Path):
    return json.loads(path.read_text())


def dump(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/bretagne')
    args = ap.parse_args()
    root = Path(args.out)

    v = load(SDE22_VERIFY)
    assert v['department'] == "Côtes-d'Armor"
    by_connector = {(x['connector'], x['powerKw']): x for x in v['connectorsVerified']}
    assert by_connector[('TYPE2', 22)]['energyEurPerKwh'] == 0.40
    assert by_connector[('CCS', 47)]['energyEurPerKwh'] == 0.40
    assert v['connectionTimeRuleDisplayed']['eurPerMinute'] == 0.20
    assert v['connectionTimeRuleDisplayed']['startsAfterConnectedMinutes'] == 300
    assert v['connectionTimeRuleDisplayed']['activeLocalWindow'] == '07:00-21:00'

    op_path = root / 'ouestcharge_bretagne_official.json'
    op = load(op_path)
    c = op['departments']["Côtes-d'Armor"]
    c['manualAppVerification'] = {
        'verifiedAt': v['verifiedAt'],
        'authorityDisplayed': v['networkAuthorityDisplayed'],
        'stationContext': v['stationContext'],
        'connectors': v['connectorsVerified'],
        'connectionTimeRuleDisplayed': v['connectionTimeRuleDisplayed'],
        'inactivityRuleDisplayed': v['inactivityRuleDisplayed'],
        'sessionFee': v['sessionFee'],
    }
    c['pricingRuleStatus'] = 'station_app_verified_precedence'
    c['directTariffClassable'] = False
    c['verifiedStationTariffClassable'] = True
    c['stationDisplayedTariffHasPriority'] = True
    c['ownerPageGridStatus'] = 'superseded_for_verified_station'
    c['centralPageStatus'] = '0.40_energy_confirmed_for_22kw_and_47kw_at_verified_station'
    c['resolutionNeeded'] = 'department-wide generalization remains blocked; use station-displayed tariff when available'
    op['tccDecision']['cotesArmorDirectClassable'] = False
    op['tccDecision']['cotesArmorVerifiedStationClassable'] = True
    op['tccDecision']['cotesArmorStationDisplayedTariffHasPriority'] = True
    op['sourceEvidence']['manualStationVerificationFile'] = str(SDE22_VERIFY)
    dump(op_path, op)

    reg_path = root / 'bretagne_regional_coverage.json'
    reg = load(reg_path)
    for row in reg['departmentCoverage']:
        if row['department'] == "Côtes-d'Armor":
            row['pricingRuleStatus'] = 'station_app_verified_precedence'
            row['verifiedStationTariffClassable'] = True
            row['stationDisplayedTariffHasPriority'] = True
            row['notes'] = [
                'Manual app verification confirms 0.40 EUR/kWh on both Type 2 22 kW and CCS 47 kW at the tested SDE22 station.',
                'The app also displays 0.20 EUR/min after five connected hours during 07:00-21:00 plus a separate inactivity line under the same conditions.',
                'The SDE22 owner-page 0.33/0.44/0.55 grid is superseded for this verified station; department-wide power-category generalization remains blocked.'
            ]
            break
    blocked = reg['coverage'].get('referenceOnlyOrBlockedFamilies', [])
    reg['coverage']['referenceOnlyOrBlockedFamilies'] = [x for x in blocked if not x.startswith('SDE22 / Ouest Charge')]
    reg['coverage']['stationLevelResolvedFamilies'] = ['SDE22 / Ouest Charge via app-displayed station tariff']
    reg['tccDecision']['stationDisplayedTariffHasPriorityForSDE22'] = True
    reg['tccDecision']['nextStep'] = 'verify Brest Métropole / Easy Charge Service direct live pricing; retain station-level tariff precedence for SDE22'

    b = load(BREST_VERIFY)
    assert b['department'] == 'Finistère'
    assert b['city'] == 'Brest'
    assert b['operator'] == 'Easy Charge Service'
    assert b['station']['officialPlannedName'] == 'Place des Délisseurs'
    assert b['station']['operatorAppVisible'] is False
    assert b['tccDecision']['treatAsLiveVerifiedStation'] is False
    assert b['tccDecision']['directTariffVerified'] is False

    brest_path = root / 'brest_easycharge_transition_bretagne.json'
    brest = load(brest_path)
    brest['manualAppVisibilityCheck'] = {
        'verifiedAt': b['verifiedAt'],
        'station': b['station']['officialPlannedName'],
        'city': b['city'],
        'publicIrveListingObserved': b['station']['publicIrveListingObserved'],
        'operatorAppVisible': b['station']['operatorAppVisible'],
        'liveStatus': 'not_confirmed_in_operator_app'
    }
    brest['tccDecision']['directEnergyTariffClassable'] = False
    brest['tccDecision']['defaultDisplay'] = 'reference_only_until_operator_app_or_on_site_reconfirmation'
    brest['tccDecision']['placeDesDelisseursLiveVerified'] = False
    brest['sourceEvidence']['manualStationVerificationFile'] = str(BREST_VERIFY)
    dump(brest_path, brest)

    for row in reg['departmentCoverage']:
        if row['department'] == 'Finistère':
            notes = row.setdefault('notes', [])
            notes.append('Place des Délisseurs is announced by Brest Métropole and appears in recent public IRVE data, but was not visible in the Easy Charge operator app during manual verification on 2026-08-22; keep it reference-only until reconfirmed.')
            break
    reg['tccDecision']['brestEasyChargePlaceDesDelisseursLiveVerified'] = False
    reg['tccDecision']['nextStep'] = 'find a currently visible Brest Easy Charge station in the operator app before resolving direct live pricing'
    reg['sourceEvidence']['manualStationVerificationFiles'] = [str(SDE22_VERIFY), str(BREST_VERIFY)]
    dump(reg_path, reg)

    summary = root / 'SUMMARY.md'
    text = summary.read_text() if summary.exists() else '# Bretagne coverage\n'
    text += ('\n## Manual resolution — Côtes-d\'Armor / SDE22\n\n'
             '- App verification: **0.40 EUR/kWh** on **Type 2 22 kW** and **CCS 47 kW** at the tested SDE22 station.\n'
             '- Connected-time component displayed: **0.20 EUR/min after 5 h, 07:00-21:00**.\n'
             '- Separate inactivity line displayed under the same conditions; do not double-count without operator confirmation.\n'
             '- SDE22 owner-page 0.33/0.44/0.55 grid is superseded for this station; station-displayed tariff has priority.\n')
    text += ('\n## Manual check — Brest / Easy Charge Service\n\n'
             '- **Place des Délisseurs** remains listed by Brest Métropole and in recent public IRVE data.\n'
             '- It was **not visible in the Easy Charge operator app** during manual verification on 2026-08-22.\n'
             '- Treat the station as **rollout/reference-only**, not live verified; no direct tariff should be inferred until operator-app or on-site reconfirmation.\n')
    summary.write_text(text)


if __name__ == '__main__':
    main()
