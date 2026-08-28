#!/usr/bin/env python3
"""Run the Enel Italy finalizer with the currently verified live tariff grid.

Kept as a thin wrapper so the original research finalizer remains reproducible.
The live interactive Enel cards probed on 2026-08-29 render:
- Basic: AC 0.67/0.58, DC 0.75/0.64, HPC 0.82/0.82 (day/night)
- Super: Basic minus 0.05 €/kWh
- Explorer: Basic minus 0.10 €/kWh
"""
from __future__ import annotations

import enel_italy_finalize_candidate as impl

LIVE_BASIC = {
    "AC": {"day": 0.67, "night": 0.58},
    "DC": {"day": 0.75, "night": 0.64},
    "HPC": {"day": 0.82, "night": 0.82},
}

impl.TARIFF_POLICY["basicEurPerKwh"] = LIVE_BASIC
impl.TARIFF_POLICY["sources"].insert(0, {
    "kind": "live_rendered_tariff_cards",
    "url": "https://www.enel.it/it-it/mobilita-elettrica/tariffe-abbonamenti",
    "evidence": "Selenium Giorno/Notte probe 2026-08-29: Basic AC 0.67/0.58, DC 0.75/0.64, HPC 0.82/0.82",
})

if __name__ == "__main__":
    impl.main()
