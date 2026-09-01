#!/usr/bin/env python3
"""Build a conservative Free To X direct tariff layer from PUN F2X inventory.

Only tariff cases explicitly supported by current official card-payment terms are
rankable:
- AC: 0.50 EUR/kWh
- DC up to and including 64 kW: promotional 0.50 EUR/kWh, valid 2026-07-15..2026-09-30

DC above 64 kW remains blocked until an official machine-readable or explicit
power threshold separating ordinary DC (0.65) from HPC (0.79) is validated.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PARTY = "F2X"
AC_PRICE = 0.50
PROMO_DC_PRICE = 0.50
PROMO_FROM = "2026-07-15"
PROMO_THROUGH = "2026-09-30"
SOURCE = "https://freeto-x.it/metodi-di-pagamento/pagamento-con-carta-di-credito/"
PROMO_SOURCE = "https://freeto-x.it/promo/"


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def connector_kind(evse):
    connectors=[c for c in (evse.get('connectors') or []) if isinstance(c,dict)]
    types={str(c.get('powerType') or '').upper() for c in connectors}
    if any(t.startswith('AC') for t in types): return 'AC'
    if any(t.startswith('DC') for t in types): return 'DC'
    return None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pun',default='data/national/pun_italy_national.json.gz')
    ap.add_argument('--out',default='data/national/freetox_direct_stations_italy.json.gz')
    ap.add_argument('--report',default='data/reports/freetox_italy_pun_direct_report.json')
    a=ap.parse_args()
    with gzip.open(a.pun,'rt',encoding='utf-8') as f: pun=json.load(f)

    rows=[]; blocked=Counter(); classes=Counter()
    for e in pun.get('evses',[]):
        if str(e.get('partyId') or '').upper()!=PARTY: continue
        kind=connector_kind(e)
        power=e.get('maxPowerKw')
        try: power=float(power) if power is not None else None
        except Exception: power=None
        tariff=None; reason=None; tariff_class=None
        if kind=='AC':
            tariff_class='AC'
            tariff={'pricingType':'flat','energyEurPerKwh':AC_PRICE,'validFrom':None,'validThrough':None,'source':SOURCE,'rankable':True}
        elif kind=='DC' and power is not None and power <= 64:
            tariff_class='DC_PROMO_LE64'
            tariff={'pricingType':'flat','energyEurPerKwh':PROMO_DC_PRICE,'validFrom':PROMO_FROM,'validThrough':PROMO_THROUGH,'source':PROMO_SOURCE,'paymentMethod':'credit_or_debit_card','rankable':True}
        elif kind=='DC':
            tariff_class='DC_GT64_UNRESOLVED'
            reason='dc_vs_hpc_threshold_not_officially_validated'
        else:
            tariff_class='UNKNOWN'
            reason='power_type_unresolved'
        classes[tariff_class]+=1
        if reason: blocked[reason]+=1
        rows.append({
            'evseId':e.get('evseId'),'stationId':e.get('stationId'),'partyId':PARTY,
            'operator':e.get('operator'),'operationalState':e.get('operationalState'),
            'sourceStatus':e.get('sourceStatus'),'maxPowerKw':power,'tariffClass':tariff_class,
            'directTariff':tariff,'rankableDirectTariff':bool(tariff),'blockingReason':reason,
        })

    if len(rows)<500: raise RuntimeError(f'Unexpectedly small PUN F2X inventory: {len(rows)}')
    rankable=sum(1 for x in rows if x['rankableDirectTariff'])
    payload={
        'schemaVersion':1,'dataset':'freetox-direct-italy-candidate','generatedAt':now_iso(),
        'country':'IT','operator':'Free To X','punPartyId':PARTY,
        'policy':{
            'cardPaymentAcEurPerKwh':AC_PRICE,
            'cardPaymentDcEurPerKwh':0.65,
            'cardPaymentHpcEurPerKwh':0.79,
            'promoDcLe64EurPerKwh':PROMO_DC_PRICE,
            'promoValidFrom':PROMO_FROM,'promoValidThrough':PROMO_THROUGH,
            'dcAbove64FailClosedUntilDcHpcThresholdValidated':True,
            'sources':[SOURCE,PROMO_SOURCE],
        },
        'counts':{
            'punF2xEvseCount':len(rows),'rankableDirectEvseCount':rankable,
            'rankableCoveragePct':round(100*rankable/len(rows),2),
            'tariffClassCounts':dict(sorted(classes.items())),
            'blockedReasons':dict(sorted(blocked.items())),
        },
        'evses':rows,
    }
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n'
    out.write_bytes(gzip.compress(raw.encode(),compresslevel=9,mtime=0))
    report={'generatedAt':payload['generatedAt'],'policy':payload['policy'],'counts':payload['counts']}
    rp=Path(a.report); rp.parent.mkdir(parents=True,exist_ok=True); rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
