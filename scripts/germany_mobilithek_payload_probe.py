#!/usr/bin/env python3
"""Check anonymous payload access for selected Mobilithek AFIR offers.

Mobilithek exposes a noauth publication-file endpoint for datasets that allow
anonymous consumption. This probe reads only a small prefix from each response;
it does not persist or parse the full national feeds yet.
"""
from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{offer_id}/file/noauth"
USER_AGENT = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"
MAX_SAMPLE = 262144

OFFERS = {
    "enbw-static": "907574882292453376",
    "enbw-dynamic": "907575401287241728",
    "chargecloud-static": "978597062404620288",
    "eco-movement-static": "954064102947180544",
    "eround-static": "961625658278940672",
    "eround-dynamic": "961629419076456448",
    "monta-static": "963836072152719360",
    "monta-dynamic": "963870983660167168",
    "qwello-static": "972963216296222720",
    "qwello-dynamic": "972966368902897664",
    "edri-static": "972837891969273856",
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def probe(label: str, offer_id: str) -> dict:
    url = ENDPOINT.format(offer_id=offer_id)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/xml, */*",
        "Accept-Encoding": "gzip",
        "Range": f"bytes=0-{MAX_SAMPLE - 1}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            status = getattr(response, "status", 200)
            headers = dict(response.headers.items())
            content_encoding = response.headers.get("Content-Encoding", "").lower()
            if "gzip" in content_encoding:
                reader = gzip.GzipFile(fileobj=response)
                sample = reader.read(MAX_SAMPLE)
            else:
                sample = response.read(MAX_SAMPLE)
    except urllib.error.HTTPError as exc:
        body = exc.read(4096)
        return {
            "label": label,
            "offerId": offer_id,
            "url": url,
            "ok": False,
            "status": exc.code,
            "error": body.decode("utf-8", errors="replace")[:1000],
        }
    except Exception as exc:
        return {"label": label, "offerId": offer_id, "url": url, "ok": False, "error": repr(exc)}

    text = sample.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()
    kind = "json" if stripped.startswith(("{", "[")) else "xml" if stripped.startswith("<") else "unknown"
    return {
        "label": label,
        "offerId": offer_id,
        "url": url,
        "ok": 200 <= status < 300,
        "status": status,
        "contentType": headers.get("Content-Type"),
        "contentEncoding": headers.get("Content-Encoding"),
        "contentLength": headers.get("Content-Length"),
        "contentRange": headers.get("Content-Range"),
        "sampleBytes": len(sample),
        "detectedKind": kind,
        "containsAfir": "afir" in text.lower(),
        "containsEnergyInfrastructure": "energyInfrastructure" in text or "energyinfrastructure" in text.lower(),
        "containsStatus": "status" in text.lower() or "available" in text.lower() or "occup" in text.lower(),
        "preview": text[:1000],
    }


def main():
    results = [probe(label, offer_id) for label, offer_id in OFFERS.items()]
    payload = {
        "schemaVersion": 2,
        "dataset": "germany-mobilithek-afir-noauth-probe",
        "generatedAt": now(),
        "results": results,
        "counts": {
            "offers": len(results),
            "ok": sum(bool(x.get("ok")) for x in results),
            "json": sum(x.get("detectedKind") == "json" for x in results),
            "xml": sum(x.get("detectedKind") == "xml" for x in results),
        },
    }
    out = Path("data/germany/mobilithek_noauth_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_MOBILITHEK_NOAUTH=" + json.dumps(payload["counts"], sort_keys=True))
    for result in results:
        print("TCC_MOBILITHEK_PAYLOAD=" + json.dumps({k: result.get(k) for k in (
            "label", "offerId", "ok", "status", "contentType", "contentEncoding",
            "contentLength", "contentRange", "sampleBytes", "detectedKind",
            "containsAfir", "containsEnergyInfrastructure", "containsStatus", "error"
        ) if k in result}, ensure_ascii=False, sort_keys=True))
    if payload["counts"]["ok"] == 0:
        raise SystemExit("no tested AFIR offer supports anonymous payload access")


if __name__ == "__main__":
    main()
