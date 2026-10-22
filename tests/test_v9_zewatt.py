"""Offline execution of archived Ze-Watt static/dynamic/company method."""

import gzip
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from v9_rebuild import zewatt
from v9_rebuild.orchestrator import read_sources, run_source


def archived_station():
    with gzip.open(zewatt.ROOT / "data/zewatt/france/current/zewatt.json.gz", "rt") as handle:
        data = json.load(handle)
    return next(row for row in data["stations"] if row.get("visitorStripe") and row.get("hasPositivePrice")
                and (row.get("static") or {}).get("evses"))


class OfflineRunner:
    def __init__(self, *, direct=True, bad_pagination=False, company_error=False):
        self.direct = direct
        self.bad_pagination = bad_pagination
        self.company_error = company_error

    def __call__(self, command, **kwargs):
        if command[1].endswith("extract_zewatt_france.mjs"):
            row = archived_station()
            static = []
            for evse in row["static"]["evses"]:
                static.append({"id_station_local": row["serial"],
                               "id_station_itinerance": row["static"]["stationIdItinerance"],
                               "nom_station": row["static"]["stationName"],
                               "id_pdc_itinerance": evse["idPdcItinerance"],
                               "puissance_nominale": evse["nominalPowerW"],
                               "adresse_station": evse["address"],
                               "coordonneesXY": evse["coordinates"]})
            dynamic = [{"id_pdc_itinerance": static[0]["id_pdc_itinerance"], "etat_pdc": "EN_SERVICE"}]
            norm = row["normalizedPrice"]
            raw = {"per_kwh_price": norm["perKwhEurTtc"],
                   "per_minute_price": norm["perMinuteEurTtc"],
                   "per_minute_parking_price": norm["postChargePerMinuteEurTtc"],
                   "parking_delay_in_minutes": norm["postChargeGraceMinutes"],
                   "transaction_time_per_minute_parking_price": norm["connectedTimePerMinuteEurTtc"],
                   "transaction_time_parking_delay_in_minutes": norm["connectedTimeGraceMinutes"],
                   "per_session_price": norm["perSessionEurTtc"]}
            company = {"name": row["name"], "pk": row["pk"], "visitor_stripe": self.direct,
                       "visitor_gireve": row["visitorGireve"],
                       "json_ttc_price_for_legal_compliance": raw,
                       "connectors": row["connectors"]}
            preload = Path(kwargs["cwd"]) / "fixture_fetch.mjs"
            preload.write_text(
                "const staticRows=" + json.dumps(static) + ";const dynamicRows=" + json.dumps(dynamic) +
                ";const company=" + json.dumps(company) + ";" +
                "globalThis.fetch=async(url)=>{url=String(url);" +
                "if(url.includes('1189bf16'))return new Response(JSON.stringify({data:url.includes('page=2')?[]:staticRows,meta:{total:" +
                ("3" if self.bad_pagination else "staticRows.length") + "}}),{status:200});" +
                "if(url.includes('5a9a3832'))return new Response(JSON.stringify({data:dynamicRows,meta:{total:dynamicRows.length}}),{status:200});" +
                ("if(url.includes('/company'))return new Response('{}',{status:400});" if self.company_error else
                 "if(url.includes('/company'))return new Response(JSON.stringify(company),{status:200});") +
                "throw Error('unexpected fixture URL '+url)};\n")
            command = ["node", "--import", str(preload), command[1], *command[2:]]
        return subprocess.run(command, **kwargs)


class ZewattMigrationTests(unittest.TestCase):
    def test_exact_offers_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            zewatt.run(base / "direct", runner=OfflineRunner())
            payload = zewatt.validate_output(base / "direct")
            self.assertEqual(len(payload["directOffers"]), 1)
            self.assertEqual(set(payload["directOffers"][0]["evseIds"]),
                             {row["idPdcItinerance"] for row in archived_station()["static"]["evses"]})
            source = next(row for row in read_sources() if row["id"] == "FR:zewatt")
            def process(command, **_):
                zewatt.run(Path(command[-1]), runner=OfflineRunner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_zero_direct_and_incomplete_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            zewatt.run(base / "no-direct", runner=OfflineRunner(direct=False))
            self.assertEqual(zewatt.validate_output(base / "no-direct")["directOffers"], [])
            with self.assertRaisesRegex(RuntimeError, "method failed"):
                zewatt.run(base / "pagination", runner=OfflineRunner(bad_pagination=True))
            with self.assertRaisesRegex(ValueError, "technical collection"):
                zewatt.run(base / "company-error", runner=OfflineRunner(company_error=True))


if __name__ == "__main__":
    unittest.main()
