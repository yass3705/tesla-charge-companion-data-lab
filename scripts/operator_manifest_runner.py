#!/usr/bin/env python3
"""Validate an operator against official HTML sources and emit a normalized JSON marker.

This runner is intentionally conservative: manifests contain the validated tariff model,
while the runner verifies that the official pages still expose the expected evidence.
If evidence disappears or changes, the run fails instead of silently publishing stale data.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def html_text(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def fetch(url: str, attempts: int = 3) -> tuple[int, str, str]:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                decoded = raw.decode(charset, errors="replace")
                return int(getattr(resp, "status", 200)), html_text(decoded), hashlib.sha256(raw).hexdigest()
        except Exception as exc:  # noqa: BLE001 - surfaced after bounded retries
            last = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Unable to fetch {url} after {attempts} attempts: {last}")


def numeric_tokens(text: str) -> list[float]:
    vals: list[float] = []
    for m in re.finditer(r"(?<!\d)(\d+(?:[,.]\d+)?)(?!\d)", norm(text)):
        try:
            vals.append(float(m.group(1).replace(",", ".")))
        except ValueError:
            pass
    return vals


def has_number(text: str, value: float, tol: float = 0.0005) -> bool:
    return any(abs(x - value) <= tol for x in numeric_tokens(text))


def validate_source(source: dict, text: str) -> None:
    n = norm(text)
    for phrase in source.get("requiredPhrases", []):
        if norm(str(phrase)) not in n:
            raise RuntimeError(f"{source['key']}: required phrase missing: {phrase}")
    for group in source.get("requiredAny", []):
        if not any(norm(str(x)) in n for x in group):
            raise RuntimeError(f"{source['key']}: none of required alternatives found: {group}")
    for value in source.get("requiredNumbers", []):
        if not has_number(text, float(value)):
            raise RuntimeError(f"{source['key']}: required numeric evidence missing: {value}")
    for pattern in source.get("requiredRegex", []):
        if not re.search(pattern, n, flags=re.I):
            raise RuntimeError(f"{source['key']}: required regex missing: {pattern}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--operator", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    manifest_path = Path("config/operator_manifests") / f"{args.operator}.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Unknown operator manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("key") != args.operator:
        raise RuntimeError("Manifest key does not match requested operator")

    evidence = []
    for source in manifest.get("sources", []):
        status, text, sha = fetch(source["url"])
        if status != 200:
            raise RuntimeError(f"{source['key']}: HTTP {status}")
        validate_source(source, text)
        evidence.append({
            "key": source["key"],
            "url": source["url"],
            "httpStatus": status,
            "rawSha256": sha,
        })

    facts = manifest["facts"]
    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": manifest.get("schemaVersion", "1.0.0"),
        "dataset": manifest["dataset"],
        "generatedAt": now_iso(),
        "operator": manifest["operator"],
        "country": manifest.get("country", "FR"),
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": evidence,
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": manifest.get("notes", []),
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    output_name = manifest["outputFile"]
    (out / output_name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = [f"# {manifest['operator']} official check", ""]
    summary.extend(f"- {line}" for line in manifest.get("summaryLines", []))
    summary.append(f"- Fingerprint: `{fingerprint}`")
    (out / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
