#!/usr/bin/env python3
"""Add Riviera Française / CARF evidence to the PACA regional coverage output."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

URL = "https://www.evzen.com/fr/reseau-carf"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(v):
    import unicodedata
    v = unescape(v or "")
    v = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", v, flags=re.I | re.S)
    v = re.sub(r"<[^>]+>", " ", v)
    v = unicodedata.normalize("NFKD", v)
    v = "".join(c for c in v if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", v.lower().replace("\xa0", " ")).strip()


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=55) as r:
        raw = r.read()
        return int(getattr(r, "status", 200)), raw, r.geturl(), r.headers.get("content-type", "")


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/paca")
    args = ap.parse_args()
    out = Path(args.out)
    coverage_path = out / "paca_regional_coverage.json"
    summary_path = out / "SUMMARY.md"
    if not coverage_path.exists() or not summary_path.exists():
        raise RuntimeError("base PACA output missing before CARF overlay")

    status, raw, final, ctype = fetch()
    text = raw.decode("utf-8", errors="replace")
    n = norm(text)
    required = ["riviera francaise", "4,00", "2,00", "moulinet", "1er juillet 2025"]
    missing = [x for x in required if norm(x) not in n]
    if status != 200 or missing:
        raise RuntimeError(f"CARF current tariff witness failed: status={status}, missing={missing}")

    source = {
        "url": final,
        "httpStatus": status,
        "contentType": ctype,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    common = {
        "schemaVersion": "1.0.0",
        "generatedAt": now(),
        "country": "FR",
        "region": "Provence-Alpes-Côte d’Azur",
        "publicationStatus": "validated_candidate",
    }
    carf = {
        **common,
        "dataset": "riviera-francaise-carf-evzen-official-paca",
        "operator": "Riviera Française / CARF",
        "serviceOperator": "EVzen / SMEG Développement",
        "department": "Alpes-Maritimes",
        "classification": {
            "localPublicNetwork": True,
            "exactPublishedTariff": True,
            "basis": "connection_time",
            "roamingSeparate": True,
        },
        "effectiveDate": "2025-07-01",
        "directTariff": {
            "day0700To2200EurPerHour": 4.0,
            "night2200To0700EurPerHour": 2.0,
            "billedByMinute": True,
            "moulinetStationsFree": True,
        },
        "tccDecision": {
            "directTariffClassable": True,
            "timeWindowRequired": True,
            "moulinetFreeExceptionRequired": True,
            "roamingSeparate": True,
        },
        "sourceEvidence": source,
    }
    write(out / "riviera_francaise_carf_evzen_official_paca.json", carf)

    p = json.loads(coverage_path.read_text())
    families = p["departments"]["Alpes-Maritimes"]["publicNetworkFamilies"]
    if "Riviera Française / CARF" not in families:
        families.append("Riviera Française / CARF")
    exact = p["coverage"]["operatorFamiliesWithExactCurrentPublicGrid"]
    if "Riviera Française / CARF" not in exact:
        exact.append("Riviera Française / CARF")
    p["sourceHealth"]["officialOrOperatorSourcesReachableAtRun"] = int(p["sourceHealth"]["officialOrOperatorSourcesReachableAtRun"]) + 1
    p["sourceHealth"]["sourcesTotal"] = int(p["sourceHealth"]["sourcesTotal"]) + 1
    p.setdefault("sourceEvidence", {})["rivieraFrancaiseCarf"] = source
    p.setdefault("notes", []).append("Riviera Française / CARF is a distinct Alpes-Maritimes public network and must not be collapsed into WiiiZ or Prise de Nice.")
    write(coverage_path, p)

    summary = summary_path.read_text()
    marker = "- WiiiZ: current EVzen grid validated, including AC zone/profile tariffs and **DC 50 kW at 0.24/0.40 EUR/kWh + 0.25 EUR/min post-charge**.\n"
    line = "- Riviera Française / CARF: current EVzen connection-time grid validated at **4.00 EUR/h (07:00-22:00)** and **2.00 EUR/h (22:00-07:00)**; Moulinet stations remain **free**.\n"
    if line not in summary:
        if marker in summary:
            summary = summary.replace(marker, marker + line, 1)
        else:
            summary += line
    summary = re.sub(r"Current source reachability: \*\*\d+/\d+\*\*\.", f"Current source reachability: **{p['sourceHealth']['officialOrOperatorSourcesReachableAtRun']}/{p['sourceHealth']['sourcesTotal']}**.", summary)
    summary_path.write_text(summary)


if __name__ == "__main__":
    main()
