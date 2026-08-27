#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from urllib import request, error

TARGETS = [
    ("app.api.fastvolt.bornerecharge.ma", "/app/charging_stations/"),
    ("app.api.fastvolt.bornerecharge.ma", "/user/get_charging_station_details/"),
    ("mobile.ev.fastvolt.ma", "/app/charging_stations/"),
    ("mobile.ev.fastvolt.ma", "/user/get_charging_station_details/"),
]


def safe_get(host, path):
    url = f"https://{host}{path}"
    req = request.Request(url, method="GET", headers={"User-Agent": "tcc-data-lab-public-readonly/1.0", "Accept": "application/json,text/plain,*/*"})
    result = {"host": host, "path": path, "method": "GET", "url": url}
    try:
        with request.urlopen(req, timeout=15) as resp:
            body = resp.read(65536)
            result.update({"status": resp.status, "content_type": resp.headers.get("content-type"), "response_length_sampled": len(body)})
    except error.HTTPError as exc:
        body = exc.read(65536)
        result.update({"status": exc.code, "content_type": exc.headers.get("content-type"), "response_length_sampled": len(body)})
    except Exception as exc:
        result.update({"status": None, "error_class": type(exc).__name__, "error": "transport_or_resolution_error"})
        return result

    ctype = (result.get("content_type") or "").lower()
    if "json" in ctype:
        try:
            data = json.loads(body.decode("utf-8", "replace"))
            if isinstance(data, dict):
                result["top_level_keys"] = sorted(str(k) for k in data.keys())[:40]
                # Retain only generic validation/error field names, never business/account values.
                generic = {}
                for key in ("message", "detail", "error", "errors"):
                    if key in data:
                        val = data[key]
                        if isinstance(val, dict):
                            generic[key + "_keys"] = sorted(str(k) for k in val.keys())[:30]
                        elif isinstance(val, list):
                            generic[key + "_type"] = "list"
                        else:
                            generic[key + "_type"] = type(val).__name__
                if generic:
                    result["generic_error_shape"] = generic
            elif isinstance(data, list):
                result["json_shape"] = "list"
                result["item_count"] = len(data)
                if data and isinstance(data[0], dict):
                    result["first_item_keys"] = sorted(str(k) for k in data[0].keys())[:40]
        except Exception:
            result["json_parse"] = "failed"
    return result


def main():
    probes = [safe_get(h, p) for h, p in TARGETS]
    out = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "MA",
        "scope": "FastVolt/EVPlug BorneRecharge evidenced shared GET-route validation",
        "policy": {
            "read_only": True,
            "get_only": True,
            "no_login": True,
            "no_credentials": True,
            "no_query_parameters": True,
            "no_mutations": True,
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
        "probes": probes,
    }
    with open("reports/morocco/fastvolt/latest-bornerecharge-evidenced-routes.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
