#!/usr/bin/env python3
"""Discover and validate the public Mobilithek chargecloud dynamic AFIR offer.

This script deliberately avoids guessing a publication id. It queries the public
Mobilithek metadata catalogue, extracts candidate publication ids whose metadata
mentions chargecloud and dynamic/recharging terms, and probes the anonymous file
endpoint. The result is staging/QA only.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"
SEARCH_URL = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search?page={page}&size=100&sort=latest,desc"
DETAIL_URL = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{offer_id}"
FILE_URL = "https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{offer_id}/file/noauth"
KNOWN_STATIC_ID = "978597062404620288"
TARGET_MARKERS = ("chargecloud", "afir-recharging-dyn", "recharging dynamic", "dynamic data chargecloud")


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_json(url: str, *, body: dict | None = None, timeout: int = 60):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, */*",
        "Accept-Encoding": "gzip",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8-sig")), {
            "status": getattr(r, "status", 200),
            "contentType": r.headers.get("Content-Type"),
            "bytes": len(raw),
        }


def request_bytes(url: str, timeout: int = 120):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, */*",
        "Accept-Encoding": "gzip",
        "Range": "bytes=0-99999999",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw, {
            "status": getattr(r, "status", 200),
            "contentType": r.headers.get("Content-Type"),
            "bytes": len(raw),
        }


def iter_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_dicts(value)


def candidate_ids_from_obj(obj: Any):
    found = set()
    for row in iter_dicts(obj):
        text = json.dumps(row, ensure_ascii=False).lower()
        if "chargecloud" not in text:
            continue
        if not any(marker in text for marker in ("dyn", "dynamic", "status")):
            continue
        for key in ("publicationId", "publicationID", "offerId", "offerID", "id"):
            value = row.get(key)
            if value is not None and re.fullmatch(r"\d{15,20}", str(value)):
                found.add(str(value))
        for value in re.findall(r"\b\d{15,20}\b", text):
            found.add(value)
    return found


def contains_status_publication(obj: Any):
    if isinstance(obj, dict):
        if "aegiEnergyInfrastructureStatusPublication" in obj:
            return True
        return any(contains_status_publication(v) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_status_publication(v) for v in obj)
    return False


def count_status_objects(obj: Any):
    counts = {"siteStatus": 0, "stationStatus": 0, "pointStatus": 0}
    def walk(value: Any):
        if isinstance(value, dict):
            for key, child in value.items():
                lk = key.lower()
                if lk == "energyinfrastructuresitestatus":
                    counts["siteStatus"] += len(child) if isinstance(child, list) else int(child is not None)
                elif lk == "energyinfrastructurestationstatus":
                    counts["stationStatus"] += len(child) if isinstance(child, list) else int(child is not None)
                elif lk == "refillpointstatus":
                    counts["pointStatus"] += len(child) if isinstance(child, list) else int(child is not None)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(obj)
    return counts


def probe_offer(offer_id: str):
    result = {"offerId": offer_id, "metadata": None, "file": None}
    try:
        meta, transport = request_json(DETAIL_URL.format(offer_id=offer_id))
        result["metadata"] = {
            "transport": transport,
            "sample": meta,
        }
    except Exception as exc:
        result["metadata"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        raw, transport = request_bytes(FILE_URL.format(offer_id=offer_id))
        parsed = json.loads(raw.decode("utf-8-sig"))
        result["file"] = {
            "transport": transport,
            "json": True,
            "isDynamicStatusPublication": contains_status_publication(parsed),
            "statusObjectCounts": count_status_objects(parsed),
            "topKeys": list(parsed.keys())[:30] if isinstance(parsed, dict) else None,
        }
    except Exception as exc:
        result["file"] = {"error": f"{type(exc).__name__}: {exc}"}
    return result


def main():
    report = {
        "dataset": "germany-chargecloud-dynamic-offer-discovery",
        "generatedAt": now(),
        "scope": {"stagedOnly": True, "publishesToTcc": False},
        "knownStaticOfferId": KNOWN_STATIC_ID,
        "searchAttempts": [],
        "candidateOfferIds": [],
        "probes": [],
        "resolvedDynamicOfferId": None,
    }

    # Validate that the public metadata endpoint itself is reachable for a known offer.
    try:
        static_meta, transport = request_json(DETAIL_URL.format(offer_id=KNOWN_STATIC_ID))
        report["knownStaticMetadataReachable"] = True
        report["knownStaticMetadataTransport"] = transport
        report["knownStaticMetadataKeys"] = list(static_meta.keys()) if isinstance(static_meta, dict) else None
    except Exception as exc:
        report["knownStaticMetadataReachable"] = False
        report["knownStaticMetadataError"] = f"{type(exc).__name__}: {exc}"

    bodies = [
        {},
        {"searchText": "chargecloud"},
        {"search": "chargecloud"},
        {"text": "chargecloud"},
        {"query": "chargecloud"},
    ]
    candidates = set()
    successful_body = None

    for body in bodies:
        attempt = {"body": body, "pages": [], "error": None}
        try:
            for page in range(0, 20):
                payload, transport = request_json(SEARCH_URL.format(page=page), body=body)
                page_ids = sorted(candidate_ids_from_obj(payload))
                attempt["pages"].append({
                    "page": page,
                    "transport": transport,
                    "candidateIds": page_ids,
                    "topType": type(payload).__name__,
                    "topKeys": list(payload.keys())[:30] if isinstance(payload, dict) else None,
                })
                candidates.update(page_ids)
                if page_ids:
                    successful_body = body
                    break
                # Stop once the API clearly reports an empty page.
                serialized = json.dumps(payload, separators=(",", ":"))
                if serialized in ("[]", "{}"):
                    break
            report["searchAttempts"].append(attempt)
            if candidates:
                break
        except Exception as exc:
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            report["searchAttempts"].append(attempt)

    report["successfulSearchBody"] = successful_body
    report["candidateOfferIds"] = sorted(candidates)

    for offer_id in sorted(candidates):
        probe = probe_offer(offer_id)
        report["probes"].append(probe)
        if (probe.get("file") or {}).get("isDynamicStatusPublication"):
            report["resolvedDynamicOfferId"] = offer_id
            break

    # If catalogue search failed, retain a useful signal rather than inventing an id.
    report["resolved"] = report["resolvedDynamicOfferId"] is not None

    out = Path("data/germany/chargecloud_dynamic_discovery.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "resolved": report["resolved"],
        "resolvedDynamicOfferId": report["resolvedDynamicOfferId"],
        "candidateOfferIds": report["candidateOfferIds"],
        "knownStaticMetadataReachable": report.get("knownStaticMetadataReachable"),
    }
    print("TCC_CHARGECLOUD_DYNAMIC_DISCOVERY=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    for probe in report["probes"]:
        print("TCC_CHARGECLOUD_DYNAMIC_PROBE=" + json.dumps({
            "offerId": probe["offerId"],
            "file": probe.get("file"),
        }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
