#!/usr/bin/env python3
"""Keep a public field-whitelisted snapshot of GeniePoint's official OCPI feed."""
import argparse
import gzip
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(source):
    if source.startswith("https://"):
        with urllib.request.urlopen(urllib.request.Request(source, headers={"User-Agent": "TCC-public-OCPI/1.0"}), timeout=30) as response:
            payload = json.load(response)
    else:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if payload.get("status_code") not in (None, 1000) or not isinstance(payload.get("data"), list):
        raise ValueError("GeniePoint official OCPI response is not a successful data array")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--locations", default="https://opendata.geniepoint.co.uk/locations")
    parser.add_argument("--tariffs", default="https://opendata.geniepoint.co.uk/tariffs")
    args = parser.parse_args()
    locations_raw, tariffs_raw = load(args.locations), load(args.tariffs)
    locations = []
    for raw in locations_raw["data"]:
        if raw.get("country_code") != "GB" or raw.get("party_id") != "GPT" or raw.get("publish") is not True:
            raise ValueError("GeniePoint feed contains non-public or foreign location")
        evses = []
        for evse in raw.get("evses") or []:
            connectors = [{key: connector.get(key) for key in
                           ("id", "standard", "power_type", "max_electric_power", "tariff_ids")}
                          for connector in evse.get("connectors") or []]
            evses.append({"uid": evse.get("uid"), "evse_id": evse.get("evse_id"),
                          "status": evse.get("status"), "connectors": connectors})
        locations.append({key: raw.get(key) for key in
                          ("country_code", "party_id", "id", "publish", "name", "address", "city", "postal_code", "country", "coordinates")}
                         | {"evses": evses})
    tariffs = [{"id": raw.get("id"), "currency": raw.get("currency"), "type": raw.get("type"),
                "elements": [{"price_components": [{key: component.get(key) for key in ("type", "price", "vat", "step_size")}
                                                 for component in element.get("price_components") or []],
                              "restrictions": element.get("restrictions")}
                             for element in raw.get("elements") or []]}
               for raw in tariffs_raw["data"]]
    ids = {str(t["id"]) for t in tariffs if t["id"] is not None}
    references = {str(tid) for loc in locations for evse in loc["evses"]
                  for connector in evse["connectors"] for tid in connector.get("tariff_ids") or []}
    connector_count = sum(len(evse["connectors"]) for loc in locations for evse in loc["evses"])
    if len(locations) < 300 or connector_count < 1100 or len(tariffs) < 500 or references - ids:
        raise ValueError("GeniePoint feed coverage or exact tariff join regressed")
    if any(t["currency"] != "GBP" for t in tariffs):
        raise ValueError("GeniePoint tariff currency drift")
    output = ROOT / "data/national/uk_geniepoint_official_ocpi.json.gz"
    report = ROOT / "reports/uk/geniepoint-official-ocpi-latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    data = {"country": "GB", "network": "GeniePoint", "sourceLocations": "https://opendata.geniepoint.co.uk/locations",
            "sourceTariffs": "https://opendata.geniepoint.co.uk/tariffs", "retrievedAt": locations_raw.get("timestamp"),
            "locations": locations, "tariffs": tariffs}
    with output.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", mtime=0) as compressed:
            compressed.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    summary = {"retrievedAt": data["retrievedAt"], "locations": len(locations),
               "connectors": connector_count, "tariffs": len(tariffs),
               "referencedTariffIds": len(references), "missingTariffIds": 0,
               "priceBasis": "OCPI 2.2 price excludes VAT; component VAT must be applied before consumer ranking"}
    report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
