#!/usr/bin/env python3
"""Apply values verified from Enel's live rendered tariff cards.

The Enel page contains stale expanded HTML blocks alongside the current interactive
cards. This script makes the final candidate follow the values actually rendered
by the current Giorno/Notte cards, which were probed with Selenium on 2026-08-29.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

CANDIDATE = Path("data/national/enel_direct_stations_italy_final_candidate.json.gz")
REPORT = Path("data/reports/enel_italy_finalization_report.json")

LIVE_BASIC = {
    "AC": {"day": 0.67, "night": 0.58},
    "DC": {"day": 0.75, "night": 0.64},
    "HPC": {"day": 0.82, "night": 0.82},
}
LIVE_EXPLORER = {
    "AC": {"day": 0.57, "night": 0.48},
    "DC": {"day": 0.65, "night": 0.54},
    "HPC": {"day": 0.72, "night": 0.72},
}
LIVE_SUPER = {
    cls: {slot: round(price + 0.05, 2) for slot, price in slots.items()}
    for cls, slots in LIVE_EXPLORER.items()
}


def read_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def write_gz(path: Path, payload):
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9))


def main():
    payload = read_gz(CANDIDATE)
    policy = payload["operatorTariffPolicy"]
    policy["basicEurPerKwh"] = LIVE_BASIC
    policy["liveRenderedCardEvidence"] = {
        "verifiedAt": "2026-08-29",
        "method": "selenium_click_giorno_notte_on_current_enel_tariff_page",
        "url": "https://www.enel.it/it-it/mobilita-elettrica/tariffe-abbonamenti",
        "basicEurPerKwh": LIVE_BASIC,
        "plugAndGoSuperEurPerKwh": LIVE_SUPER,
        "plugAndGoExplorerEurPerKwh": LIVE_EXPLORER,
        "note": "current interactive cards take precedence over stale expanded promotional blocks in page HTML",
    }
    # Keep source metadata explicit about the live-card precedence.
    policy.setdefault("sources", []).insert(0, {
        "kind": "live_rendered_tariff_cards",
        "url": "https://www.enel.it/it-it/mobilita-elettrica/tariffe-abbonamenti",
        "evidence": "Giorno/Notte cards rendered 2026-08-29: Basic AC 0.67/0.58, DC 0.75/0.64, HPC 0.82/0.82; Explorer -0.10; Super -0.05",
    })
    write_gz(CANDIDATE, payload)

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["basicEurPerKwh"] = LIVE_BASIC
    report["liveRenderedCardEvidence"] = policy["liveRenderedCardEvidence"]
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(policy["liveRenderedCardEvidence"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
