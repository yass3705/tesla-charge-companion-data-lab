#!/usr/bin/env python3
"""Cross-check Shell Melloussa using two public, read-only secondary sources.

This diagnostic intentionally does not promote CPO, tariff, or live-status data.
It compares the already-committed WATT corroboration record with the exact
public Atlas Recharge station page and confirms that the WATT listing remains
present. Raw HTML is never written to disk or uploaded.
"""
from __future__ import annotations

import ast
import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path

WATT_URL = "https://map.watt.ma/operators/shell-vivo/"
ATLAS_URL = "https://atlasrecharge.com/bornes/ghedir-eddefla/shell-melloussa-163"
EXISTING_WATT_PROBE = Path("scripts/morocco_shell_vivo_watt_public_page_probe.py")
OUT = Path("artifacts/morocco-shell-melloussa-crosscheck/summary.json")
USER_AGENT = "TeslaChargeCompanion-PublicReadOnlyProbe/1.0"


def fetch_text(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def visible_text(raw: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = text.replace("\xa0", " ")
    return " ".join(text.split())


def committed_watt_melloussa_record() -> dict:
    tree = ast.parse(EXISTING_WATT_PROBE.read_text(encoding="utf-8"))
    expected = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "EXPECTED":
                    expected = ast.literal_eval(node.value)
                    break
        if expected is not None:
            break
    if not isinstance(expected, list):
        raise RuntimeError("Unable to recover committed WATT EXPECTED list")
    rows = [row for row in expected if "mellous" in str(row.get("name", "")).casefold()]
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one committed Melloussa row, got {len(rows)}")
    return rows[0]


def main() -> None:
    watt_record = committed_watt_melloussa_record()
    watt_status, watt_raw = fetch_text(WATT_URL)
    atlas_status, atlas_raw = fetch_text(ATLAS_URL)
    watt_text = visible_text(watt_raw)
    atlas_text = visible_text(atlas_raw)

    watt_name_found = str(watt_record["name"]).casefold() in watt_text.casefold()
    atlas_observed = {
        "name_found": "shell melloussa" in atlas_text.casefold(),
        "power_50_kw_found": re.search(r"\b50\s*kW\b", atlas_text, flags=re.I) is not None,
        "two_points_found": re.search(r"\b2\s+points?\b", atlas_text, flags=re.I) is not None,
        "ccs_found": "ccs" in atlas_text.casefold(),
        "type_2_found": re.search(r"\btype\s*2\b", atlas_text, flags=re.I) is not None,
        "free_access_claim_found": "gratuit" in atlas_text.casefold(),
        "operator_unresolved_marker_found": re.search(
            r"op[ée]rateur\s*[—–-]\s*acc[èe]s", atlas_text, flags=re.I
        )
        is not None,
    }

    if watt_status != 200 or atlas_status != 200:
        raise RuntimeError(f"Unexpected HTTP status: WATT={watt_status}, Atlas={atlas_status}")
    if not watt_name_found:
        raise RuntimeError("Current WATT public page no longer contains the committed Melloussa listing")
    required_atlas = [
        "name_found",
        "power_50_kw_found",
        "two_points_found",
        "ccs_found",
        "type_2_found",
    ]
    missing = [key for key in required_atlas if not atlas_observed[key]]
    if missing:
        raise RuntimeError(f"Atlas Melloussa page missing expected public markers: {missing}")

    output = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "read_only": True,
            "http_method": "GET",
            "credentials_used": False,
            "cookies_used": False,
            "raw_html_persisted": False,
            "secondary_public_evidence_only": True,
            "do_not_infer_native_cpo": True,
            "do_not_promote_tariff": True,
            "do_not_promote_live_status": True,
        },
        "site": {
            "canonical_diagnostic_key": "shell-melloussa",
            "site_brand": "Shell",
            "cpo_operator": "unresolved",
            "tariff_channel": None,
            "status_source": None,
            "production_role": "diagnostic_conflict_only",
        },
        "sources": {
            "watt": {
                "url": WATT_URL,
                "http_status": watt_status,
                "role": "app_source/access_network secondary corroboration",
                "listing_present_now": watt_name_found,
                "committed_record": {
                    "name": watt_record["name"],
                    "power_kw": watt_record["power_kw"],
                    "connector_count": watt_record["connectors"],
                },
            },
            "atlas_recharge": {
                "url": ATLAS_URL,
                "http_status": atlas_status,
                "role": "independent community directory secondary corroboration",
                "observed": atlas_observed,
                "reported_record": {
                    "name": "Shell Melloussa",
                    "power_kw": 50,
                    "connector_count": 2,
                    "connector_types": ["CCS", "Type 2"],
                    "access_claim": "free",
                    "operator_attribution": "unresolved",
                },
            },
        },
        "conflict": {
            "power_kw": {"watt_committed": watt_record["power_kw"], "atlas_reported": 50},
            "connector_count": {"watt_committed": watt_record["connectors"], "atlas_reported": 2},
            "operator_attribution_resolved": False,
            "assessment": (
                "Two independent public secondary sources describe the same Shell-branded Melloussa site "
                "with incompatible power/connector details. Neither source proves the physical CPO, a "
                "native tariff channel, or a native live-status source; keep the site diagnostic-only."
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "watt": f"{watt_record['power_kw']}kW/{watt_record['connectors']}",
                "atlas": "50kW/2",
                "operator": "unresolved",
                "production_role": "diagnostic_conflict_only",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
