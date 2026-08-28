#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from urllib import request, error

# Bounded, evidenced application routes plus a small set of conventional public
# API-metadata paths on the already validated FastVolt mobile authority. A single
# deliberately nonexistent sentinel path is included only to distinguish route
# resolution from host-wide authentication middleware. This is not a crawler or
# path brute-forcer.
TARGETS = [
    ("app.api.fastvolt.bornerecharge.ma", "/app/charging_stations/", "evidenced_app_route"),
    ("app.api.fastvolt.bornerecharge.ma", "/user/get_charging_station_details/", "evidenced_app_route"),
    ("mobile.ev.fastvolt.ma", "/app/charging_stations/", "evidenced_app_route"),
    ("mobile.ev.fastvolt.ma", "/user/get_charging_station_details/", "evidenced_app_route"),
    ("mobile.ev.fastvolt.ma", "/openapi.json", "conventional_public_metadata"),
    ("mobile.ev.fastvolt.ma", "/swagger.json", "conventional_public_metadata"),
    ("mobile.ev.fastvolt.ma", "/docs", "conventional_public_metadata"),
    ("mobile.ev.fastvolt.ma", "/redoc", "conventional_public_metadata"),
    ("mobile.ev.fastvolt.ma", "/robots.txt", "conventional_public_metadata"),
    ("mobile.ev.fastvolt.ma", "/api/schema/", "conventional_public_metadata"),
    ("mobile.ev.fastvolt.ma", "/__tcc_readonly_nonexistent_sentinel__", "nonexistent_control"),
]


def safe_get(host, path, probe_class):
    url = f"https://{host}{path}"
    req = request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "tcc-data-lab-public-readonly/1.0",
            "Accept": "application/json,text/plain,text/html,*/*",
        },
    )
    result = {
        "host": host,
        "path": path,
        "probe_class": probe_class,
        "method": "GET",
        "url": url,
    }
    try:
        with request.urlopen(req, timeout=15) as resp:
            body = resp.read(65536)
            result.update(
                {
                    "status": resp.status,
                    "content_type": resp.headers.get("content-type"),
                    "response_length_sampled": len(body),
                }
            )
    except error.HTTPError as exc:
        body = exc.read(65536)
        result.update(
            {
                "status": exc.code,
                "content_type": exc.headers.get("content-type"),
                "response_length_sampled": len(body),
            }
        )
    except Exception as exc:
        result.update(
            {
                "status": None,
                "error_class": type(exc).__name__,
                "error": "transport_or_resolution_error",
            }
        )
        return result

    ctype = (result.get("content_type") or "").lower()
    if "json" in ctype:
        try:
            data = json.loads(body.decode("utf-8", "replace"))
            if isinstance(data, dict):
                result["top_level_keys"] = sorted(str(k) for k in data.keys())[:40]
                generic = {}
                for key in ("message", "detail", "error", "errors", "openapi", "swagger", "paths", "components"):
                    if key in data:
                        val = data[key]
                        if isinstance(val, dict):
                            generic[key + "_keys"] = sorted(str(k) for k in val.keys())[:30]
                        elif isinstance(val, list):
                            generic[key + "_type"] = "list"
                        else:
                            generic[key + "_type"] = type(val).__name__
                if generic:
                    result["generic_schema_shape"] = generic
            elif isinstance(data, list):
                result["json_shape"] = "list"
                result["item_count"] = len(data)
                if data and isinstance(data[0], dict):
                    result["first_item_keys"] = sorted(str(k) for k in data[0].keys())[:40]
        except Exception:
            result["json_parse"] = "failed"
    return result


def main():
    probes = [safe_get(h, p, c) for h, p, c in TARGETS]
    mobile = [p for p in probes if p["host"] == "mobile.ev.fastvolt.ma"]
    sentinel = next((p for p in mobile if p["probe_class"] == "nonexistent_control"), None)
    same_as_sentinel = []
    if sentinel and sentinel.get("status") is not None:
        sig = (sentinel.get("status"), sentinel.get("content_type"), sentinel.get("response_length_sampled"))
        same_as_sentinel = [
            p["path"] for p in mobile
            if p["probe_class"] != "nonexistent_control"
            and (p.get("status"), p.get("content_type"), p.get("response_length_sampled")) == sig
        ]

    out = {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "MA",
        "scope": "FastVolt/EVPlug evidenced GET routes plus bounded public metadata and one nonexistent control",
        "policy": {
            "read_only": True,
            "get_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_parameters": True,
            "no_mutations": True,
            "no_business_or_organisation_guessing": True,
            "no_path_bruteforce_or_crawling": True,
            "single_nonexistent_control_only": True,
            "raw_response_body_persisted": False,
            "only_status_content_type_and_schema_shape_persisted": True,
        },
        "modeling": {
            "cpo_operator": "FastVolt / Afrimobility",
            "site_brand": None,
            "app_source_access_network": "FastVolt",
            "tariff_channel": "FastVolt direct",
            "status_source": None,
            "evplug_role": "technical/platform/eMSP evidence only; not CPO attribution",
        },
        "route_resolution_control": {
            "sentinel_path": sentinel.get("path") if sentinel else None,
            "sentinel_status": sentinel.get("status") if sentinel else None,
            "paths_with_identical_status_content_type_length": same_as_sentinel,
            "interpretation": (
                "If evidenced routes and a deliberately nonexistent path have the same HTTP/content signature, "
                "the anonymous response is consistent with host-wide middleware and does not independently prove route resolution."
            ),
        },
        "probes": probes,
    }
    with open(
        "reports/morocco/fastvolt/latest-bornerecharge-evidenced-routes.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
