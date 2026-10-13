#!/usr/bin/env python3
"""Bounded read-only EnergyVision DATEX inspection. Never publishes offers.

Only structural metadata is recorded: XML element/attribute names and counts,
payload lengths and SHA-256. No response body, station identity, coordinates,
price, personal data or API key is written to reports or logs.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from defusedxml import ElementTree as DET

BASE = "https://datex.cpo.energyvision.be/datex"
ENDPOINTS = ("metadata", "health", "energy-infrastructure-table", "energy-infrastructure-status")
MAX_BYTES = {"metadata": 2_000_000, "health": 2_000_000,
             "energy-infrastructure-table": 60_000_000,
             "energy-infrastructure-status": 60_000_000}
RELEVANT = ("charging", "infrastructure", "electric", "evse", "plug", "connector",
            "tariff", "price", "cost", "rate", "station", "location", "point")


def local(tag: str) -> str:
    return str(tag).split("}")[-1].split(":")[-1]


def safely_read(response, limit: int) -> bytes:
    """Prevent unbounded network and gzip expansion."""
    content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("response_size_limit_exceeded")
    if response.headers.get("Content-Encoding", "").lower() == "gzip" or content[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as g:
            decoded = g.read(limit + 1)
        if len(decoded) > limit:
            raise ValueError("expanded_response_size_limit_exceeded")
        return decoded
    return content


def xml_structure(body: bytes) -> dict:
    """Stream parse untrusted XML with entities forbidden; never inspect values."""
    tags = collections.Counter()
    attributes = collections.Counter()
    paths = collections.Counter()
    stack: list[str] = []
    root = ""
    namespace = ""
    for event, elem in DET.iterparse(io.BytesIO(body), events=("start", "end")):
        if event == "start":
            name = local(elem.tag)
            if not root:
                root = name
                if isinstance(elem.tag, str) and elem.tag.startswith("{"):
                    namespace = elem.tag[1:].split("}", 1)[0]
            stack.append(name)
            tags[name] += 1
            for attribute in elem.attrib:
                attributes[local(attribute)] += 1
            if len(stack) <= 9 and any(word in name.lower() for word in RELEVANT):
                paths["/".join(stack)] += 1
        else:
            if stack:
                stack.pop()
            elem.clear()
    if not root or not tags:
        raise ValueError("empty_or_non_xml_document")
    return {
        "rootTag": root,
        "namespace": namespace,
        "totalElements": sum(tags.values()),
        "distinctElementTags": len(tags),
        "elementCounts": dict(tags.most_common(120)),
        "attributeCounts": dict(attributes.most_common(45)),
        "relevantPaths": dict(paths.most_common(75)),
    }


def fetch(endpoint: str, token: str) -> dict:
    limit = MAX_BYTES[endpoint]
    req = urllib.request.Request(
        BASE + "/" + endpoint,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/xml, text/xml, application/json",
                 "Accept-Encoding": "identity",
                 "User-Agent": "TeslaChargeCompanion/9 EnergyVision-DATEX-validation"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
                result = {"httpStatus": response.status, "contentType": content_type}
                body = safely_read(response, limit)
            result.update({
                "payloadBytes": len(body),
                "payloadSha256": hashlib.sha256(body).hexdigest(),
            })
            if body.lstrip().startswith(b"<"):
                result["xml"] = xml_structure(body)
            elif content_type.endswith("json"):
                # JSON values may contain station identities. Record only top-level keys.
                doc = json.loads(body)
                result["jsonTopLevelType"] = type(doc).__name__
                result["jsonKeys"] = sorted(doc)[:30] if isinstance(doc, dict) else []
            else:
                raise ValueError("unexpected_non_xml_non_json_response")
            return result
        except urllib.error.HTTPError as exc:
            code = exc.code
            if code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(2)
                continue
            return {"httpStatus": code, "error": "http_error"}
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt == 0:
                time.sleep(2)
                continue
            return {"error": type(exc).__name__}
        except (ValueError, DET.ParseError) as exc:
            return {"error": str(exc)[:90]}
    return {"error": "request_failed"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/belgium/energyvision-datex-probe-latest.json")
    args = parser.parse_args()
    token = os.environ.get("ENERGYVISION_API_KEY", "").strip()
    if not token:
        raise SystemExit("ENERGYVISION_API_KEY not configured; cannot perform authenticated collection")
    results = {endpoint: fetch(endpoint, token) for endpoint in ENDPOINTS}
    report = {
        "schemaVersion": 1, "provider": "EnergyVision", "country": "BE",
        "mode": "authenticated_read_only_structure_audit",
        "collectedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "urlHost": "datex.cpo.energyvision.be",
        "endpoints": results,
        "v9PricingReady": False,
        "reason": "No EVSE-level identity or applicable ad-hoc tariff has yet been verified",
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    overview = {
        endpoint: {
            "status": result.get("httpStatus"),
            "error": result.get("error"),
            "bytes": result.get("payloadBytes"),
            "root": result.get("xml", {}).get("rootTag"),
            "topTags": list(result.get("xml", {}).get("elementCounts", {}).items())[:18],
            "priceRelated": {k: v for k, v in result.get("xml", {}).get("elementCounts", {}).items()
                             if any(t in k.lower() for t in ("price", "tariff", "cost", "fee"))},
        } for endpoint, result in results.items()
    }
    print(json.dumps(overview, ensure_ascii=False, sort_keys=True))
    healthy = all(result.get("httpStatus") == 200 and result.get("payloadBytes", 0) > 0
                  for result in results.values())
    print("ENERGYVISION_READONLY_DATEX_ENDPOINTS_VALIDATED" if healthy
          else "ENERGYVISION_READONLY_DATEX_INCOMPLETE")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
