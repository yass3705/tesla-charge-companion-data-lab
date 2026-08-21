#!/usr/bin/env python3
"""Overlay manually verified Bretagne station evidence onto generated regional outputs."""
from __future__ import annotations
import argparse, json
from pathlib import Path

VERIFY = Path('data/station_verifications/ouestcharge_sde22_pledaran_app_2026_08_22.json')


def load(path: Path):
    return json.loads(path.read_text())


def dump(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/bretagne')
    args = ap.parse_args()
    root = Path(args.out)

    v = load(VERIFY)
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
    op['sourceEvidence']['manualStationVerificationFile'] = str(VERIFY)
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
    reg['sourceEvidence']['manualStationVerificationFiles'] = [str(VERIFY)]
    dump(reg_path, reg)

    summary = root / 'SUMMARY.md'
    text = summary.read_text() if summary.exists() else '# Bretagne coverage\n'
    text += ('\n## Manual resolution — Côtes-d\'Armor / SDE22\n\n'
             '- App verification: **0.40 EUR/kWh** on **Type 2 22 kW** and **CCS 47 kW** at the tested SDE22 station.\n'
             '- Connected-time component displayed: **0.20 EUR/min after 5 h, 07:00-21:00**.\n'
             '- Separate inactivity line displayed under the same conditions; do not double-count without operator confirmation.\n'
             '- SDE22 owner-page 0.33/0.44/0.55 grid is superseded for this station; station-displayed tariff has priority.\n')
    summary.write_text(text)


if __name__ == '__main__':
    main()
