#!/usr/bin/env python3
"""Validate and publish e-Vadea France tariffs from the official image-only table."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def nums(line: str) -> list[float]:
    vals = []
    for token in re.findall(r"(?<!\d)(\d+(?:[,.]\d+)?)(?!\d)", line):
        vals.append(float(token.replace(",", ".")))
    return vals


def find_line(lines: list[str], *needles: str) -> str:
    needles = tuple(norm(x) for x in needles)
    for line in lines:
        n = norm(line)
        if all(x in n for x in needles):
            return line
    raise RuntimeError(f"required OCR tariff row missing: {needles}")


def parse_row(line: str, power_tokens: tuple[float, ...]) -> tuple[float, float]:
    values = nums(line)
    remaining = values[:]
    for token in power_tokens:
        if token in remaining:
            remaining.remove(token)
    if 15.0 in remaining:
        remaining.remove(15.0)
    remaining = [x for x in remaining if 0.01 <= x <= 20]
    if len(remaining) < 2:
        raise RuntimeError(f"unable to parse e-Vadea row: {line!r}; values={values}")
    return remaining[0], remaining[1]


def run_discovery(out: Path) -> dict:
    discovery_out = out / "discovery"
    discovery_out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "scripts/evadea_tariff_image_discovery.py", "--out", str(discovery_out)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"e-Vadea discovery failed: {proc.stderr[-1200:]}")
    return json.loads((discovery_out / "discovery.json").read_text(encoding="utf-8"))


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
        raise RuntimeError("incomplete official tariff-image evidence")

    a1 = parse_row(find_line(lines, "moins de 100kw"), (100.0,))
    a2 = parse_row(find_line(lines, "100kw et plus"), (100.0,))
    h1 = parse_row(find_line(lines, "moins de 30kw"), (30.0,))
    h2 = parse_row(find_line(lines, "30kw", "60kw"), (30.0, 60.0))
    h3 = parse_row(find_line(lines, "60kw et plus"), (60.0,))

    observed = {
        "autorouteLt100": list(a1),
        "autorouteGe100": list(a2),
        "horsAutorouteLt30": list(h1),
        "horsAutoroute30To60": list(h2),
        "horsAutorouteGe60": list(h3),
    }
    expected = {
        "autorouteLt100": [0.48, 6.0],
        "autorouteGe100": [0.62, 6.0],
        "horsAutorouteLt30": [0.40, 0.5],
        "horsAutoroute30To60": [0.48, 5.0],
        "horsAutorouteGe60": [0.58, 5.0],
    }
    if observed != expected:
        raise RuntimeError(f"e-Vadea tariff grid changed or OCR mismatch: {observed}")

    all_text = norm(" ".join(lines))
    for evidence in ("sans consommation d'energie", "5 premieres minutes", "tout kwh entame est du"):
        if evidence not in all_text:
            raise RuntimeError(f"official tariff-table rule missing after OCR: {evidence}")

    supporting = d.get("supportingHtmlEvidence") or {}
    sources = {x.get("key"): x.get("url") for x in (d.get("sources") or []) if isinstance(x, dict)}

    core = {
        "classification": {
            "singleFlatNationalTariff": False,
            "tariffGridByRoadContextAndPower": True,
            "stationContextLookupRequiredForExactSimulation": True,
        },
        "operatorDirect": {
            "motorway": {
                "lessThan100Kw": {"eurPerKwh": a1[0]},
                "from100Kw": {"eurPerKwh": a2[0]},
            },
            "offMotorway": {
                "lessThan30Kw": {"eurPerKwh": h1[0]},
                "from30To60Kw": {"eurPerKwh": h2[0]},
                "from60Kw": {"eurPerKwh": h3[0]},
            },
            "paymentMethods": ["e-Vadea app", "bank card", "QR code"],
            "bankCardPreauthorizationEur": 49.0,
            "bankCardPreauthorizationEvidence": "current official FAQ; browser-visible fact separately verified from OCR tariff table",
        },
        "fees": {
            "occupancy": {
                "trigger": "vehicle remains connected without energy consumption",
                "gracePeriodMinutes": 5,
                "billingBlockMinutes": 15,
                "startedBlockCharged": True,
                "motorway": {
                    "lessThan100KwEurPerBlock": a1[1],
                    "from100KwEurPerBlock": a2[1],
                },
                "offMotorway": {
                    "lessThan30KwEurPerBlock": h1[1],
                    "from30To60KwEurPerBlock": h2[1],
                    "from60KwEurPerBlock": h3[1],
                },
            },
            "parking": {"status": "local_rules_may_apply_separately"},
        },
        "energyBilling": {"startedKwhCharged": True},
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
            "sources": sources,
        },
    }
    core["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(
        json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
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
            "Exact direct price depends on motorway/off-motorway context and charger power band.",
            "Occupancy fees start only while connected without energy consumption, after 5 free minutes.",
            "Third-party mobility-provider tariffs are roaming/eMSP prices and can differ.",
            "The official static inventory is stale and is not live availability.",
        ],
    }
    (out / "evadea_official_france.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = f"""# e-Vadea France official check

- Motorway: **<100 kW {a1[0]:.2f} EUR/kWh; >=100 kW {a2[0]:.2f} EUR/kWh**.
- Off-motorway: **<30 kW {h1[0]:.2f}; 30-60 kW {h2[0]:.2f}; >=60 kW {h3[0]:.2f} EUR/kWh**.
- Occupancy: **5 min free**, then per started **15 min** block.
- Motorway occupancy: **{a1[1]:g} EUR/15 min**.
- Off-motorway occupancy: **{h1[1]:g} / {h2[1]:g} / {h3[1]:g} EUR/15 min**.
- Bank-card preauthorization: **49 EUR** (official FAQ).
- Third-party mobility badge: **eMSP tariff may differ**.
- Tariff image SHA-256: `{image.get('sha256')}`.
- Fingerprint: `{core['sourceEvidence']['relevantTariffFingerprintSha256']}`.
"""
    (out / "SUMMARY.md").write_text(summary)
    print(summary)


if __name__ == "__main__":
    main()
