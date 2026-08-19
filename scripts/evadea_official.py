#!/usr/bin/env python3
"""Build validated e-Vadea France tariff rules from the official image-only tariff table.

The e-Vadea public tariff page currently exposes its price grid as an image. The
companion therefore reuses the dedicated OCR discovery step, then validates and
parses the current road-context/power tariff grid. Supporting FAQ/how-to facts
remain explicitly separated from the OCR-derived tariff amounts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("’", "'")).strip()


def nums(line: str) -> list[float]:
    out: list[float] = []
    for token in re.findall(r"(?<!\d)(\d+(?:[,.]\d+)?)(?!\d)", line):
        try:
            out.append(float(token.replace(",", ".")))
        except ValueError:
            pass
    return out


def find_line(lines: list[str], *needles: str) -> str:
    for line in lines:
        n = norm(line)
        if all(x in n for x in needles):
            return line
    raise RuntimeError(f"required OCR tariff row missing: {needles}")


def parse_row(line: str, expected_power_tokens: tuple[float, ...]) -> tuple[float, float]:
    values = nums(line)
    filtered = values[:]
    for p in expected_power_tokens:
        if p in filtered:
            filtered.remove(p)
    # Expected remainder is energy price + occupancy amount + 15-minute block.
    if 15.0 in filtered:
        filtered.remove(15.0)
    candidates = [v for v in filtered if 0.01 <= v <= 20]
    if len(candidates) < 2:
        raise RuntimeError(f"unable to parse tariff row: {line!r}; values={values}")
    energy = candidates[0]
    occupancy = candidates[1]
    return energy, occupancy


def run_discovery(out: Path) -> dict:
    discovery_out = out / "discovery"
    discovery_out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "scripts/evadea_tariff_image_discovery.py", "--out", str(discovery_out)],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"e-Vadea discovery failed: {proc.stderr[-1200:]}")
    p = discovery_out / "discovery.json"
    if not p.exists():
        raise RuntimeError("e-Vadea discovery did not produce discovery.json")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/evadea-final")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    d = run_discovery(out)
    if d.get("operator") != "e-Vadea" or d.get("country") != "FR":
        raise RuntimeError("unexpected discovery operator/country")

    image = d.get("tariffImage") or {}
    lines = list(image.get("tariffRelevantLines") or [])
    if not lines or len(str(image.get("sha256") or "")) != 64:
        raise RuntimeError("incomplete e-Vadea tariff image evidence")

    autoroute_lt100 = find_line(lines, "moins de 100kw")
    autoroute_ge100 = find_line(lines, "100kw et plus")
    hors_lt30 = find_line(lines, "moins de 30kw")
    hors_30_60 = find_line(lines, "30kw", "60kw")
    hors_ge60 = find_line(lines, "60kw et plus")

    a1_energy, a1_occ = parse_row(autoroute_lt100, (100.0,))
    a2_energy, a2_occ = parse_row(autoroute_ge100, (100.0,))
    h1_energy, h1_occ = parse_row(hors_lt30, (30.0,))
    h2_energy, h2_occ = parse_row(hors_30_60, (30.0, 60.0))
    h3_energy, h3_occ = parse_row(hors_ge60, (60.0,))

    # Strong semantic checks from the official OCR table.
    all_text = norm(" ".join(lines))
    if "sans consommation d'energie" not in all_text and "sans consommation d’énergie" not in all_text:
        raise RuntimeError("occupancy trigger evidence missing from official tariff table")
    if "5 premieres minutes" not in all_text:
        raise RuntimeError("5-minute occupancy grace-period evidence missing from official tariff table")
    if "tout kwh entame est du" not in all_text and "tout kwh entamé est dû" not in all_text:
        raise RuntimeError("started-kWh billing evidence missing from official tariff table")

    observed = {
        "autorouteLt100": [a1_energy, a1_occ],
        "autorouteGe100": [a2_energy, a2_occ],
        "horsAutorouteLt30": [h1_energy, h1_occ],
        "horsAutoroute30To60": [h2_energy, h2_occ],
        "horsAutorouteGe60": [h3_energy, h3_occ],
    }
    expected = {
        "autorouteLt100": [0.48, 6.0],
        "autorouteGe100": [0.62, 6.0],
        "horsAutorouteLt30": [0.40, 0.5],
        "horsAutoroute30To60": [0.48, 5.0],
        "horsAutorouteGe60": [0.58, 5.0],
    }
    if observed != expected:
        raise RuntimeError(f"e-Vadea tariff grid changed or OCR mismatch: observed={observed}")

    supporting = d.get("supportingHtmlEvidence") or {}
    source_urls = {x.get("key"): x.get("url") for x in (d.get("sources") or []) if isinstance(x, dict)}

    core = {
        "classification": {
            "singleFlatNationalTariff": False,
            "tariffGridByRoadContextAndPower": True,
            "stationContextLookupRequiredForExactSimulation": True,
            "reason": "e-Vadea publishes separate motorway and off-motorway price grids with power bands.",
        },
        "operatorDirect": {
            "motorway": {
                "lessThan100Kw": {"eurPerKwh": a1_energy},
                "from100Kw": {"eurPerKwh": a2_energy},
            },
            "offMotorway": {
                "lessThan30Kw": {"eurPerKwh": h1_energy},
                "from30To60Kw": {"eurPerKwh": h2_energy},
                "from60Kw": {"eurPerKwh": h3_energy},
            },
            "paymentMethods": ["e-Vadea app", "bank card", "QR code"],
            "bankCardPreauthorizationEur": 49.0,
            "bankCardPreauthorizationEvidence": "current official FAQ; browser-visible text may not be present in raw runner HTML",
        },
        "fees": {
            "occupancy": {
                "trigger": "vehicle remains connected without energy consumption",
                "gracePeriodMinutes": 5,
                "billingBlockMinutes": 15,
                "startedBlockCharged": True,
                "motorway": {
                    "lessThan100KwEurPerBlock": a1_occ,
                    "from100KwEurPerBlock": a2_occ,
                },
                "offMotorway": {
                    "lessThan30KwEurPerBlock": h1_occ,
                    "from30To60KwEurPerBlock": h2_occ,
                    "from60KwEurPerBlock": h3_occ,
                },
            },
            "parking": {
                "status": "local_rules_may_apply_separately",
                "note": "Official FAQ says charging spaces are reserved for EV charging and local authorities may enforce misuse.",
            },
        },
        "energyBilling": {
            "startedKwhCharged": True,
        },
        "roaming": {
            "classification": "third_party_eMSP",
            "operatorDirect": False,
            "providerMayChargeDifferentTariff": True,
            "mustNotBeClassifiedAsEVadeaDirect": True,
        },
        "inventory": d.get("inventory"),
        "sourceEvidence": {
            "officialOnly": True,
            "tariffTableImageOnly": True,
            "ocrRequired": True,
            "tariffImageUrl": image.get("url"),
            "tariffImageSha256": image.get("sha256"),
            "tariffImageBytes": image.get("bytes"),
            "supportingHtmlEvidence": supporting,
            "sources": source_urls,
        },
    }
    core["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(
        json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    result = {
        "schemaVersion": "1.0.0",
        "dataset": "evadea-official-france",
        "generatedAt": now_iso(),
        "operator": "e-Vadea",
        "country": "FR",
        **core,
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Exact direct tariff depends on whether the station is on a motorway and on the charger power band.",
            "Occupancy fees apply only while connected without energy consumption, after the first 5 free minutes.",
            "Third-party mobility-provider pricing remains eMSP roaming and can differ from e-Vadea direct pricing.",
            "The published static inventory is stale and must not be treated as live availability.",
        ],
    }

    (out / "evadea_official_france.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = f"""# e-Vadea France official check

- Tariff model: **motorway/off-motorway + charger power band**.
- Motorway: **<100 kW {a1_energy:.2f} EUR/kWh; >=100 kW {a2_energy:.2f} EUR/kWh**.
- Off-motorway: **<30 kW {h1_energy:.2f}; 30-60 kW {h2_energy:.2f}; >=60 kW {h3_energy:.2f} EUR/kWh**.
- Occupancy after charging stops: **5 min free**, then per started **15 min** block.
- Motorway occupancy: **{a1_occ:g} EUR/15 min**.
- Off-motorway occupancy: **{h1_occ:g} / {h2_occ:g} / {h3_occ:g} EUR/15 min** by power band.
- Bank-card preauthorization: **49 EUR** (official FAQ).
- Third-party mobility badge: **eMSP tariff may differ**.
- Tariff image SHA-256: `{image.get('sha256')}`.
- Fingerprint: `{core['sourceEvidence']['relevantTariffFingerprintSha256']}`.
"""
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
