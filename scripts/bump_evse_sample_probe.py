#!/usr/bin/env python3
"""Read one public Bump EVSE by its official IRVE identifier and discover its tariff group.

Uses Bump's public unauthenticated GraphQL query API. The sample EVSE identifier comes from Bump's
own official IRVE dataset. Only public station/EVSE technical fields are retained; no account,
vehicle, session, payment or personal data is queried.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_direct_inventory import DATASET_API, decode_csv, get_bytes, get_json, is_bump_operator, norm, resolve_csv_resource

ENDPOINT = "https://api.bump-charge.com/graphql"
UA = "TeslaChargeCompanionDataLab/1.0 (public EVSE tariff discovery)"
OUT_JSON = Path("reports/bump/evse_sample_probe_latest.json")
OUT_MD = Path("reports/bump/evse_sample_probe_latest.md")
TYPE_SHAPE = "kind name ofType { kind name ofType { kind name ofType { kind name } } }"
SAFE_VALUE_KEYS = (
    "id", "identifier", "reference", "name", "status", "power", "tariff", "operator",
    "currency", "type", "location", "evse", "connector", "country", "city", "postal",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def post(query: str, variables: dict[str, Any] | None = None) -> tuple[int | str, dict[str, Any]]:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(2_000_000)
            obj = json.loads(raw)
            return int(r.status), obj if isinstance(obj, dict) else {}
    except urllib.error.HTTPError as e:
        try:
            obj = json.loads(e.read(500_000))
        except Exception:
            obj = {}
        return int(e.code), obj if isinstance(obj, dict) else {}
    except Exception as e:
        return "network_error", {"errorType": type(e).__name__}


def sample_evse() -> dict[str, str]:
    dataset = get_json(DATASET_API)
    resource = resolve_csv_resource(dataset)
    rows, _ = decode_csv(get_bytes(str(resource.get("url") or resource.get("latest"))))
    candidates = [r for r in rows if is_bump_operator(r.get("nom_operateur")) and norm(r.get("id_pdc_itinerance"))]
    if not candidates:
        raise RuntimeError("No official Bump EVSE identifier found")
    # Deterministic sample for repeatability.
    candidates.sort(key=lambda r: norm(r.get("id_pdc_itinerance")))
    r = candidates[0]
    return {
        "evseIdentifier": norm(r.get("id_pdc_itinerance")),
        "stationIdentifier": norm(r.get("id_station_itinerance")),
        "stationName": norm(r.get("nom_station")),
        "powerKw": norm(r.get("puissance_nominale")),
    }


def unwrap_type(t: Any) -> tuple[str | None, str | None, list[str]]:
    wrappers = []
    cur = t if isinstance(t, dict) else {}
    for _ in range(8):
        kind = cur.get("kind")
        name = cur.get("name")
        if kind in ("NON_NULL", "LIST"):
            wrappers.append(kind)
        if name:
            return kind, name, wrappers
        cur = cur.get("ofType") if isinstance(cur.get("ofType"), dict) else {}
    return None, None, wrappers


def introspect_type(type_name: str) -> dict[str, Any]:
    if not re.fullmatch(r"[_A-Za-z][_0-9A-Za-z]*", type_name):
        raise ValueError(type_name)
    query = f"""
    query TccType {{
      __type(name: \"{type_name}\") {{
        name kind
        fields {{ name type {{ {TYPE_SHAPE} }} args {{ name type {{ {TYPE_SHAPE} }} }} }}
      }}
    }}
    """
    status, obj = post(query)
    t = ((obj.get("data") or {}).get("__type") or {}) if isinstance(obj, dict) else {}
    fields = []
    for f in t.get("fields") or []:
        kind, named, wrappers = unwrap_type(f.get("type"))
        fields.append({"name": f.get("name"), "kind": kind, "namedType": named, "wrappers": wrappers})
    return {"status": status, "name": t.get("name"), "kind": t.get("kind"), "fields": fields}


def scalar_field_names(type_info: dict[str, Any]) -> list[str]:
    scalar_kinds = {"SCALAR", "ENUM"}
    return sorted({f["name"] for f in type_info.get("fields") or [] if f.get("kind") in scalar_kinds and f.get("name")})


def safe_subset(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            low = str(k).casefold()
            if any(s in low for s in SAFE_VALUE_KEYS):
                out[str(k)] = safe_subset(v)
            elif isinstance(v, dict):
                nested = safe_subset(v)
                if nested:
                    out[str(k)] = nested
            elif isinstance(v, list):
                nested = safe_subset(v)
                if nested:
                    out[str(k)] = nested
        return out
    if isinstance(value, list):
        return [safe_subset(v) for v in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def find_values_by_key(value: Any, wanted: str) -> list[Any]:
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).casefold() == wanted.casefold():
                found.append(v)
            found.extend(find_values_by_key(v, wanted))
    elif isinstance(value, list):
        for v in value:
            found.extend(find_values_by_key(v, wanted))
    return found


def main() -> None:
    sample = sample_evse()
    root_type = introspect_type("ViewEvseUsingIdentifierOutput")
    nested_types = {}
    for f in root_type.get("fields") or []:
        named = f.get("namedType")
        if named and f.get("kind") == "OBJECT":
            nested_types[named] = introspect_type(named)

    root_scalars = scalar_field_names(root_type)
    selections = list(root_scalars)
    for f in root_type.get("fields") or []:
        if f.get("kind") != "OBJECT" or not f.get("namedType"):
            continue
        nested = nested_types.get(f["namedType"]) or {}
        scalars = scalar_field_names(nested)
        if scalars:
            selections.append(f"{f['name']} {{ {' '.join(scalars)} }}")
    if not selections:
        raise RuntimeError("No selectable public fields on ViewEvseUsingIdentifierOutput")

    query = f"""
    query TccViewEvse($identifier: EvseIdentifier!) {{
      chargePoints {{
        locations {{
          viewByIdentifier(identifier: $identifier) {{
            {' '.join(selections)}
          }}
        }}
      }}
    }}
    """
    status, obj = post(query, {"identifier": sample["evseIdentifier"]})
    data = obj.get("data") if isinstance(obj, dict) else None
    errors = obj.get("errors") if isinstance(obj, dict) else None
    safe_data = safe_subset(data) if data is not None else None

    tariff_group_ids = [x for x in find_values_by_key(data, "tariffGroupId") if x]
    evse_ids = [x for x in find_values_by_key(data, "id") if isinstance(x, str) and ("E" in x or x == sample["evseIdentifier"])]

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "bump-public-evse-sample-probe",
        "generatedAt": now_iso(),
        "method": {
            "unauthenticated": True,
            "publicReadOnlyQuery": True,
            "sampleFromOfficialBumpIrve": True,
            "personalDataQueried": False,
            "mutationsSent": False,
        },
        "sample": sample,
        "rootType": root_type,
        "nestedTypes": nested_types,
        "queryStatus": status,
        "graphqlErrorMessages": [str(e.get("message"))[:300] for e in (errors or []) if isinstance(e, dict)],
        "safePublicData": safe_data,
        "tariffGroupIdsFound": sorted({str(x) for x in tariff_group_ids}),
        "evseIdsFound": sorted({str(x) for x in evse_ids}),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Bump official EVSE sample probe",
        "",
        "Public unauthenticated GraphQL lookup using one EVSE identifier from Bump's official IRVE dataset.",
        "",
        f"- Station: **{sample['stationName']}**",
        f"- EVSE identifier: **{sample['evseIdentifier']}**",
        f"- Declared power: **{sample['powerKw']} kW**",
        f"- GraphQL HTTP status: **{status}**",
        f"- Tariff group IDs discovered: **{', '.join(payload['tariffGroupIdsFound']) or 'none'}**",
        "",
        "## Public technical data retained",
        "",
        "```json",
        json.dumps(safe_data, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    if payload["graphqlErrorMessages"]:
        lines += ["## GraphQL errors", ""] + [f"- {m}" for m in payload["graphqlErrorMessages"]] + [""]
    lines += [
        "## TCC rule",
        "",
        "No tariff is published from this sample unless a tariffGroupId is obtained and the corresponding public tariff detail exposes an explicit price structure.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": status, "tariffGroupIds": payload["tariffGroupIdsFound"], "errors": payload["graphqlErrorMessages"]}, indent=2))


if __name__ == "__main__":
    main()
