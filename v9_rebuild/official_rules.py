#!/usr/bin/env python3
"""Isolated execution of preserved single-script official tariff rules."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

RULES = {
    "atlante": ("Atlante", "atlante-official-france", 4),
    "driveco": ("DRIVECO", "driveco-official-france", 6),
    "eborn": ("eborn", "eborn-official-france-regional", 3),
    "electric55": ("Electric 55 Charging (E55C)", "electric55-official-france", 3),
    "etotem": ("e-Totem", "etotem-official-france", 5),
    "fastned": ("Fastned", "fastned-official-france", 7),
    "freshmile": ("Freshmile", "freshmile-official-france", 7),
    "ionity": ("IONITY", "ionity-official-france", 6),
}


def paths(source: str) -> tuple[Path, Path, Path]:
    if source not in RULES:
        raise ValueError(f"Unsupported preserved official rule: {source}")
    return (Path(f"data/operator_direct/{source}_official_france.json"),
            Path(f"reports/{source}/latest_summary.md"), Path(f"out/{source}"))


def validate_output(out: Path, source: str) -> dict:
    output, report, _ = paths(source)
    payload = json.loads((out / output).read_text(encoding="utf-8"))
    operator, dataset, expected_evidence = RULES[source]
    evidence = payload.get("sourceEvidence") or {}
    sources = evidence.get("sources") or []
    if (payload.get("schemaVersion") != ("1.0.1" if source == "freshmile" else "1.0.0") or payload.get("dataset") != dataset
            or payload.get("operator") != operator or payload.get("country") != "FR"
            or payload.get("publicationStatus") != "candidate_validated_source"
            or (source != "etotem" and evidence.get("officialOnly") is not True)
            or len(sources) != expected_evidence
            or len({row.get("key") for row in sources}) != expected_evidence
            or any(row.get("httpStatus") != 200 for row in sources if source != "etotem" or row.get("key") != "saintLouis")
            or not isinstance(payload.get("operatorDirect"), dict)
            or not (out / report).is_file() or not (out / report).read_text(encoding="utf-8").strip()):
        raise ValueError(f"{source} official technical contract invalid")
    fingerprint = evidence.get("relevantTariffFingerprintSha256")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
        raise ValueError(f"{source} official fingerprint invalid")
    if source == "etotem":
        if (payload.get("classification", {}).get("stationOrNetworkLevelLookupRequiredForExactCpoDirect") is not True
                or payload["operatorDirect"].get("nationalLibertyOffer", {}).get("exactCurrentNationwideEurPerKwh") is not None
                or payload.get("mobilityProviderLayer", {}).get("classification") != "eTotem_eMSP_and_partner_network_access"
                or evidence.get("firstPartyCurrentSources") != ["users", "mobility", "home"]):
            raise ValueError("e-Totem official tariff scope invalid")
    elif source == "atlante":
        direct = payload["operatorDirect"]
        if (payload.get("classification", {}).get("stationLevelPriceLookupRequiredWithoutSubscription") is not True
                or direct.get("withoutAtlanteGo", {}).get("singleNationalPrice") is not None
                or direct.get("atlanteGo", {}).get("eligibleCustomerType") != "private_individuals"
                or payload.get("roaming", {}).get("operatorDirect") is not False
                or payload.get("loyalty", {}).get("mustNotBeNetterIntoBaseEnergyTariff") is not True):
            raise ValueError("Atlante official channel or scope contract invalid")
    elif source == "driveco":
        if (payload.get("classification", {}).get("stationLevelPriceLookupRequiredForExactSimulation") is not True
                or payload["operatorDirect"].get("application", {}).get("exactStationPriceShownBeforeCharge") is not True
                or payload.get("roaming", {}).get("operatorDirect") is not False
                or payload.get("publishedReferencePricing", {}).get("mustNotReplaceExactStationPrice") is not True
                or not isinstance(payload.get("inventory", {}).get("samples"), list)):
            raise ValueError("DRIVECO official station-specific scope invalid")
    elif source == "eborn":
        direct = payload["operatorDirect"]
        if (payload.get("classification", {}).get("tariffDependsOnPowerAndCustomerProfile") is not True
                or direct.get("subscriptionPlans", {}).get("forfait", {}).get("includedKwhPerMonth") is None
                or payload.get("fees", {}).get("postCharge", {}).get("graceMinutesAfterChargeEnd") is None
                or payload.get("roaming", {}).get("incomingThirdPartyBadge", {}).get("operatorDirect") is not False):
            raise ValueError("eborn official power, subscription or roaming scope invalid")
    elif source == "electric55":
        direct = payload["operatorDirect"].get("adHocBankCard", {})
        if (payload.get("classification", {}).get("exactAdHocConsumerPriceLookupRequired") is not True
                or direct.get("priceDisplayedBeforePayment") is not True
                or direct.get("nationalConsumerEurPerKwh") is not None
                or payload.get("indicativeWholesaleTariffsToMobilityOperators", {}).get("consumerTariff") is not False
                or payload.get("inventory", {}).get("nationalStationDatabaseBuiltByThisValidator") is not False):
            raise ValueError("E55C wholesale or exact consumer price scope invalid")
    elif source == "freshmile":
        direct = payload["operatorDirect"].get("freshmileManagedStations", {})
        if (payload.get("classification", {}).get("freshmileActsAsCpoAndEmsp") is not True
                or direct.get("nationalEurPerKwh") is not None
                or direct.get("exactPriceLookupRequired") is not True
                or payload.get("mobilityProvider", {}).get("incomingRoamingOnFreshmileCpo", {}).get("operatorDirect") is not False
                or payload.get("fees", {}).get("connectionTime", {}).get("exactStationLookupRequired") is not True):
            raise ValueError("Freshmile official CPO/eMSP or station price scope invalid")
    elif source == "fastned":
        direct = payload["operatorDirect"]
        if (payload.get("classification", {}).get("singleNationalOperatorTariff") is not True
                or len(payload.get("stationValidationSamples") or []) != 4
                or direct.get("standard", {}).get("currency") != "EUR"
                or payload.get("roaming", {}).get("classification") != "third_party_eMSP"):
            raise ValueError("Fastned official channel or station contract invalid")
    else:
        direct = payload["operatorDirect"]
        if (payload.get("classification", {}).get("stationLevelPriceLookupRequiredForExactSimulation") is not True
                or direct.get("pricingRule", {}).get("publishedValuesAreMinimums") is not True
                or direct.get("pricingRule", {}).get("stationPriceMayBeHigher") is not True
                or payload.get("roaming", {}).get("operatorDirect") is not False):
            raise ValueError("IONITY official price scope invalid")
    return payload


def run(out: Path, source: str, *, runner=subprocess.run) -> None:
    output, report, temp = paths(source)
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Official rule output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(ROOT / f"scripts/{source}_official.py"), "--out", str(out / temp)],
                    cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError(f"Historical {source} official method failed")
    (out / output).parent.mkdir(parents=True, exist_ok=True)
    (out / report).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / temp / f"{source}_official_france.json", out / output)
    shutil.copy2(out / temp / "SUMMARY.md", out / report)
    shutil.rmtree(out / "out")
    validate_output(out, source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=sorted(RULES), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.source)


if __name__ == "__main__":
    main()
