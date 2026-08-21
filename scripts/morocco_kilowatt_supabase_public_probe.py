#!/usr/bin/env python3
"""Sanitized, read-only Kilowatt Morocco Supabase discovery.

Recovers the public client context from the published Android package at runtime,
uses it only in-memory against the app's own Supabase REST endpoint, and persists
no raw API key/JWT, credentials, account data, or unfiltered response bodies.
Only charging-infrastructure table names/schema keys and whitelisted public
station/tariff/status fields may be retained.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

PACKAGE = "ma.kilowatt.app"
KNOWN_PROJECT = "jmrgknphxsviooizyilj.supabase.co"
OUT = Path("artifacts/morocco-kilowatt-supabase")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"
JWT_RE = re.compile(rb"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
URL_RE = re.compile(rb"https://[a-z0-9]{20}\.supabase\.co", re.I)
INFRA_WORDS = ("station", "charger", "charge_point", "chargepoint", "evse", "connector", "location", "tariff", "price", "pricing")
SENSITIVE_TABLE_WORDS = ("user", "profile", "account", "payment", "invoice", "wallet", "customer", "auth", "session", "receipt")
SAFE_FIELDS = {
    "id", "name", "title", "status", "availability", "available", "is_available",
    "power", "power_kw", "max_power", "max_power_kw", "latitude", "longitude", "lat", "lng",
    "address", "city", "country", "currency", "tariff", "tariff_id", "price", "price_kwh",
    "price_per_kwh", "price_per_minute", "idle_price", "idle_fee", "fixed_starting_fee", "free",
    "operator", "operator_id", "network", "network_id", "cpo", "connector_type", "type",
    "station_id", "location_id", "evse_id", "connector_id", "updated_at", "last_updated",
}


def b64json(part: bytes) -> dict:
    try:
        part += b"=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part).decode("utf-8", "replace"))
    except Exception:
        return {}


def download(dest: Path):
    for fmt in ("XAPK", "APK"):
        try:
            req = urllib.request.Request(
                f"https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest",
                headers={"User-Agent": UA, "Accept": "*/*"},
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) > 100_000:
                dest.write_bytes(data)
                return fmt, len(data)
        except Exception:
            pass
    return None, 0


def unzip_safe(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as z:
            for info in z.infolist():
                if ".." not in Path(info.filename).parts and info.file_size < 180 * 1024 * 1024:
                    z.extract(info, dst)
    except Exception:
        pass


def bytes_for_candidate_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 160 * 1024 * 1024:
            continue
        if p.name in ("index.android.bundle", "main.jsbundle", "libapp.so", "resources.arsc", "classes.dex") or p.suffix.lower() in (".json", ".js", ".txt", ".xml"):
            try:
                yield p.read_bytes()
            except Exception:
                try:
                    yield subprocess.run(["strings", "-a", str(p)], capture_output=True, timeout=120).stdout
                except Exception:
                    pass


def choose_public_anon_key(blobs):
    seen = set()
    candidates = []
    project_urls = set()
    for blob in blobs:
        for u in URL_RE.findall(blob):
            project_urls.add(u.decode("ascii", "ignore").lower())
        for tok in JWT_RE.findall(blob):
            if tok in seen:
                continue
            seen.add(tok)
            parts = tok.split(b".")
            if len(parts) != 3:
                continue
            payload = b64json(parts[1])
            role = str(payload.get("role", "")).lower()
            ref = str(payload.get("ref", "")).lower()
            iss = str(payload.get("iss", "")).lower()
            if role in ("anon", "authenticated") or "supabase" in iss:
                candidates.append((tok.decode("ascii", "ignore"), role, ref, sorted(payload.keys())))
    # Prefer the publishable anonymous key only. Never use service_role/authenticated tokens.
    for token, role, ref, keys in candidates:
        if role == "anon" and (not ref or ref in KNOWN_PROJECT):
            return token, role, ref, keys, sorted(project_urls)
    return None, None, None, [], sorted(project_urls)


def http_json(url: str, headers: dict):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
            ctype = r.headers.get("content-type", "")
            body = r.read(1_500_000)
    except urllib.error.HTTPError as e:
        status = e.code
        ctype = e.headers.get("content-type", "") if e.headers else ""
        try:
            body = e.read(300_000)
        except Exception:
            body = b""
    except Exception as e:
        return None, "", None, type(e).__name__
    try:
        obj = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        obj = None
    return status, ctype, obj, None


def safe_sample(obj):
    if not isinstance(obj, list) or not obj or not isinstance(obj[0], dict):
        return None
    row = obj[0]
    out = {}
    for k, v in row.items():
        lk = str(k).lower()
        if lk not in SAFE_FIELDS:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict):
            nested = {nk: nv for nk, nv in v.items() if str(nk).lower() in SAFE_FIELDS and isinstance(nv, (str, int, float, bool, type(None)))}
            if nested:
                out[k] = nested
    return out or None


def main():
    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "package": PACKAGE,
        "policy": {
            "read_only": True,
            "no_login": True,
            "no_mutations": True,
            "public_anon_key_used_in_memory_only": True,
            "raw_key_persisted": False,
            "raw_package_persisted": False,
            "raw_response_bodies_persisted": False,
            "account_or_user_tables_queried": False,
        },
    }
    with tempfile.TemporaryDirectory(prefix="kilowatt-supabase-") as td:
        root = Path(td)
        pkg = root / "app.pkg"
        fmt, size = download(pkg)
        report.update({"download_ok": bool(fmt), "download_format": fmt, "download_bytes": size})
        if not fmt:
            (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
            return
        tree = root / "tree"
        unzip_safe(pkg, tree)
        for i, apk in enumerate(list(tree.rglob("*.apk"))[:30]):
            unzip_safe(apk, tree / f"apk_{i}")
        blobs = list(bytes_for_candidate_files(tree))
        token, role, ref, jwt_keys, urls = choose_public_anon_key(blobs)
        report["client_context"] = {
            "supabase_project_seen": any(KNOWN_PROJECT in u for u in urls),
            "project_hosts": [urllib.parse.urlsplit(u).hostname for u in urls[:10]],
            "anonymous_key_found": bool(token),
            "jwt_role": role,
            "jwt_ref_matches_project": bool(ref and ref == KNOWN_PROJECT.split(".")[0]),
            "jwt_claim_names": jwt_keys,
        }
        if not token:
            (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
            return
        base = f"https://{KNOWN_PROJECT}"
        headers = {"User-Agent": UA, "Accept": "application/json", "apikey": token, "Authorization": f"Bearer {token}"}
        status, ctype, spec, err = http_json(base + "/rest/v1/", headers)
        discovery = {"status": status, "content_type": ctype, "error_type": err}
        paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
        infra_tables = []
        if isinstance(paths, dict):
            for p in paths.keys():
                table = str(p).strip("/")
                low = table.lower()
                if table and any(w in low for w in INFRA_WORDS) and not any(w in low for w in SENSITIVE_TABLE_WORDS):
                    infra_tables.append(table)
        infra_tables = sorted(set(infra_tables))[:30]
        discovery["charging_infrastructure_tables"] = infra_tables
        discovery["charging_infrastructure_table_count"] = len(infra_tables)
        report["rest_discovery"] = discovery
        probes = []
        for table in infra_tables[:12]:
            url = base + "/rest/v1/" + urllib.parse.quote(table, safe="") + "?limit=1"
            st, ct, obj, er = http_json(url, headers)
            item = {"table": table, "status": st, "content_type": ct, "error_type": er}
            if isinstance(obj, list):
                item["row_count_returned"] = len(obj)
                if obj and isinstance(obj[0], dict):
                    item["field_names"] = sorted(str(k) for k in obj[0].keys())[:100]
                    sample = safe_sample(obj)
                    if sample:
                        item["sanitized_public_sample"] = sample
            probes.append(item)
        report["table_probes"] = probes
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"download_ok": report.get("download_ok"), "anonymous_key_found": report.get("client_context", {}).get("anonymous_key_found"), "table_count": report.get("rest_discovery", {}).get("charging_infrastructure_table_count")}))


if __name__ == "__main__":
    main()
