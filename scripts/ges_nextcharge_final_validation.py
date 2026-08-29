#!/usr/bin/env python3
"""Freeze the validated GES/NextCharge Italy eMSP tariff semantics.

This script does not discover or invent tariffs. It consumes the already-built
national candidate plus two validation artifacts:
- public frontend unit-display probe;
- exact-UID recovery probe for operational PUN EVSE absent from NextCharge.

It emits a compact final validation report suitable for an integration review.
"""
from __future__ import annotations
import argparse,gzip,json
from datetime import datetime,timezone
from pathlib import Path

EXPECTED_COMPONENTS={"energy","time","parking","session"}

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def load_json(path):
    p=Path(path)
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
    with p.open('r',encoding='utf-8') as f:return json.load(f)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidate',required=True)
    ap.add_argument('--national-report',required=True)
    ap.add_argument('--unit-probe',required=True)
    ap.add_argument('--recovery',required=True)
    ap.add_argument('--out-dir',default='data/reports')
    args=ap.parse_args()

    candidate=load_json(args.candidate)
    national=load_json(args.national_report)
    unit=load_json(args.unit_probe)
    recovery=load_json(args.recovery)

    entries=candidate.get('entries') or []
    counts=national.get('counts') or {}
    q=national.get('qualityGates') or {}

    # Validate the public frontend evidence we rely on for units.
    matched={x.get('path'):x.get('value') for x in ((unit.get('language') or {}).get('matchedEntries') or []) if isinstance(x,dict)}
    assert matched.get('connectors_feekWh')=='Costo per kWh'
    assert matched.get('connectors_feeMinutes')=='Costo per minuto'
    bundle='\n'.join(unit.get('bundleUnitContexts') or [])
    assert 'prices.energy' in bundle or '.energy' in bundle
    assert 'prices.time' in bundle or '.time' in bundle
    assert 'prices.parking' in bundle or '.parking' in bundle
    assert (unit.get('security') or {}).get('staticPublicAssetsOnly') is True
    assert (unit.get('security') or {}).get('applicationApiCalled') is False

    operational=[e for e in entries if e.get('punOperationalState')=='operational']
    operational_empty=[]
    unknown_keys={}
    for e in entries:
        snap=e.get('tariffSnapshot') or {}
        prices=snap.get('prices') or {}
        for k in prices:
            if k not in EXPECTED_COMPONENTS:unknown_keys[k]=unknown_keys.get(k,0)+1
        if e.get('punOperationalState')=='operational' and not prices:
            operational_empty.append(e.get('evseId'))
    operational_empty=sorted(x for x in operational_empty if x)

    rcounts=recovery.get('counts') or {}
    unresolved=sorted(x.get('evseId') for x in (recovery.get('unresolved') or []) if x.get('evseId'))
    recovered=recovery.get('recovered') or []

    assertions={
      'nationalQualityGatesAllTrue': bool(q) and all(bool(v) for v in q.values()),
      'tariffConflictFree': counts.get('conflictingTariffEvse')==0,
      'unknownPriceKeysZero': not unknown_keys and not (counts.get('unknownPriceKeys') or {}),
      'allMatchedCurrencyEur': (counts.get('currencyDistribution') or {})=={'EUR':counts.get('exactMatchedEvse')},
      'operationalCoverageConsistent': len(operational)==counts.get('exactMatchedOperationalEvse'),
      'emptyOperationalCountConsistent': len(operational_empty)==counts.get('exactMatchedOperationalEvse',0)-counts.get('usableOperationalNextChargeEmspTariffEvse',0),
      'recoveryTargetsConsistent': rcounts.get('operationalMissingTargets')==counts.get('missingOperationalExactEvse'),
      'recoveryExactMatchesZero': rcounts.get('recoveredExactEvse')==0 and len(recovered)==0,
      'recoveryFailuresZero': rcounts.get('failures')==0,
      'recoveryUnresolvedConsistent': len(unresolved)==counts.get('missingOperationalExactEvse'),
      'operationalUsableCoverageGte95pct': float(counts.get('usableOperationalCoverage') or 0)>=0.95,
    }
    if not all(assertions.values()):
        raise SystemExit('Final GES validation assertion failed: '+json.dumps(assertions,ensure_ascii=False))

    final={
      'generatedAt':now(),
      'scope':{
        'country':'IT',
        'punPartyId':'GES',
        'commercialLayer':'emsp',
        'emsp':'NextCharge',
        'billedBy':'Go Electric Stations S.r.l.s.',
        'identityRule':'PUN evseId ITGESE<n> == NextCharge uidConnector <n>',
        'geographyUsedForIdentity':False,
        'rankableAsCpoDirectTariff':False,
      },
      'validatedTariffSemantics':{
        'energy':{'unit':'EUR/kWh','rankable':True,'evidence':'NextCharge public frontend label connectors_feekWh = Costo per kWh'},
        'time':{'unit':'EUR/min','rankable':True,'evidence':'NextCharge public frontend maps time to connectors_feeMinutes = Costo per minuto'},
        'parking':{'unit':'EUR/min','rankable':True,'conditional':True,'evidence':'NextCharge public frontend maps parking to connectors_feeMinutes; apply connector restrictions/trigger/window exactly'},
        'session':{'unit':'EUR/session','rankable':True,'evidence':'Official NextCharge terms define a per-session cost component'},
        'componentsAdditive':True,
        'consumerSnapshotRule':'Use the connector tariff shown by NextCharge; tariff may change without notice, therefore store extraction timestamp and refresh on demand/monthly.',
        'parkingRestrictionRule':'Do not charge parking unless the returned restriction/trigger conditions are satisfied.',
      },
      'officialEvidence':[
        {'kind':'terms','url':'https://nextcharge.app/apps/map/apis/terms/v1.4/termsAndConditions.php?appearanceFontSize=medium&appearanceTheme=auto&lang=it','supports':['Go Electric Stations billing','per connector tariff','per session/time/energy components','components additive','additional post-charge/parking fee can apply']},
        {'kind':'public_frontend_localization','url':(unit.get('language') or {}).get('url'),'supports':['energy EUR/kWh','minute-based time/parking display','parking warning semantics']},
      ],
      'nationalCoverage':counts,
      'failClosedOperational':{
        'exactMatchedButEmptyPrices':{
          'count':len(operational_empty),
          'evseIds':operational_empty,
          'policy':'Keep PUN station/status; no NextCharge tariff; not rankable.'
        },
        'absentFromCurrentNextChargeAfterExactRecovery':{
          'count':len(unresolved),
          'evseIds':unresolved,
          'recoverySearch':{
            'exactUidRequired':True,
            'uniqueNextChargeStationsQueried':rcounts.get('uniqueNextChargeStationsQueried'),
            'stationsGridRequests':(rcounts.get('requestCounts') or {}).get('stationsGrid'),
            'stationConnectorStationRequests':(rcounts.get('requestCounts') or {}).get('stationConnectorsStations'),
            'recoveredExactEvse':rcounts.get('recoveredExactEvse'),
            'failures':rcounts.get('failures'),
          },
          'policy':'Treat as roaming coverage gaps; keep PUN station/status; no NextCharge tariff; never geo-force a match.'
        }
      },
      'qualityAssertions':assertions,
      'integrationDecision':{
        'status':'validated_candidate',
        'canRankNextChargeEmspTariffs':True,
        'canRankAsGesCpoDirectTariffs':False,
        'readyForTccIntegrationReview':True,
        'mainMergePerformed':False,
      },
      'security':{
        'accountCredentialsUsed':False,
        'sessionTokenPersisted':False,
        'captchaBypassed':False,
        'paymentOrRechargeEndpointsCalled':False,
      }
    }

    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    jp=out/'ges_nextcharge_italy_final_validation.json'
    jp.write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    md=out/'ges_nextcharge_italy_final_validation.md'
    c=counts
    md.write_text(
      '# GES / NextCharge Italy — final validation\n\n'
      f"- PUN GES EVSE: **{c.get('punGesEvse')}**\n"
      f"- Exact NextCharge matches: **{c.get('exactMatchedEvse')}** ({float(c.get('exactMatchCoverage') or 0)*100:.2f}%)\n"
      f"- Operational PUN EVSE: **{c.get('punGesOperationalParseableEvse')}**\n"
      f"- Operational exact matches: **{c.get('exactMatchedOperationalEvse')}** ({float(c.get('operationalExactMatchCoverage') or 0)*100:.2f}%)\n"
      f"- Operational usable eMSP tariffs: **{c.get('usableOperationalNextChargeEmspTariffEvse')}** ({float(c.get('usableOperationalCoverage') or 0)*100:.2f}%)\n"
      f"- Operational exact matches with empty price object: **{len(operational_empty)}**\n"
      f"- Operational PUN EVSE absent after exact recovery: **{len(unresolved)}**\n"
      '- Units: energy EUR/kWh; time EUR/min; parking EUR/min conditional; session EUR/session. Components additive.\n'
      '- Commercial layer: **NextCharge eMSP**, billed by Go Electric Stations; **not** assumed to be the underlying CPO direct tariff.\n'
      '- Identity: exact `ITGESE<n>` ↔ `uidConnector <n>` only; geography never authorizes a tariff join.\n'
      '- Integration decision: **validated candidate**, ready for TCC integration review; no main merge performed.\n',
      encoding='utf-8')
    print(json.dumps({'report':str(jp),'markdown':str(md),'assertions':assertions,'operationalEmpty':len(operational_empty),'operationalUnresolved':len(unresolved)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
