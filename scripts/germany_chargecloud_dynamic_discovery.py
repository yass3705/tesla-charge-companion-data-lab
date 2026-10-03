#!/usr/bin/env python3
"""Discover and validate the public Mobilithek chargecloud dynamic AFIR offer.

Bounded staging probe: query a few public metadata pages, extract publication ids
whose metadata mentions chargecloud + dynamic status, then verify the anonymous
publication endpoint. Never guess or activate an unverified id.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"
SEARCH_URL = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search?page={page}&size=100&sort=latest,desc"
DETAIL_URL = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{offer_id}"
FILE_URL = "https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{offer_id}/file/noauth"
GOVDATA_URL = "https://www.govdata.de/suche?query=AFIR-recharging-dyn-chargecloud-json"
KNOWN_STATIC_ID = "978597062404620288"


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request(url: str, *, body: dict | None = None, timeout: int = 15):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"User-Agent": UA, "Accept": "application/json, text/html, */*", "Accept-Encoding": "gzip"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw, {"status": getattr(r, "status", 200), "contentType": r.headers.get("Content-Type"), "bytes": len(raw)}


def request_json(url: str, *, body: dict | None = None, timeout: int = 15):
    raw, transport = request(url, body=body, timeout=timeout)
    return json.loads(raw.decode("utf-8-sig")), transport


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
        if "chargecloud" not in text or not any(x in text for x in ("dyn", "dynamic", "status")):
            continue
        for key in ("publicationId", "publicationID", "offerId", "offerID", "id"):
            value = row.get(key)
            if value is not None and re.fullmatch(r"\d{15,20}", str(value)):
                found.add(str(value))
        found.update(re.findall(r"\b\d{15,20}\b", text))
    return found


def contains_status_publication(obj: Any):
    if isinstance(obj, dict):
        return "aegiEnergyInfrastructureStatusPublication" in obj or any(contains_status_publication(v) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_status_publication(v) for v in obj)
    return False


def count_status_objects(obj: Any):
    counts = {"siteStatus": 0, "stationStatus": 0, "pointStatus": 0}
    def walk(value: Any):
        if isinstance(value, dict):
            for key, child in value.items():
                lk = key.lower()
                if lk == "energyinfrastructuresitestatus": counts["siteStatus"] += len(child) if isinstance(child, list) else int(child is not None)
                elif lk == "energyinfrastructurestationstatus": counts["stationStatus"] += len(child) if isinstance(child, list) else int(child is not None)
                elif lk == "refillpointstatus": counts["pointStatus"] += len(child) if isinstance(child, list) else int(child is not None)
                walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(obj)
    return counts


def probe_offer(offer_id: str):
    out = {"offerId": offer_id}
    try:
        meta, transport = request_json(DETAIL_URL.format(offer_id=offer_id))
        out["metadata"] = {"transport": transport, "topKeys": list(meta.keys())[:30] if isinstance(meta, dict) else None}
    except Exception as exc:
        out["metadata"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        raw, transport = request(FILE_URL.format(offer_id=offer_id), timeout=30)
        payload = json.loads(raw.decode("utf-8-sig"))
        out["file"] = {
            "transport": transport,
            "isDynamicStatusPublication": contains_status_publication(payload),
            "statusObjectCounts": count_status_objects(payload),
            "topKeys": list(payload.keys())[:30] if isinstance(payload, dict) else None,
        }
    except Exception as exc:
        out["file"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


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

    try:
        meta, transport = request_json(DETAIL_URL.format(offer_id=KNOWN_STATIC_ID))
        report["knownStaticMetadataReachable"] = True
        report["knownStaticMetadataTransport"] = transport
        report["knownStaticMetadataKeys"] = list(meta.keys())[:30] if isinstance(meta, dict) else None
        print("TCC_CHARGECLOUD_METADATA_STATIC=" + json.dumps({"reachable": True, "transport": transport}, sort_keys=True))
    except Exception as exc:
        report["knownStaticMetadataReachable"] = False
        report["knownStaticMetadataError"] = f"{type(exc).__name__}: {exc}"
        print("TCC_CHARGECLOUD_METADATA_STATIC=" + json.dumps({"reachable": False, "error": report["knownStaticMetadataError"]}, sort_keys=True))

    candidates = set()
    for body in ({}, {"searchText": "chargecloud"}, {"query": "chargecloud"}):
        for page in range(0, 4):
            attempt = {"body": body, "page": page}
            try:
                payload, transport = request_json(SEARCH_URL.format(page=page), body=body)
                ids = sorted(candidate_ids_from_obj(payload))
                attempt.update({"transport": transport, "candidateIds": ids, "topKeys": list(payload.keys())[:30] if isinstance(payload, dict) else None})
                candidates.update(ids)
                print("TCC_CHARGECLOUD_CATALOGUE_PAGE=" + json.dumps(attempt, ensure_ascii=False, sort_keys=True))
                report["searchAttempts"].append(attempt)
                if ids:
                    break
            except Exception as exc:
                attempt["error"] = f"{type(exc).__name__}: {exc}"
                report["searchAttempts"].append(attempt)
                print("TCC_CHARGECLOUD_CATALOGUE_PAGE=" + json.dumps(attempt, ensure_ascii=False, sort_keys=True))
                break
        if candidates:
            break

    # GovData fallback: its public page may expose the Mobilithek publication URL.
    if not candidates:
        try:
            raw, transport = request(GOVDATA_URL, timeout=20)
            text = raw.decode("utf-8", errors="replace")
            ids = set(re.findall(r"mobilithek\.info/(?:offers/|mdp-api/[^\"' ]*/publication/)(\d{15,20})", text, flags=re.I))
            report["govDataFallback"] = {"transport": transport, "candidateIds": sorted(ids)}
            candidates.update(ids)
            print("TCC_CHARGECLOUD_GOVDATA=" + json.dumps(report["govDataFallback"], sort_keys=True))
        except Exception as exc:
            report["govDataFallback"] = {"error": f"{type(exc).__name__}: {exc}"}

    report["candidateOfferIds"] = sorted(candidates)
    for offer_id in report["candidateOfferIds"]:
        probe = probe_offer(offer_id)
        report["probes"].append(probe)
        print("TCC_CHARGECLOUD_DYNAMIC_PROBE=" + json.dumps(probe, ensure_ascii=False, sort_keys=True))
        if (probe.get("file") or {}).get("isDynamicStatusPublication"):
            report["resolvedDynamicOfferId"] = offer_id
            break

    report["resolved"] = report["resolvedDynamicOfferId"] is not None
    out = Path("data/germany/chargecloud_dynamic_discovery.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_CHARGECLOUD_DYNAMIC_DISCOVERY=" + json.dumps({
        "resolved": report["resolved"],
        "resolvedDynamicOfferId": report["resolvedDynamicOfferId"],
        "candidateOfferIds": report["candidateOfferIds"],
        "knownStaticMetadataReachable": report.get("knownStaticMetadataReachable"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
