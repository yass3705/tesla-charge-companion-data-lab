#!/usr/bin/env python3
"""Query Bump's public tariff engine for one verified Bump-operated EVSE.

The EVSE/tariff-group pair comes from Bump's unauthenticated public map search and is linked to
Bump's official IRVE export. Only read-only GraphQL tariff queries are sent; no account, charging,
payment or mutation operation is used.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT = "https://api.bump-charge.com/graphql"
OUT = Path("reports/bump/tariff_detail_latest.json")
UA = "TeslaChargeCompanionDataLab/1.0 (public Bump tariff detail probe)"
EVSE_ID = "73df1aa7-c85e-afd7-0a9b-03ee71f39215"
EVSE_IDENTIFIER = "FRBMPE1151"
LOCATION_ID = 11936
TARIFF_GROUP_ID = "f03e61b7-dd44-4533-bf42-3fc299c589ff"
TYPE_SHAPE = "kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } }"
SAFE_FIELD = re.compile(
    r"^(?:id|name|label|description|alternativeText|currency|price|amount|value|unit|type|priceType|dimension|"
    r"stepSize|step|vat|tax|taxes|tariff|tariffs|tariffGroupId|tariffId|component|components|element|elements|"
    r"restriction|restrictions|startDateTime|endDateTime|minDuration|maxDuration|minKwh|maxKwh|minCurrent|"
    r"maxCurrent|minPower|maxPower|minimum|maximum|energy|time|duration|parking|flat|flatFee|fixed|session|fee|"
    r"fees|cost|costs|rate|rates|kwh|minute|minutes|priceExcludingVat|priceIncludingVat|pricePerKWh|pricePerHour|"
    r"minPrice|includingVat|excludingVat|total|subtotal|billing|overstay|occupancy|idle|gracePeriod|freePeriod|"
    r"generatedDescription|quick|short|long|quickDetail|shortDetail|isTariffChangingInTime)$",
    re.I,
)


def post(query: str, variables: dict[str, Any] | None = None) -> tuple[int | str, dict[str, Any]]:
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        method="POST",
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            obj = json.load(r)
            return int(r.status), obj if isinstance(obj, dict) else {}
    except urllib.error.HTTPError as e:
        try:
            obj = json.loads(e.read(500_000))
        except Exception:
            obj = {}
        return int(e.code), obj if isinstance(obj, dict) else {}
    except Exception as e:
        return "network_error", {"errorType": type(e).__name__}


def unwrap(t: Any) -> tuple[str | None, str | None]:
    cur = t if isinstance(t, dict) else {}
    for _ in range(10):
        kind, name = cur.get("kind"), cur.get("name")
        if name:
            return kind, name
        cur = cur.get("ofType") if isinstance(cur.get("ofType"), dict) else {}
    return None, None


def inspect_type(name: str) -> dict[str, Any]:
    assert re.fullmatch(r"[_A-Za-z][_0-9A-Za-z]*", name)
    q = f'''query TccType {{ __type(name: "{name}") {{ name kind fields {{ name type {{ {TYPE_SHAPE} }} args {{ name }} }} }} }}'''
    _, obj = post(q)
    t = ((obj.get("data") or {}).get("__type") or {})
    fields = []
    for f in t.get("fields") or []:
        kind, named = unwrap(f.get("type"))
        fields.append({"name": f.get("name"), "kind": kind, "namedType": named, "hasArgs": bool(f.get("args"))})
    return {"name": t.get("name"), "kind": t.get("kind"), "fields": fields}


def build_selection(type_name: str, cache: dict[str, Any], depth: int = 0, stack: set[str] | None = None) -> str:
    if depth > 6:
        return "__typename"
    stack = set(stack or ())
    if type_name in stack:
        return "__typename"
    stack.add(type_name)
    t = cache.setdefault(type_name, inspect_type(type_name))
    parts = ["__typename"]
    for f in t.get("fields") or []:
        name = str(f.get("name") or "")
        if f.get("hasArgs") or not SAFE_FIELD.match(name):
            continue
        kind, named = f.get("kind"), f.get("namedType")
        if kind in ("SCALAR", "ENUM"):
            parts.append(name)
        elif kind == "OBJECT" and named:
            child = build_selection(named, cache, depth + 1, stack)
            parts.append(f"{name} {{ {child} }}")
    return " ".join(parts)


def main() -> None:
    cache: dict[str, Any] = {}
    selection = build_selection("Tariff", cache)
    query = f'''query TccTariff($tariffGroupId: TariffGroupId!, $evseId: EvseId, $hasAnonymous: Boolean) {{
      tariffs {{
        detail(tariffGroupId: $tariffGroupId, evseId: $evseId, hasAnonymous: $hasAnonymous) {{ {selection} }}
      }}
    }}'''
    attempts = []
    for label, anonymous in (("anonymous_true", True), ("anonymous_false", False), ("anonymous_null", None)):
        variables = {"tariffGroupId": TARIFF_GROUP_ID, "evseId": EVSE_ID, "hasAnonymous": anonymous}
        status, obj = post(query, variables)
        data = (((obj.get("data") or {}).get("tariffs") or {}).get("detail")) if isinstance(obj, dict) else None
        errors = [str(e.get("message"))[:1000] for e in (obj.get("errors") or []) if isinstance(e, dict)]
        attempts.append({"label": label, "status": status, "errors": errors, "data": data})

    payload = {
        "schemaVersion": "1.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": {
            "unauthenticated": True,
            "publicReadOnlyTariffQueryOnly": True,
            "schemaDerivedPricingFieldsOnly": True,
            "mutationsSent": False,
            "credentialsUsed": False,
            "personalDataQueried": False,
            "chargingSessionStarted": False,
            "paymentSubmitted": False,
        },
        "verifiedBinding": {
            "officialEvseIdentifier": EVSE_IDENTIFIER,
            "locationId": LOCATION_ID,
            "evseId": EVSE_ID,
            "tariffGroupId": TARIFF_GROUP_ID,
        },
        "selection": selection,
        "typeShapes": cache,
        "attempts": attempts,
        "tariffResolved": any(a.get("data") is not None and not a.get("errors") for a in attempts),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selection": selection, "attempts": attempts, "tariffResolved": payload["tariffResolved"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
