#!/usr/bin/env python3
"""Discover Bump's public GraphQL endpoint and query schema without credentials.

Only harmless read-only GraphQL meta-queries are sent. No mutation, account data, charge action,
payment action, token, cookie or private identifier is used. Persisted output contains endpoint
status and schema field/argument names only, never raw response bodies.
"""
from __future__ import annotations

import json
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

TYPENAME_QUERY = "query TccPublicProbe { __typename }"
SCHEMA_QUERY = """
query TccPublicSchemaProbe {
  __schema {
    queryType {
      fields {
        name
        args { name type { kind name ofType { kind name ofType { kind name } } } }
      }
    }
  }
}
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


def sanitize_schema(raw: bytes) -> list[dict[str, Any]]:
    obj = json_obj(raw) or {}
    fields = (((obj.get("data") or {}).get("__schema") or {}).get("queryType") or {}).get("fields") or []
    out = []
    for field in fields:
        if not isinstance(field, dict) or not field.get("name"):
            continue
        args = []
        for arg in field.get("args") or []:
            if not isinstance(arg, dict) or not arg.get("name"):
                continue
            t = arg.get("type") or {}
            args.append({
                "name": str(arg["name"]),
                "typeKind": t.get("kind"),
                "typeName": t.get("name"),
                "ofTypeKind": (t.get("ofType") or {}).get("kind") if isinstance(t.get("ofType"), dict) else None,
                "ofTypeName": (t.get("ofType") or {}).get("name") if isinstance(t.get("ofType"), dict) else None,
                "innerTypeName": (((t.get("ofType") or {}).get("ofType") or {}).get("name") if isinstance((t.get("ofType") or {}).get("ofType"), dict) else None),
            })
        out.append({"name": str(field["name"]), "args": args})
    return sorted(out, key=lambda x: x["name"].casefold())


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
    if endpoint:
        status, content_type, raw = post_graphql(endpoint, SCHEMA_QUERY)
        schema_fields = sanitize_schema(raw)
        introspection = {
            "attempted": True,
            "status": status,
            "contentType": content_type,
            "fieldCount": len(schema_fields),
            "succeeded": bool(schema_fields),
        }

    interesting_names = {"tariffs", "chargepoints", "locations", "search", "viewbyqrurl", "viewevsebyidentifier", "chargelocationbyid", "viewlocationbyidentifier"}
    interesting = [f for f in schema_fields if f["name"].casefold() in interesting_names or any(k in f["name"].casefold() for k in ("tariff", "charge", "location", "evse"))]

    payload = {
        "schemaVersion": "1.0.0",
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
            lines.append(f"- `{f['name']}` — args: `{args}`")
    lines += [
        "",
        "## TCC rule",
        "",
        "This probe only establishes public schema metadata. Station prices remain non-rankable until an explicit tariff query can be matched to Bump's official station/PDC inventory.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"endpoint": endpoint, "fieldCount": len(schema_fields), "interestingFieldCount": len(interesting)}, indent=2))


if __name__ == "__main__":
    main()
