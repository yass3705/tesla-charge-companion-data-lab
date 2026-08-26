#!/usr/bin/env python3
"""Recursively inspect Bump's public GraphQL tariff-description schema.

Read-only unauthenticated GraphQL introspection only. The output contains type/field metadata,
never user/account/session/payment data.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT = "https://api.bump-charge.com/graphql"
OUT_JSON = Path("reports/bump/tariff_schema_latest.json")
OUT_MD = Path("reports/bump/tariff_schema_latest.md")
UA = "TeslaChargeCompanionDataLab/1.0 (public Bump tariff schema probe)"
TYPE_SHAPE = "kind name ofType { kind name ofType { kind name ofType { kind name } } }"
START_TYPES = ["Tariff", "TariffDescription", "TariffGroupDetail", "TariffCalculatorOutput"]
FOLLOW = re.compile(r"tariff|price|amount|cost|component|description|restriction|energy|charging|parking|time|duration|fee|rate|step|consumption|calculator", re.I)
MAX_TYPES = 80


def post(query: str) -> tuple[int | str, dict[str, Any]]:
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"query": query}).encode(),
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


def unwrap(t: Any) -> dict[str, Any]:
    cur = t if isinstance(t, dict) else {}
    wrappers: list[str] = []
    for _ in range(8):
        kind, name = cur.get("kind"), cur.get("name")
        if kind in ("NON_NULL", "LIST"):
            wrappers.append(str(kind))
        if name:
            return {"kind": kind, "name": name, "wrappers": wrappers}
        cur = cur.get("ofType") if isinstance(cur.get("ofType"), dict) else {}
    return {"kind": None, "name": None, "wrappers": wrappers}


def inspect(name: str) -> tuple[int | str, dict[str, Any] | None, list[str]]:
    if not re.fullmatch(r"[_A-Za-z][_0-9A-Za-z]*", name):
        return "invalid", None, []
    q = f'''query TccTariffType {{
      __type(name: "{name}") {{
        name kind
        fields {{ name type {{ {TYPE_SHAPE} }} args {{ name type {{ {TYPE_SHAPE} }} }} }}
        inputFields {{ name type {{ {TYPE_SHAPE} }} }}
        enumValues {{ name }}
        possibleTypes {{ name kind }}
      }}
    }}'''
    status, obj = post(q)
    errors = [str(x.get("message"))[:500] for x in (obj.get("errors") or []) if isinstance(x, dict)]
    t = ((obj.get("data") or {}).get("__type")) if isinstance(obj, dict) else None
    if not isinstance(t, dict):
        return status, None, errors
    fields = []
    for f in t.get("fields") or []:
        if not isinstance(f, dict):
            continue
        fields.append({
            "name": f.get("name"),
            "type": unwrap(f.get("type")),
            "args": [{"name": a.get("name"), "type": unwrap(a.get("type"))} for a in (f.get("args") or []) if isinstance(a, dict)],
        })
    inputs = [{"name": f.get("name"), "type": unwrap(f.get("type"))} for f in (t.get("inputFields") or []) if isinstance(f, dict)]
    return status, {
        "name": t.get("name"), "kind": t.get("kind"), "fields": fields, "inputFields": inputs,
        "enumValues": [v.get("name") for v in (t.get("enumValues") or []) if isinstance(v, dict)],
        "possibleTypes": [{"name": p.get("name"), "kind": p.get("kind")} for p in (t.get("possibleTypes") or []) if isinstance(p, dict)],
    }, errors


def main() -> None:
    queue = deque(START_TYPES)
    seen: set[str] = set()
    types: dict[str, Any] = {}
    errors: dict[str, list[str]] = {}
    while queue and len(seen) < MAX_TYPES:
        name = queue.popleft()
        if name in seen:
            continue
        seen.add(name)
        status, t, errs = inspect(name)
        if errs:
            errors[name] = errs
        if not t:
            continue
        types[name] = {"status": status, **t}
        candidates: list[str] = []
        for f in t.get("fields") or []:
            if f.get("type", {}).get("name"):
                candidates.append(str(f["type"]["name"]))
            for a in f.get("args") or []:
                if a.get("type", {}).get("name"):
                    candidates.append(str(a["type"]["name"]))
        for f in t.get("inputFields") or []:
            if f.get("type", {}).get("name"):
                candidates.append(str(f["type"]["name"]))
        candidates += [str(p.get("name")) for p in t.get("possibleTypes") or [] if p.get("name")]
        for candidate in candidates:
            if candidate not in seen and FOLLOW.search(candidate):
                queue.append(candidate)

    payload = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": {"unauthenticated": True, "introspectionOnly": True, "mutationsSent": False, "personalDataQueried": False},
        "startTypes": START_TYPES,
        "typeCount": len(types),
        "types": types,
        "errors": errors,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Bump tariff schema", "", f"Types discovered: **{len(types)}**", ""]
    for name, t in types.items():
        lines += [f"## `{name}` ({t.get('kind')})", ""]
        for f in t.get("fields") or []:
            typ = f.get("type", {}).get("name") or "?"
            lines.append(f"- `{f.get('name')}` → `{typ}`")
        for f in t.get("inputFields") or []:
            typ = f.get("type", {}).get("name") or "?"
            lines.append(f"- input `{f.get('name')}` → `{typ}`")
        if t.get("enumValues"):
            lines.append("- enum: " + ", ".join(f"`{x}`" for x in t["enumValues"]))
        lines.append("")
    OUT_MD.write_text("\n".join(lines))
    print(json.dumps({"typeCount": len(types), "typeNames": list(types), "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
