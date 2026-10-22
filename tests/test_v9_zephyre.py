"""Offline execution of archived Zephyre extractor and offer compiler."""

import csv
import gzip
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from v9_rebuild import zephyre
from v9_rebuild.orchestrator import read_sources, run_source


def archived_station():
    with gzip.open(zephyre.ROOT / "data/zephyre/france/current/zephyre.json.gz", "rt") as handle:
        data = json.load(handle)
    return next(row for row in data["stations"] if row.get("multitenantDirectPaymentAvailable")
                and (row.get("tariff") or {}).get("priceComponents") and row.get("irve"))


class OfflineRunner:
    def __init__(self, *, direct=True, nearby_error=False):
        self.direct = direct
        self.nearby_error = nearby_error

    def __call__(self, command, **kwargs):
        if command[1].endswith("extract_zephyre_france.mjs"):
            row = archived_station()
            irve = row["irve"]
            columns = ["id_pdc_itinerance", "id_station_itinerance", "id_station_local", "nom_station",
                       "nom_operateur", "adresse_station", "consolidated_latitude", "consolidated_longitude",
                       "puissance_nominale", "tarification", "date_maj", "last_modified",
                       "datagouv_dataset_id", "datagouv_resource_id"]
            vals = [irve.get(key) for key in ("evseId", "stationId", "stationLocalId", "stationName",
                    "operator", "address", "latitude", "longitude", "nominalPowerKw", "irveTarification",
                    "dateMaj", "lastModified", "datasetId", "resourceId")]
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(columns)
            writer.writerow(["" if value is None else value for value in vals])
            csv_body = stream.getvalue()
            cp = {"evseId": row["evseId"], "name": row["internalName"], "evseStatus": row["status"],
                  "available": row["available"], "multitenantDirectPaymentAvailable": self.direct,
                  "paymentMethods": row["paymentMethods"], "maxChargingPower": row["maxChargingPowerKw"],
                  "tariff": row["tariff"]}
            nearby = [{"address": row["address"], "chargePoints": [cp]}]
            detail = {"address": row["address"], "provider": row["provider"], "currency": row["currency"],
                      "chargePoints": [cp]}
            preload = Path(kwargs["cwd"]) / "fixture_fetch.mjs"
            preload.write_text(
                "const csv=" + json.dumps(csv_body) + ";const nearby=" + json.dumps(nearby) +
                ";const detail=" + json.dumps(detail) + ";" +
                "globalThis.fetch=async(url)=>{url=String(url);" +
                "if(url.includes('data.gouv.fr'))return new Response(csv,{status:200});" +
                ("if(url.includes('/nearby'))return new Response('{}',{status:400});" if self.nearby_error else
                 "if(url.includes('/nearby'))return new Response(JSON.stringify(nearby),{status:200});") +
                "if(url.includes('/chargepoint/'))return new Response(JSON.stringify(detail),{status:200});" +
                "throw Error('unexpected fixture URL '+url)};\n")
            command = ["node", "--import", str(preload), command[1], *command[2:]]
        return subprocess.run(command, **kwargs)


class ZephyreMigrationTests(unittest.TestCase):
    def test_exact_offer_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            zephyre.run(base / "direct", runner=OfflineRunner())
            payload = zephyre.validate_output(base / "direct")
            self.assertEqual(len(payload["directOffers"]), 1)
            self.assertEqual(payload["directOffers"][0]["evseIds"], [archived_station()["evseId"]])
            source = next(row for row in read_sources() if row["id"] == "FR:zephyre")
            def process(command, **_):
                zephyre.run(Path(command[-1]), runner=OfflineRunner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_zero_direct_is_valid_and_transport_error_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            zephyre.run(base / "no-direct", runner=OfflineRunner(direct=False))
            self.assertEqual(zephyre.validate_output(base / "no-direct")["directOffers"], [])
            with self.assertRaisesRegex(ValueError, "technical execution"):
                zephyre.run(base / "error", runner=OfflineRunner(nearby_error=True))


if __name__ == "__main__":
    unittest.main()
