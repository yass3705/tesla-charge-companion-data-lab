#!/usr/bin/env python3
"""Discover Bump's public GraphQL charging/tariff schema without credentials.

Only harmless read-only GraphQL meta-queries are sent. No mutation, account data, charge action,
payment action, token, cookie or private identifier is used. Persisted output contains endpoint
status and schema field/argument/type names only, never raw response bodies.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://api.bump-charge.com"
OUT_JSON = Path("reports/bump/graphql_public_probe_latest.json")
OUT_MD = Path("reports/bump/graphql_public_probe_latest.md")
UA = "TeslaChargeCompanionDataLab/1.0 (read-only public GraphQL probe)"
ENDPOINTS = ("/graphql", "/api/graphql", "/v1/graphql", "/")
TARGET_NAMESPACES = ("chargePoints", "tariffs", "locationPlanning")
TARGET_EXTRA_TYPES = (
    "LocationQueryController",
    "Tariff",
    "TariffGroupDetail",
    "TariffGroupDetailInput",
    "TariffGroupId",
    "EvseId",
)

TYPENAME_QUERY = "query TccPublicProbe { __typename }"
TYPE_SHAPE = "kind name ofType { kind name ofType { kind name ofType { kind name } } }"
SCHEMA_QUERY = f"""
query TccPublicSchemaProbe {{
  __schema {{
    queryType {{
      fields {{
        name
        type {{ {TYPE_SHAPE} }}
        args {{ name type {{ {TYPE_SHAPE} }} }}
      }}
    }}
  }}
}}
""".strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def post_graphql(path: str, query: str) -> tuple[int | str, str, bytes]:
    body = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=body,
        method="POST",
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return int(r.status), (r.headers.get("Content-Type") or "").split(";", 1)[0], r.read(2_000_001)
    except urllib.error.HTTPError as e:
        return int(e.code), (e.headers.get("Content-Type") or "").split(";", 1)[0], e.read(500_000)
    except Exception as e:
        return "network_error", type(e).__name__, b""


def json_obj(raw: bytes) -> dict[str, Any] | None:
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def typename_success(raw: bytes) -> bool:
    obj = json_obj(raw)
    return bool(obj and isinstance(obj.get("data"), dict) and obj["data"].get("__typename") == "Query")


def type_summary(t: Any) -> dict[str, Any]:
    if not isinstance(t, dict):
        return {"kind": None, "name": None, "namedType": None, "wrappers": []}
    wrappers = []
    cur = t
    named = None
    for _ in range(8):
        if not isinstance(cur, dict):
            break
        kind = cur.get("kind")
        name = cur.get("name")
        if kind in ("NON_NULL", "LIST"):
            wrappers.append(kind)
        if name:
            named = name
            break
        cur = cur.get("ofType")
    return {"kind": t.get("kind"), "name": t.get("name"), "namedType": named, "wrappers": wrappers}


def sanitize_fields(fields: Any) -> list[dict[str, Any]]:
    out = []
    for field in fields or []:
        if not isinstance(field, dict) or not field.get("name"):
            continue
        args = []
        for arg in field.get("args") or []:
            if isinstance(arg, dict) and arg.get("name"):
                args.append({"name": str(arg["name"]), "type": type_summary(arg.get("type"))})
        out.append({
            "name": str(field["name"]),
            "type": type_summary(field.get("type")),
            "args": args,
        })
    return sorted(out, key=lambda x: x["name"].casefold())


def sanitize_input_fields(fields: Any) -> list[dict[str, Any]]:
    out = []
    for field in fields or []:
        if isinstance(field, dict) and field.get("name"):
            out.append({"name": str(field["name"]), "type": type_summary(field.get("type"))})
    return sorted(out, key=lambda x: x["name"].casefold())


def sanitize_enum_values(values: Any) -> list[str]:
    return sorted(str(v.get("name")) for v in values or [] if isinstance(v, dict) and v.get("name"))


def sanitize_query_schema(raw: bytes) -> list[dict[str, Any]]:
    obj = json_obj(raw) or {}
    fields = (((obj.get("data") or {}).get("__schema") or {}).get("queryType") or {}).get("fields") or []
    return sanitize_fields(fields)


def type_introspection_query(type_name: str) -> str:
    if not re.fullmatch(r"[_A-Za-z][_0-9A-Za-z]*", type_name):
        raise ValueError("Invalid GraphQL type name")
    return f"""
query TccPublicTypeProbe {{
  __type(name: \"{type_name}\") {{
    name
    kind
    fields {{
      name
      type {{ {TYPE_SHAPE} }}
      args {{ name type {{ {TYPE_SHAPE} }} }}
    }}
    inputFields {{ name type {{ {TYPE_SHAPE} }} }}
    enumValues {{ name }}
  }}
}}
""".strip()


def parse_type(raw: bytes) -> dict[str, Any] | None:
    obj = json_obj(raw) or {}
    t = (obj.get("data") or {}).get("__type")
    if not isinstance(t, dict):
        return None
    return {
        "name": t.get("name"),
        "kind": t.get("kind"),
        "fields": sanitize_fields(t.get("fields")),
        "inputFields": sanitize_input_fields(t.get("inputFields")),
        "enumValues": sanitize_enum_values(t.get("enumValues")),
    }


def format_type(t: dict[str, Any]) -> str:
    name = t.get("namedType") or t.get("kind") or "?"
    wrappers = t.get("wrappers") or []
    return "/".join(wrappers + [name]) if wrappers else name


def main() -> None:
    attempts = []
    endpoint = None
    for path in ENDPOINTS:
        status, content_type, raw = post_graphql(path, TYPENAME_QUERY)
        ok = typename_success(raw)
        obj = json_obj(raw)
        attempts.append({
            "path": path,
            "status": status,
            "contentType": content_type,
            "graphqlTypenameSuccess": ok,
            "topLevelJsonKeys": sorted(obj.keys()) if obj else [],
        })
        if ok:
            endpoint = path
            break

    schema_fields: list[dict[str, Any]] = []
    introspection = {"attempted": False, "status": None, "fieldCount": 0}
    namespace_types: dict[str, str] = {}
    namespace_details: dict[str, Any] = {}
    extra_types: dict[str, Any] = {}
    if endpoint:
        status, content_type, raw = post_graphql(endpoint, SCHEMA_QUERY)
        schema_fields = sanitize_query_schema(raw)
        introspection = {
            "attempted": True,
            "status": status,
            "contentType": content_type,
            "fieldCount": len(schema_fields),
            "succeeded": bool(schema_fields),
        }
        by_name = {f["name"]: f for f in schema_fields}
        discovered_extra = set(TARGET_EXTRA_TYPES)
        for namespace in TARGET_NAMESPACES:
            f = by_name.get(namespace)
            type_name = (f or {}).get("type", {}).get("namedType") if f else None
            if not type_name:
                continue
            namespace_types[namespace] = type_name
            t_status, t_content, t_raw = post_graphql(endpoint, type_introspection_query(type_name))
            parsed = parse_type(t_raw)
            namespace_details[namespace] = {
                "typeName": type_name,
                "status": t_status,
                "contentType": t_content,
                "type": parsed,
            }
            if parsed:
                for fld in parsed["fields"]:
                    named = fld["type"].get("namedType")
                    if named:
                        discovered_extra.add(named)
                    for arg in fld["args"]:
                        anamed = arg["type"].get("namedType")
                        if anamed:
                            discovered_extra.add(anamed)

        # Read metadata only for charging/tariff/location-specific return/input types.
        for type_name in sorted(discovered_extra):
            low = type_name.casefold()
            if type_name in TARGET_EXTRA_TYPES or any(k in low for k in ("tariff", "locationquery", "evse")):
                t_status, t_content, t_raw = post_graphql(endpoint, type_introspection_query(type_name))
                parsed = parse_type(t_raw)
                if parsed:
                    extra_types[type_name] = {
                        "status": t_status,
                        "contentType": t_content,
                        "type": parsed,
                    }

    interesting_names = {"tariffs", "chargepoints", "locations", "search", "viewbyqrurl", "viewevsebyidentifier", "chargelocationbyid", "viewlocationbyidentifier"}
    interesting = [f for f in schema_fields if f["name"].casefold() in interesting_names or any(k in f["name"].casefold() for k in ("tariff", "charge", "location", "evse"))]

    payload = {
        "schemaVersion": "1.2.0",
        "dataset": "bump-public-graphql-probe",
        "generatedAt": now_iso(),
        "base": BASE,
        "method": {
            "unauthenticated": True,
            "readOnlyGraphqlQueriesOnly": True,
            "mutationsSent": False,
            "credentialsUsed": False,
            "responseBodiesPersisted": False,
            "personalDataQueried": False,
        },
        "attempts": attempts,
        "graphqlEndpoint": endpoint,
        "introspection": introspection,
        "queryFields": schema_fields,
        "interestingQueryFields": interesting,
        "namespaceTypes": namespace_types,
        "namespaceDetails": namespace_details,
        "extraTypes": extra_types,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Bump public GraphQL probe",
        "",
        "Unauthenticated, read-only GraphQL meta-query only. No account/session/token or charging action used.",
        "",
        "## Endpoint attempts",
        "",
    ]
    for a in attempts:
        lines.append(f"- `POST {a['path']}` → **{a['status']}** — GraphQL Query typename: **{str(a['graphqlTypenameSuccess']).lower()}**")
    lines += ["", f"Resolved GraphQL endpoint: **{endpoint or 'none'}**", ""]
    if endpoint:
        lines += [
            "## Public query schema",
            "",
            f"Introspection status: **{introspection.get('status')}**, fields discovered: **{len(schema_fields)}**",
            "",
        ]
        for f in interesting:
            args = ", ".join(a["name"] for a in f["args"]) or "no args"
            lines.append(f"- `{f['name']}` → `{f['type'].get('namedType')}` — args: `{args}`")
        for namespace, detail in namespace_details.items():
            parsed = detail.get("type") or {}
            lines += ["", f"## Namespace `{namespace}` → `{detail['typeName']}`", ""]
            for f in parsed.get("fields") or []:
                arg_bits = [f"{arg['name']}:{format_type(arg['type'])}" for arg in f["args"]]
                lines.append(f"- `{f['name']}` → `{format_type(f['type'])}` — `{', '.join(arg_bits) or 'no args'}`")
        for type_name, detail in extra_types.items():
            parsed = detail["type"]
            lines += ["", f"## Type `{type_name}` ({parsed['kind']})", ""]
            for f in parsed.get("fields") or []:
                args = ", ".join(f"{a['name']}:{format_type(a['type'])}" for a in f["args"])
                lines.append(f"- field `{f['name']}` → `{format_type(f['type'])}`" + (f" — `{args}`" if args else ""))
            for f in parsed.get("inputFields") or []:
                lines.append(f"- input `{f['name']}` → `{format_type(f['type'])}`")
            if parsed.get("enumValues"):
                lines.append("- enum values: `" + "`, `".join(parsed["enumValues"]) + "`")
    lines += [
        "",
        "## TCC rule",
        "",
        "This probe only establishes public schema metadata. Station prices remain non-rankable until an explicit tariff query can be matched to Bump's official station/PDC inventory.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"endpoint": endpoint, "fieldCount": len(schema_fields), "namespaceTypes": namespace_types, "extraTypeCount": len(extra_types)}, indent=2))


if __name__ == "__main__":
    main()
