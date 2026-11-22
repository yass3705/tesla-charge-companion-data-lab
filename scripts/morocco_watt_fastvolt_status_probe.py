#!/usr/bin/env python3
"""Read-only diagnostic cross-check for the public WATT.ma FastVolt map status.

This probe intentionally performs one anonymous GET to the public map only. It
never treats WATT.ma as authority for physical CPO attribution, direct tariffs,
or native charger status.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path

URL = "https://map.watt.ma/"
OUT = Path("artifacts/morocco-watt-fastvolt-status/summary.json")
STATION = "FastVolt Morocco Mall"

req = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "TeslaChargeCompanion-PublicReadOnlyProbe/1.0",
        "Accept": "text/html",
    },
)
with urllib.request.urlopen(req, timeout=20) as response:
    raw = response.read(2_000_000).decode("utf-8", errors="replace")
    http_status = response.status

text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
text = " ".join(text.split())

pattern = re.compile(
    r"FastVolt\s+Morocco\s+Mall\s+(Available|In\s+Use|Offline)\s+Casablanca\s+Power\s+(\d+)\s*kW\s*[·x×]?\s*(\d+)\s+Connectors",
    re.IGNORECASE,
)
match = pattern.search(text)
if not match:
    # Fail closed: do not infer a status from nearby generic legend text.
    raise SystemExit("FastVolt Morocco Mall status tuple not found in public map response")

raw_status = " ".join(match.group(1).split())
status = {
    "available": "Available",
    "in use": "Occupied",
    "offline": "Offline",
}[raw_status.lower()]

observed_at = dt.datetime.now(dt.timezone.utc).isoformat()
production_allowed = status in {"Available", "Occupied", "Charging"}

out = {
    "schema_version": 1,
    "observed_at": observed_at,
    "source_url": URL,
    "http_status": http_status,
    "policy": {
        "read_only": True,
        "http_method": "GET",
        "single_public_request": True,
        "credentials_used": False,
        "cookies_used": False,
        "query_parameters_used": False,
        "station_ids_used": False,
        "secondary_aggregation_evidence_only": True,
        "do_not_infer_or_overwrite_cpo": True,
        "do_not_infer_direct_tariff": True,
        "do_not_label_as_native_status": True,
        "underlying_status_source_timestamp_available": False,
        "evone_production_status_allowlist": ["Available", "Occupied", "Charging"],
        "evone_diagnostic_only_statuses": ["Faulted", "Offline", "Unknown", "Unavailable"],
    },
    "observation": {
        "station_name": STATION,
        "cpo_operator": "retain independently validated FastVolt/Afrimobility attribution; WATT.ma is not the attribution authority",
        "site_brand": "Morocco Mall",
        "operator_label_on_source": "Fastvolt",
        "app_source_access_network": "WATT.ma public map / OCPI aggregation surface",
        "tariff_channel": None,
        "status_source": "WATT.ma public map / OCPI aggregation",
        "status": status,
        "source_status_label": raw_status,
        "power_kw": int(match.group(2)),
        "connector_count": int(match.group(3)),
        "status_freshness": "retrieval time known; upstream CPO observation time not exposed",
        "production_role": "diagnostic_crosscheck_only",
        "would_pass_evone_status_allowlist_if_the_source_were_evone": production_allowed,
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(
    json.dumps(
        {
            "http_status": http_status,
            "station": STATION,
            "status": status,
            "power_kw": int(match.group(2)),
            "connector_count": int(match.group(3)),
            "production_role": "diagnostic_crosscheck_only",
        },
        ensure_ascii=False,
    )
)
