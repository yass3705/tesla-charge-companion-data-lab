#!/usr/bin/env python3
"""Run four preserved Load Motion tenants and compile their direct offers off checkout."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
from pathlib import Path

from v9_rebuild.orchestrator import ROOT

TENANTS = ("yes55", "loadstations", "reveo", "mobisdec")
SECRETS = {"yes55": "YES55_PASS", "loadstations": "LOADSTATIONS_PASS", "reveo": "REVEO_PASS", "mobisdec": "MOBISDEC_PASS"}
COLLECT = Path("scripts/loadmotion/extract_loadmotion_france.mjs")
COMPILE = Path("scripts/loadmotion/compile_loadmotion_v9_offers.mjs")
CURRENT = Path("data/loadmotion/france/current")
OUTPUT = Path("v9-production-runtime/data/v9/france-loadmotion-offers.json")
KNOWN_DIMENSIONS = {"energy", "flatFee", "chargingTime", "sessionTime", "parkingTime"}


def validate_output(out: Path) -> dict:
    snapshots = {}
    for tenant in TENANTS:
        with gzip.open(out / CURRENT / f"{tenant}.json.gz", "rt", encoding="utf-8") as handle:
            data = json.load(handle)
        summary = data.get("summary") or {}
        groups = {key: data.get(key) or [] for key in ("tarifs", "noTariff", "empty", "erreursPersistantes")}
        if (data.get("tenant") != tenant or data.get("schemaVersion") != 1
                or groups["erreursPersistantes"]
                or summary.get("stations") is None
                or summary.get("connecteursTestes") != sum(len(rows) for rows in groups.values())
                or summary.get("tarifs") != len(groups["tarifs"])
                or summary.get("erreursPersistantes") != 0):
            raise ValueError(f"Load Motion {tenant} collection incomplete")
        identities = [(row.get("station"), str(row.get("connector"))) for rows in groups.values() for row in rows]
        if any(not station or connector == "None" for station, connector in identities) or len(identities) != len(set(identities)):
            raise ValueError(f"Load Motion {tenant} station/connector identity invalid")
        for row in groups["tarifs"]:
            for definition in row.get("definitions") or []:
                dims = definition.get("dimensions") or {}
                unknown = {name for name, value in dims.items() if isinstance(value, dict) and value.get("active") is True} - KNOWN_DIMENSIONS
                if unknown:
                    raise ValueError(f"Load Motion {tenant} unsupported active component: {sorted(unknown)}")
                for name in KNOWN_DIMENSIONS & dims.keys():
                    value = dims[name]
                    if isinstance(value, dict) and value.get("active") is True and not isinstance(value.get("price"), (int, float)):
                        raise ValueError(f"Load Motion {tenant} missing active component price: {name}")
        snapshots[tenant] = data
    offers = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    if (offers.get("schemaVersion") != 1 or offers.get("country") != "FR"
            or offers.get("mode") != "verified_loadmotion_direct"
            or offers.get("subscriptionOffers") != []
            or not isinstance(offers.get("directOffers"), list)):
        raise ValueError("Load Motion compiled schema invalid")
    ids = set()
    for offer in offers["directOffers"]:
        oid = offer.get("id")
        tenant = (offer.get("metadata") or {}).get("tenant")
        if (not oid or oid in ids or tenant not in TENANTS or offer.get("verifiedScope") not in
                {"exact_evse", "territorial_network_power", "operator_or_network_power_time"}
                or not isinstance((offer.get("pricing") or {}).get("rules"), list)
                or "No Tariff" in json.dumps(offer)):
            raise ValueError("Load Motion compiled offer scope invalid")
        ids.add(oid)
        if offer.get("verifiedScope") == "exact_evse":
            known = {row["station"] for row in snapshots[tenant].get("tarifs") or []}
            if any(eid not in known for eid in offer.get("evseIds") or []):
                raise ValueError("Load Motion exact EVSE offer scope invalid")
    return offers


def run(out: Path, *, runner=subprocess.run, fixture_preload: Path | None = None) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Load Motion must run outside checkout")
    for script in (COLLECT, COMPILE):
        target = out / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / script, target)
    for tenant in TENANTS:
        env = dict(os.environ)
        env["LOADMOTION_PASS"] = env.get(SECRETS[tenant], "")
        if fixture_preload:
            env["NODE_OPTIONS"] = f"--import={fixture_preload.resolve().as_uri()}"
        command = ["node", str(out / COLLECT), "--tenant", tenant, "--out", str(CURRENT / f"{tenant}.json.gz")]
        if tenant == "reveo":
            command += ["--concurrency", "2"]
        completed = runner(command, cwd=out, env=env, capture_output=True, text=True, timeout=3000)
        if completed.returncode:
            raise RuntimeError(f"Historical Load Motion tenant failed: {tenant}")
    compiled = runner(["node", str(out / COMPILE), "--current", str(CURRENT), "--out", str(OUTPUT)], cwd=out, capture_output=True, text=True, timeout=300)
    if compiled.returncode:
        raise RuntimeError("Historical Load Motion offer compiler failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
